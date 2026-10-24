/**
 * Reschedule Appointment Modal
 * Shared by the patient (My Appointments) and doctor (Today's / Weekly Appointments) screens.
 * Shows the appointment's details read-only and the same doctor's availability calendar;
 * only the date/time changes - doctor, patient, reason and status are kept.
 */

import React, { useEffect, useState } from "react";
import { api } from "../../api";
import { OFFICE_HOUR_SLOTS, WORKDAY_FIRST_SLOT_HOUR, localSlotKey, parseServerDate, parseErrorMessage, rescheduleSlotState } from "../../utils";

export interface RescheduleTarget {
  id: string;
  doctorId: string;
  appointmentTime: string;
  doctorName?: string;
  patientName?: string;
  reason?: string;
  status?: string;
}

interface RescheduleAppointmentModalProps {
  target: RescheduleTarget;
  accessToken: string;
  onClose: () => void;
  onRescheduled: () => void | Promise<void>;
  /** Other active appointment times of the same patient (API timestamps); shown as unavailable. */
  conflictingTimes?: string[];
}

const MAX_WEEK_OFFSET = 4;
const cellBorder = '1px solid rgba(136, 194, 227, 0.36)';
const labelStyle: React.CSSProperties = { fontSize: '12px', fontWeight: '700', color: '#42b5f5', textTransform: 'uppercase', display: 'block', marginBottom: '4px' };
const valueStyle: React.CSSProperties = { margin: 0, fontSize: '14px', color: '#eef8ff' };

const formatDateTime = (date: Date) =>
  date.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });

export function RescheduleAppointmentModal({ target, accessToken, onClose, onRescheduled, conflictingTimes = [] }: RescheduleAppointmentModalProps) {
  const [availability, setAvailability] = useState<Array<{ slot_time: string; status: "AVAILABLE" | "BOOKED" | "BLOCKED" }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [weekOffset, setWeekOffset] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.listAllDoctorAvailability(target.doctorId, accessToken)
      .then(setAvailability)
      .catch((err) => {
        console.error("Failed to load doctor availability:", err);
        setError("Failed to load the doctor's availability.");
      })
      .finally(() => setLoading(false));
  }, [target.doctorId, accessToken]);

  const currentKey = localSlotKey(parseServerDate(target.appointmentTime));
  const statusByKey = new Map(availability.map(a => [localSlotKey(parseServerDate(a.slot_time)), a.status]));
  const conflictKeys = new Set(conflictingTimes.map(t => localSlotKey(parseServerDate(t))));

  const now = new Date();
  const startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() + weekOffset * 7);
  const days = Array.from({ length: 7 }, (_, i) => new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate() + i));

  const handleConfirm = async () => {
    if (!selectedKey) return;
    setSaving(true);
    setError("");
    try {
      // selectedKey is a naive local-time cell key; convert to UTC for the API
      await api.rescheduleAppointment(accessToken, target.id, new Date(selectedKey).toISOString());
      await onRescheduled();
      alert(`Appointment rescheduled to ${formatDateTime(new Date(selectedKey))}`);
      onClose();
    } catch (err) {
      console.error("Failed to reschedule appointment:", err);
      setError(parseErrorMessage(err) || "Failed to reschedule appointment. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const navButton = (disabled: boolean): React.CSSProperties => ({
    padding: '8px 16px',
    background: disabled ? '#94a3b8' : '#42b5f5',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: '14px'
  });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reschedule-title"
      onClick={(e) => { if (e.target === e.currentTarget && !saving) onClose(); }}
      style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(2, 12, 22, 0.75)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 16px', overflowY: 'auto', zIndex: 1000 }}
    >
      <div className="card" style={{ padding: '20px', width: '100%', maxWidth: '960px', backgroundColor: 'rgba(9, 35, 55, 0.98)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 id="reschedule-title" style={{ margin: 0, color: '#eaf5ff' }}>Reschedule Appointment</h3>
          <button
            onClick={onClose}
            disabled={saving}
            style={{ background: '#dc3545', color: 'white', border: 'none', borderRadius: '4px', padding: '4px 12px', cursor: 'pointer', fontSize: '14px' }}
          >
            ✕ Close
          </button>
        </div>

        {/* Appointment details (unchanged by rescheduling) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
          {target.patientName && (
            <div><span style={labelStyle}>Patient</span><p style={valueStyle}>{target.patientName}</p></div>
          )}
          {target.doctorName && (
            <div><span style={labelStyle}>Doctor</span><p style={valueStyle}>{target.doctorName}</p></div>
          )}
          <div><span style={labelStyle}>Current Date/Time</span><p style={valueStyle}>{formatDateTime(parseServerDate(target.appointmentTime))}</p></div>
          {target.status && (
            <div><span style={labelStyle}>Status</span><p style={valueStyle}>{target.status}</p></div>
          )}
          {target.reason && (
            <div style={{ gridColumn: '1 / -1' }}><span style={labelStyle}>Reason</span><p style={valueStyle}>{target.reason}</p></div>
          )}
        </div>

        {/* Week navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', gap: '8px' }}>
          <button onClick={() => setWeekOffset(o => Math.max(0, o - 1))} disabled={weekOffset === 0} style={navButton(weekOffset === 0)}>
            Previous Week
          </button>
          <h4 style={{ margin: 0, color: '#eaf5ff' }}>
            Week of {days[0].getMonth() + 1}/{days[0].getDate()} - {days[6].getMonth() + 1}/{days[6].getDate()}
          </h4>
          <button onClick={() => setWeekOffset(o => Math.min(MAX_WEEK_OFFSET, o + 1))} disabled={weekOffset === MAX_WEEK_OFFSET} style={navButton(weekOffset === MAX_WEEK_OFFSET)}>
            Next Week
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#b4cce2' }}>Loading availability...</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', border: cellBorder }}>
              <thead>
                <tr style={{ backgroundColor: 'rgba(9, 35, 55, 0.82)' }}>
                  {days.map(day => (
                    <th key={day.toDateString()} style={{ padding: '10px 6px', textAlign: 'center', border: cellBorder, color: '#42b5f5', fontSize: '12px', fontWeight: 'bold' }}>
                      <div>{day.toLocaleDateString('en-US', { weekday: 'short' })}</div>
                      <div style={{ fontSize: '10px', marginTop: '4px' }}>
                        {String(day.getMonth() + 1).padStart(2, '0')}/{String(day.getDate()).padStart(2, '0')}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  {days.map(day => (
                    <td key={day.toDateString()} style={{ border: cellBorder, padding: '4px', verticalAlign: 'top' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {OFFICE_HOUR_SLOTS.map((label, i) => {
                          const cell = new Date(day.getFullYear(), day.getMonth(), day.getDate(), WORKDAY_FIRST_SLOT_HOUR + i);
                          const key = localSlotKey(cell);
                          const state = rescheduleSlotState(cell, { now, currentKey, statusByKey, conflictKeys });
                          const isPast = state === 'past';
                          const isCurrent = state === 'current';
                          const isSelected = key === selectedKey;
                          const isAvailable = state === 'available';

                          return (
                            <div
                              key={label}
                              title={isCurrent ? 'Current appointment time' : undefined}
                              onClick={() => { if (isAvailable && !saving) setSelectedKey(key); }}
                              style={{
                                padding: '4px 6px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                textAlign: 'center',
                                fontWeight: '500',
                                color: 'white',
                                cursor: isAvailable ? 'pointer' : 'default',
                                opacity: isPast ? 0.5 : 1,
                                outline: isSelected ? '2px solid #ffffff' : 'none',
                                backgroundColor: isPast ? '#2a2a2a' :
                                  isCurrent ? '#42b5f5' :
                                  isSelected ? '#f0a020' :
                                  isAvailable ? '#28a745' :
                                  '#6c757d'
                              }}
                            >
                              {label}
                            </div>
                          );
                        })}
                      </div>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        <div style={{ marginTop: '12px', display: 'flex', gap: '16px', fontSize: '12px', flexWrap: 'wrap' }}>
          {[['#42b5f5', 'Current'], ['#f0a020', 'Selected'], ['#28a745', 'Available'], ['#6c757d', 'Unavailable']].map(([color, text]) => (
            <div key={text} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '12px', height: '12px', backgroundColor: color, borderRadius: '2px' }}></div>
              <span style={{ color: '#b4cce2' }}>{text}</span>
            </div>
          ))}
        </div>

        {error && (
          <div style={{ color: '#ff90ab', fontSize: '13px', marginTop: '12px' }}>{error}</div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
          <span style={{ color: '#b4cce2', fontSize: '14px' }}>
            {selectedKey ? `New time: ${formatDateTime(new Date(selectedKey))}` : 'Select an available slot'}
          </span>
          <button
            onClick={handleConfirm}
            disabled={!selectedKey || saving}
            style={{
              padding: '8px 16px',
              background: !selectedKey || saving ? '#94a3b8' : '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: !selectedKey || saving ? 'not-allowed' : 'pointer'
            }}
          >
            {saving ? 'Rescheduling...' : 'Confirm Reschedule'}
          </button>
        </div>
      </div>
    </div>
  );
}
