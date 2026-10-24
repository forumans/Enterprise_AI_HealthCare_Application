/**
 * Reschedule Appointment Modal
 * Shared by the patient (My Appointments), doctor (Today's / Weekly Appointments) and
 * support staff screens. Shows the appointment's details read-only and the same doctor's
 * availability calendar; only the date/time changes - doctor, patient, reason and status are kept.
 */

import React, { useState } from "react";
import { api } from "../../api";
import { parseServerDate, parseErrorMessage } from "../../utils";
import { SlotPickerCalendar } from "./SlotPickerCalendar";

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

const labelStyle: React.CSSProperties = { fontSize: '12px', fontWeight: '700', color: '#42b5f5', textTransform: 'uppercase', display: 'block', marginBottom: '4px' };
const valueStyle: React.CSSProperties = { margin: 0, fontSize: '14px', color: '#eef8ff' };

export const formatDateTime = (date: Date) =>
  date.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });

export function RescheduleAppointmentModal({ target, accessToken, onClose, onRescheduled, conflictingTimes = [] }: RescheduleAppointmentModalProps) {
  const [error, setError] = useState("");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

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

        <SlotPickerCalendar
          doctorId={target.doctorId}
          accessToken={accessToken}
          selectedKey={selectedKey}
          onSelect={setSelectedKey}
          currentTime={target.appointmentTime}
          conflictingTimes={conflictingTimes}
          disabled={saving}
        />

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
