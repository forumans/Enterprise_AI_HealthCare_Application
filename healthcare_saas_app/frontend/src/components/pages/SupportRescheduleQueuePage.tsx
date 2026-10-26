/**
 * Support Reschedule Queue Page
 * "Needs Reschedule": upcoming appointments whose hour the doctor has since blocked. They stay booked
 * until support staff contact the patient and reschedule or cancel them. Appointments in the next
 * 24 hours are marked Urgent and listed first.
 */

import React, { useEffect, useState } from "react";
import { api } from "../../api";
import { useClinicTimeZone } from "../../contexts/ClinicTimeZoneContext";
import { parseErrorMessage } from "../../utils";
import type { RescheduleQueueRow } from "../../types";
import { RescheduleAppointmentModal, formatDateTime, type RescheduleTarget } from "../common/RescheduleAppointmentModal";

/** Fired on `window` when the queue changes, so the menu badge refreshes. */
export const RESCHEDULE_QUEUE_CHANGED_EVENT = "hc:reschedule-queue-changed";

const cellStyle: React.CSSProperties = { padding: '12px', color: '#eef8ff', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' };
const headStyle: React.CSSProperties = { padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' };
const actionButton = (color: string, busy = false): React.CSSProperties => ({
  background: busy ? '#94a3b8' : color,
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  padding: '6px 12px',
  fontSize: '12px',
  cursor: busy ? 'not-allowed' : 'pointer',
  fontWeight: '500'
});

interface SupportRescheduleQueuePageProps {
  auth: any;
}

export function SupportRescheduleQueuePage({ auth }: SupportRescheduleQueuePageProps) {
  const token: string = auth.session.accessToken;
  const timeZone = useClinicTimeZone();
  const [rows, setRows] = useState<RescheduleQueueRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<RescheduleTarget | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await api.getRescheduleQueue(token));
    } catch (err) {
      setError(parseErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [token]);

  const afterChange = async () => {
    await load();
    window.dispatchEvent(new CustomEvent(RESCHEDULE_QUEUE_CHANGED_EVENT));
  };

  const handleCancel = async (row: RescheduleQueueRow) => {
    if (!window.confirm(`Cancel ${row.patient_name}'s appointment with ${row.doctor_name} on ${formatDateTime(row.appointment_time, timeZone)}?`)) {
      return;
    }
    setBusyId(row.id);
    try {
      await api.cancelAppointment(token, row.id);
      await afterChange();
      alert("Appointment cancelled successfully");
    } catch (err) {
      alert(parseErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  // Doctors that have queued appointments, for the filter
  const doctors = Array.from(new Map(rows.map(r => [r.doctor_id, r.doctor_name])).entries()).sort((a, b) => a[1].localeCompare(b[1]));
  const shown = doctorId ? rows.filter(r => r.doctor_id === doctorId) : rows;

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Needs Reschedule</h2>
      <p style={{ color: '#b4cce2', margin: 0 }}>
        Appointments in hours the doctor has blocked. They stay booked until you reschedule or cancel them with the patient.
      </p>

      <div className="card" style={{ padding: '16px' }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}>
          <label htmlFor="queue-doctor" style={{ color: '#d6ebfb', fontWeight: 700 }}>Doctor</label>
          <select
            id="queue-doctor"
            value={doctorId}
            onChange={e => setDoctorId(e.target.value)}
            style={{ padding: '8px', borderRadius: '8px', backgroundColor: 'rgba(9, 35, 55, 0.82)', color: '#eef8ff', border: '1px solid rgba(136, 194, 227, 0.36)' }}
          >
            <option value="">All doctors</option>
            {doctors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        </div>

        {error && <p role="alert" style={{ color: '#ff90ab' }}>{error}</p>}
        {loading ? (
          <p style={{ color: '#b4cce2', textAlign: 'center', padding: '20px' }}>Loading...</p>
        ) : shown.length === 0 ? (
          <p style={{ color: '#b4cce2', textAlign: 'center', padding: '20px' }}>No appointments need rescheduling.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
              <thead>
                <tr style={{ backgroundColor: 'rgba(9, 35, 55, 0.82)' }}>
                  <th style={headStyle}>Date &amp; Time</th>
                  <th style={headStyle}>Doctor</th>
                  <th style={headStyle}>Patient</th>
                  <th style={headStyle}>Phone</th>
                  <th style={headStyle}>Email</th>
                  <th style={headStyle}>Block Reason</th>
                  <th style={headStyle}>Status</th>
                  <th style={{ ...headStyle, textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {shown.map(row => (
                  <tr key={row.id} data-appointment-id={row.id} style={{ backgroundColor: row.urgent ? 'rgba(220, 53, 69, 0.18)' : 'rgba(9, 32, 52, 0.82)' }}>
                    <td style={cellStyle}>
                      {row.urgent && (
                        <span style={{ background: '#dc3545', color: 'white', borderRadius: '4px', padding: '2px 6px', fontSize: '12px', marginRight: '8px' }}>Urgent</span>
                      )}
                      {formatDateTime(row.appointment_time, timeZone)}
                    </td>
                    <td style={cellStyle}>{row.doctor_name}</td>
                    <td style={cellStyle}>{row.patient_name}</td>
                    <td style={cellStyle}>{row.patient_phone || '—'}</td>
                    <td style={cellStyle}>{row.patient_email || '—'}</td>
                    <td style={cellStyle}>{row.reason_label || '—'}</td>
                    <td style={cellStyle}>{row.status}</td>
                    <td style={{ ...cellStyle, textAlign: 'center', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
                        <button
                          onClick={() => setRescheduleTarget({
                            id: row.id,
                            doctorId: row.doctor_id,
                            appointmentTime: row.appointment_time,
                            doctorName: row.doctor_name,
                            patientName: row.patient_name,
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

      {rescheduleTarget && (
        <RescheduleAppointmentModal
          target={rescheduleTarget}
          accessToken={token}
          onClose={() => setRescheduleTarget(null)}
          onRescheduled={afterChange}
        />
      )}
    </section>
  );
}
