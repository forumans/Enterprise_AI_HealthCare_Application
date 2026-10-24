/**
 * Slot Picker Calendar
 * Week-by-week grid of a doctor's hourly slots (next 5 weeks) for picking an open time.
 * Used by the reschedule modal and the support staff booking screen.
 */

import React, { useEffect, useState } from "react";
import { api } from "../../api";
import { OFFICE_HOUR_SLOTS, WORKDAY_FIRST_SLOT_HOUR, localSlotKey, parseServerDate, rescheduleSlotState } from "../../utils";

interface SlotPickerCalendarProps {
  doctorId: string;
  accessToken: string;
  /** Local cell key ("2026-10-22T23:00:00") of the picked slot, or null. */
  selectedKey: string | null;
  onSelect: (key: string) => void;
  /** The appointment's current time when rescheduling (API timestamp); shown as "Current". */
  currentTime?: string;
  /** Other active appointment times of the same patient (API timestamps); shown as unavailable. */
  conflictingTimes?: string[];
  disabled?: boolean;
  /** Change to reload the doctor's availability (e.g. after a booking). */
  refreshKey?: number;
}

const MAX_WEEK_OFFSET = 4;
const cellBorder = '1px solid rgba(136, 194, 227, 0.36)';

export function SlotPickerCalendar({ doctorId, accessToken, selectedKey, onSelect, currentTime, conflictingTimes = [], disabled = false, refreshKey = 0 }: SlotPickerCalendarProps) {
  const [availability, setAvailability] = useState<Array<{ slot_time: string; status: "AVAILABLE" | "BOOKED" | "BLOCKED" }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [weekOffset, setWeekOffset] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError("");
    api.listAllDoctorAvailability(doctorId, accessToken)
      .then(setAvailability)
      .catch((err) => {
        console.error("Failed to load doctor availability:", err);
        setError("Failed to load the doctor's availability.");
      })
      .finally(() => setLoading(false));
  }, [doctorId, accessToken, refreshKey]);

  const currentKey = currentTime ? localSlotKey(parseServerDate(currentTime)) : "";
  const statusByKey = new Map(availability.map(a => [localSlotKey(parseServerDate(a.slot_time)), a.status]));
  const conflictKeys = new Set(conflictingTimes.map(t => localSlotKey(parseServerDate(t))));

  const now = new Date();
  const startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() + weekOffset * 7);
  const days = Array.from({ length: 7 }, (_, i) => new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate() + i));

  const navButton = (isDisabled: boolean): React.CSSProperties => ({
    padding: '8px 16px',
    background: isDisabled ? '#94a3b8' : '#42b5f5',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    fontSize: '14px'
  });

  const legend: Array<[string, string]> = [
    ...(currentTime ? [['#42b5f5', 'Current'] as [string, string]] : []),
    ['#f0a020', 'Selected'],
    ['#28a745', 'Available'],
    ['#6c757d', 'Unavailable'],
  ];

  return (
    <div>
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
                        const isSelected = key === selectedKey;
                        const isAvailable = state === 'available';

                        return (
                          <div
                            key={label}
                            title={state === 'current' ? 'Current appointment time' : undefined}
                            onClick={() => { if (isAvailable && !disabled) onSelect(key); }}
                            style={{
                              padding: '4px 6px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              textAlign: 'center',
                              fontWeight: '500',
                              color: 'white',
                              cursor: isAvailable && !disabled ? 'pointer' : 'default',
                              opacity: state === 'past' ? 0.5 : 1,
                              outline: isSelected ? '2px solid #ffffff' : 'none',
                              backgroundColor: state === 'past' ? '#2a2a2a' :
                                state === 'current' ? '#42b5f5' :
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
        {legend.map(([color, text]) => (
          <div key={text} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '12px', height: '12px', backgroundColor: color, borderRadius: '2px' }}></div>
            <span style={{ color: '#b4cce2' }}>{text}</span>
          </div>
        ))}
      </div>

      {error && (
        <div style={{ color: '#ff90ab', fontSize: '13px', marginTop: '12px' }}>{error}</div>
      )}
    </div>
  );
}
