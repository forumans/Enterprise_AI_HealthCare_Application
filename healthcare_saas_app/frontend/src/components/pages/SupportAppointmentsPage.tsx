/**
 * Support Appointments Page Component
 * Lets support staff manage appointments on behalf of a patient ("patient" mode) or a doctor
 * ("doctor" mode): book new appointments, edit the reason, reschedule and cancel.
 */

import React, { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { isAppointmentUpcoming, parseErrorMessage, parseServerDate } from "../../utils";
import type { SupportAppointmentRow } from "../../types";
import { RescheduleAppointmentModal, formatDateTime, type RescheduleTarget } from "../common/RescheduleAppointmentModal";
import { SlotPickerCalendar } from "../common/SlotPickerCalendar";
import { SupportSearchPanel } from "../common/SupportSearchPanel";

type Mode = "patient" | "doctor";
type Person = { id: string; name: string; detail?: string };

interface SupportAppointmentsPageProps {
  auth: any;
  mode: Mode;
}

const cellStyle: React.CSSProperties = { padding: '12px', color: '#eef8ff', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' };
const headStyle: React.CSSProperties = { padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' };
const labelStyle: React.CSSProperties = { fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' };
const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '11px 12px',
  borderRadius: '10px',
  border: '1px solid rgba(136, 194, 227, 0.36)',
  fontSize: '14px',
  backgroundColor: 'rgba(9, 35, 55, 0.82)',
  color: '#eef8ff'
};
// Keeps scrolled-to sections clear of the sticky top bar
const scrollTarget: React.CSSProperties = { scrollMarginTop: '90px' };
const scrollIntoView = (el: HTMLElement | null) => el?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
const actionButton =(color: string, busy = false): React.CSSProperties => ({
  background: busy ? '#94a3b8' : color,
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  padding: '6px 12px',
  fontSize: '12px',
  cursor: busy ? 'not-allowed' : 'pointer',
  fontWeight: '500'
});

export function SupportAppointmentsPage({ auth, mode }: SupportAppointmentsPageProps) {
  const token: string = auth.session.accessToken;
  const [selectedId, setSelectedId] = useState("");
  const [rows, setRows] = useState<SupportAppointmentRow[]>([]);
  const [loadingRows, setLoadingRows] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<RescheduleTarget | null>(null);

  // Booking form: the counterpart is a doctor in patient mode, a patient in doctor mode
  const [counterpart, setCounterpart] = useState<Person | null>(null);
  const counterpartId = counterpart?.id ?? "";
  const [reason, setReason] = useState("");
  const [slotKey, setSlotKey] = useState<string | null>(null);
  const [booking, setBooking] = useState(false);
  const [calendarRefresh, setCalendarRefresh] = useState(0);
  // The appointment just booked: highlighted and scrolled to in the upcoming list
  const [justBookedId, setJustBookedId] = useState<string | null>(null);
  // Bumped after a booking to remount (and so clear) both search panels
  const [searchReset, setSearchReset] = useState(0);

  // The patient/doctor being managed, picked from the name/phone search results
  const [subject, setSubject] = useState<Person | null>(null);

  // Picking a person scrolls the page down to what comes next
  const upcomingRef = useRef<HTMLDivElement>(null);
  const bookingDetailsRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (subject) scrollIntoView(upcomingRef.current); }, [subject]);
  useEffect(() => { if (counterpart) scrollIntoView(bookingDetailsRef.current); }, [counterpart]);
  // After booking, scroll back up to the new appointment (set only once the list has reloaded)
  useEffect(() => {
    if (!justBookedId) return;
    const row = upcomingRef.current?.querySelector<HTMLElement>(`[data-appointment-id="${justBookedId}"]`);
    scrollIntoView(row ?? upcomingRef.current);
  }, [justBookedId]);

  const pickSubject = (person: Person) => {
    setSubject(person);
    setSelectedId(person.id);
  };

  const pickCounterpart = (person: Person) => {
    setCounterpart(person);
    setSlotKey(null);
  };

  const bookingDoctorId = mode === "patient" ? counterpartId : selectedId;
  const bookingPatientId = mode === "patient" ? selectedId : counterpartId;

  const loadRows = async () => {
    if (!selectedId) {
      setRows([]);
      return;
    }
    setLoadingRows(true);
    try {
      const data = await api.supportListAppointments(token, mode === "patient" ? { patientId: selectedId } : { doctorId: selectedId });
      setRows(data.filter(row => isAppointmentUpcoming(row)));
    } catch (err) {
      console.error("Failed to load appointments:", err);
      alert(parseErrorMessage(err));
    } finally {
      setLoadingRows(false);
    }
  };

  useEffect(() => {
    loadRows();
    setCounterpart(null);
    setSlotKey(null);
    setReason("");
    setJustBookedId(null);
  }, [selectedId, mode]);

  const refreshAfterChange = async () => {
    await loadRows();
    setCalendarRefresh(k => k + 1);
  };

  const handleEditReason = async (row: SupportAppointmentRow) => {
    const next = window.prompt("Update the reason for this appointment:", row.reason);
    if (next === null || next.trim() === row.reason) return;
    if (next.trim().length < 5) {
      alert("Reason must be at least 5 characters.");
      return;
    }
    setBusyId(row.id);
    try {
      await api.updateAppointmentReason(token, row.id, next.trim());
      await loadRows();
    } catch (err) {
      alert(parseErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const handleCancel = async (row: SupportAppointmentRow) => {
    if (!window.confirm(`Cancel ${row.patient_name}'s appointment with ${row.doctor_name} on ${formatDateTime(parseServerDate(row.appointment_time))}?`)) {
      return;
    }
    setBusyId(row.id);
    try {
      await api.cancelAppointment(token, row.id);
      await refreshAfterChange();
      alert("Appointment cancelled successfully");
    } catch (err) {
      alert(parseErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const handleBook = async () => {
    if (!bookingDoctorId || !bookingPatientId || !slotKey) return;
    if (reason.trim().length < 5) {
      alert("Please provide a reason of at least 5 characters.");
      return;
    }
    setBooking(true);
    try {
      // slotKey is a naive local-time cell key; convert to UTC for the API
      const booked = await api.bookAppointment(token, {
        doctor_id: bookingDoctorId,
        patient_id: bookingPatientId,
        slot: new Date(slotKey).toISOString(),
        reason: reason.trim()
      });
      alert(`Appointment booked for ${formatDateTime(new Date(slotKey))}`);
      setSlotKey(null);
      setReason("");
      await refreshAfterChange();
      // Close the search results and calendar, leaving the new appointment in view
      setCounterpart(null);
      setSearchReset(k => k + 1);
      setJustBookedId(booked.id);
    } catch (err) {
      alert(parseErrorMessage(err));
    } finally {
      setBooking(false);
    }
  };

  const subjectLabel = mode === "patient" ? "Patient" : "Doctor";
  const counterpartLabel = mode === "patient" ? "Doctor" : "Patient";
  // In patient mode the patient's other bookings can't overlap the new slot
  const patientConflicts = (excludeId?: string) =>
    mode === "patient" ? rows.filter(r => r.id !== excludeId).map(r => r.appointment_time) : [];

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>{subjectLabel} Appointments</h2>
      <p style={{ color: '#b4cce2', margin: 0 }}>
        Book, update, reschedule or cancel appointments on behalf of a {subjectLabel.toLowerCase()}.
      </p>

      {mode === "patient" ? (
        <SupportSearchPanel
          key={searchReset}
          kind="patient"
          accessToken={token}
          selectedId={selectedId}
          onPick={(p) => pickSubject({ id: p.id, name: p.name, detail: p.phone })}
        />
      ) : (
        <SupportSearchPanel
          key={searchReset}
          kind="doctor"
          accessToken={token}
          selectedId={selectedId}
          onPick={(d) => pickSubject({ id: d.id, name: d.name, detail: d.specialty || 'General Practice' })}
        />
      )}

      {subject && (
        <>
          {/* Upcoming appointments */}
          <div ref={upcomingRef} className="card" style={{ padding: '16px', ...scrollTarget }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>Upcoming Appointments for {subject.name} ({rows.length})</h3>
            {loadingRows ? (
              <p style={{ color: '#b4cce2', textAlign: 'center', padding: '20px' }}>Loading appointments...</p>
            ) : rows.length === 0 ? (
              <p style={{ color: '#b4cce2', textAlign: 'center', padding: '20px' }}>No upcoming appointments</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                  <thead>
                    <tr style={{ backgroundColor: 'rgba(9, 35, 55, 0.82)' }}>
                      <th style={headStyle}>Date & Time</th>
                      <th style={headStyle}>{counterpartLabel}</th>
                      <th style={headStyle}>Reason</th>
                      <th style={headStyle}>Status</th>
                      <th style={{ ...headStyle, textAlign: 'center' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(row => (
                      <tr
                        key={row.id}
                        data-appointment-id={row.id}
                        style={{ backgroundColor: row.id === justBookedId ? 'rgba(40, 167, 69, 0.22)' : 'rgba(9, 32, 52, 0.82)', ...scrollTarget }}
                      >
                        <td style={cellStyle}>{formatDateTime(parseServerDate(row.appointment_time))}</td>
                        <td style={cellStyle}>{mode === "patient" ? row.doctor_name : row.patient_name}</td>
                        <td style={cellStyle}>{row.reason || 'No notes'}</td>
                        <td style={{ ...cellStyle, color: '#49d7c2', fontWeight: '500' }}>{row.status}</td>
                        <td style={{ ...cellStyle, textAlign: 'center', whiteSpace: 'nowrap' }}>
                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
                            <button onClick={() => handleEditReason(row)} disabled={busyId === row.id} style={actionButton('#42b5f5', busyId === row.id)}>
                              Edit Reason
                            </button>
                            <button
                              onClick={() => setRescheduleTarget({
                                id: row.id,
                                doctorId: row.doctor_id,
                                appointmentTime: row.appointment_time,
                                doctorName: row.doctor_name,
                                patientName: row.patient_name,
                                reason: row.reason,
                                status: row.status
                              })}
                              disabled={busyId === row.id}
                              style={actionButton('#f0a020', busyId === row.id)}
                            >
                              Reschedule
                            </button>
                            <button onClick={() => handleCancel(row)} disabled={busyId === row.id} style={actionButton('#dc3545', busyId === row.id)}>
                              {busyId === row.id ? 'Working...' : 'Cancel'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Book on behalf */}
          <div className="card" style={{ padding: '16px' }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>Book New Appointment for {subject.name}</h3>

            {/* Keyed by the subject (and searchReset) so switching patient/doctor, or booking, starts a fresh counterpart search */}
            <div style={{ marginBottom: '16px' }}>
              {mode === "patient" ? (
                <SupportSearchPanel
                  key={`${selectedId}-${searchReset}`}
                  kind="doctor"
                  embedded
                  accessToken={token}
                  selectedId={counterpartId}
                  onPick={(d) => pickCounterpart({ id: d.id, name: d.name, detail: d.specialty || 'General Practice' })}
                />
              ) : (
                <SupportSearchPanel
                  key={`${selectedId}-${searchReset}`}
                  kind="patient"
                  embedded
                  accessToken={token}
                  selectedId={counterpartId}
                  onPick={(p) => pickCounterpart({ id: p.id, name: p.name, detail: p.phone })}
                />
              )}
            </div>

            <div ref={bookingDetailsRef} style={{ marginBottom: '16px', ...scrollTarget }}>
              {counterpart && (
                <p style={{ color: '#eaf5ff', fontSize: '14px', margin: '0 0 12px 0' }}>
                  Booking with {counterpartLabel.toLowerCase()}: <strong>{counterpart.name}</strong>{counterpart.detail ? ` (${counterpart.detail})` : ''}
                </p>
              )}
              <label htmlFor="support-reason" style={labelStyle}>Appointment Reason <span style={{ color: '#ff90ab' }}>*</span></label>
              <textarea
                id="support-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Describe the reason for the appointment..."
                rows={3}
                style={{ ...inputStyle, resize: 'vertical' }}
              />
            </div>

            {bookingDoctorId && counterpart ? (
              <>
                <SlotPickerCalendar
                  doctorId={bookingDoctorId}
                  accessToken={token}
                  selectedKey={slotKey}
                  onSelect={setSlotKey}
                  conflictingTimes={patientConflicts()}
                  disabled={booking}
                  refreshKey={calendarRefresh}
                />
                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
                  <span style={{ color: '#b4cce2', fontSize: '14px' }}>
                    {slotKey ? `Selected: ${formatDateTime(new Date(slotKey))}` : 'Select an available slot'}
                  </span>
                  <button
                    onClick={handleBook}
                    disabled={!slotKey || booking}
                    style={{ ...actionButton('#28a745', !slotKey || booking), padding: '8px 16px', fontSize: '14px', borderRadius: '6px' }}
                  >
                    {booking ? 'Booking...' : 'Book Appointment'}
                  </button>
                </div>
              </>
            ) : (
              <p style={{ color: '#b4cce2', margin: 0 }}>Select a {counterpartLabel.toLowerCase()} to see available slots.</p>
            )}
          </div>
        </>
      )}

      {rescheduleTarget && (
        <RescheduleAppointmentModal
          target={rescheduleTarget}
          accessToken={token}
          onClose={() => setRescheduleTarget(null)}
          onRescheduled={refreshAfterChange}
          conflictingTimes={patientConflicts(rescheduleTarget.id)}
        />
      )}
    </section>
  );
}
