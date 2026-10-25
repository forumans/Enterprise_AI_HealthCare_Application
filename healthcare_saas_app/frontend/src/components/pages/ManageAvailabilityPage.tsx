/**
 * Manage Availability Page Component
 * Allows doctors to manage their available time slots for appointments
 * Follows the same patterns as the original DoctorManageAvailabilityPanel
 */

import React, { useState, useEffect } from "react";
import { api } from "../../api";
import { useAuthContext } from "../../contexts/AuthContext";
import { useClinicTimeZone } from "../../contexts/ClinicTimeZoneContext";
import {
  OFFICE_HOUR_SLOTS, addDays, cellKey, clinicSlotKey, clinicToday, dayKey, parseErrorMessage,
  parseServerDate, sameDay, weekdayOf, zonedParts, zonedTimeToDate,
} from "../../utils";
import { ClinicTimeNote } from "../common/ClinicTimeNote";
import type { SessionState } from "../../types/app";

/** Slots can be changed up to 30 days ahead, so the grid stops at the fifth week (same as the booking grids). */
const MAX_WEEK_OFFSET = 4;

export interface AvailabilityDoctor {
  id: string;
  name: string;
  specialty?: string | null;
  license_number?: string | null;
}

interface ManageAvailabilityPageProps {
  auth: any;
  /** Doctor to manage on behalf of (support staff). Omitted: the logged-in doctor. */
  doctor?: AvailabilityDoctor;
}

// DoctorDetails component (same as in TodayAppointmentsPage)
function DoctorDetails({ session, auth }: { session: SessionState; auth: any }) {
  const [doctorData, setDoctorData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadDoctorData = async () => {
      try {
        // Use /doctor/profile endpoint to get complete doctor data (includes phone)
        const data = await api.getDoctorProfile(session.accessToken);
        setDoctorData(data);
      } catch (err) {
        console.error("Failed to load doctor data:", err);
      } finally {
        setLoading(false);
      }
    };

    if (session.accessToken) {
      loadDoctorData();
    }
  }, [session.accessToken]);

  if (loading) {
    return <div>Loading doctor information...</div>;
  }

  return (
    <div className="card" style={{ padding: '20px' }}>
      <h3>Doctor Details</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <div>
          <strong>Name:</strong> {doctorData?.full_name || doctorData?.name || 'N/A'}
        </div>
        <div>
          <strong>Phone:</strong> {doctorData?.phone || 'N/A'}
        </div>
        <div>
          <strong>Specialization:</strong> {doctorData?.specialty || 'N/A'}
        </div>
        <div>
          <strong>License Number:</strong> {doctorData?.license_number || 'N/A'}
        </div>
      </div>
    </div>
  );
}

export function ManageAvailabilityPage({ auth, doctor }: ManageAvailabilityPageProps) {
  const [weekOffset, setWeekOffset] = useState(0);
  const [availability, setAvailability] = useState<Array<{ slot_time: string; status: "AVAILABLE" | "BOOKED" | "BLOCKED" }>>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");
  const [currentDoctor, setCurrentDoctor] = useState<any>(null);
  const timeZone = useClinicTimeZone();

  useEffect(() => {
    if (message && messageType === "success") {
      const timer = setTimeout(() => {
        setMessage("");
        setMessageType("");
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [message, messageType]);

  useEffect(() => {
    if (auth.session.accessToken) {
      loadAvailability();
    }
  }, [weekOffset, auth.session.accessToken, doctor?.id]);

  async function loadAvailability() {
    if (!auth.session.accessToken) {
      setMessage("Authentication required");
      setMessageType("error");
      return;
    }
    
    setLoading(true);
    try {
      // The doctor being managed: given by support staff, or the logged-in doctor
      const target = doctor ?? await api.getDoctorMe(auth.session.accessToken);
      setCurrentDoctor(target);
      
      // Fetch all availability for that doctor
      const availabilityResponse = await api.listAllDoctorAvailability(target.id, auth.session.accessToken);
      setAvailability(availabilityResponse);
    } catch (error) {
      console.error("Failed to load availability:", error);
      setMessage(parseErrorMessage(error));
      setMessageType("error");
    } finally {
      setLoading(false);
    }
  }

  // Seven clinic-calendar days starting today (clinic time), moved by weekOffset
  const now = new Date();
  const today = clinicToday(timeZone, now);
  const currentHour = zonedParts(now, timeZone).hour;
  const weekDays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const calendar: Array<{ day: string; date: number; month: number; year: number; isWeekend: boolean; isPast: boolean }> = [];

  for (let i = 0; i < 7; i++) {
    const current = addDays(today, weekOffset * 7 + i);
    const weekday = weekdayOf(current);
    calendar.push({
      day: weekDays[weekday],
      date: current.day,
      month: current.month,
      year: current.year,
      isWeekend: weekday === 0 || weekday === 6,
      isPast: dayKey(current) < dayKey(today)
    });
  }

  const timeSlots = OFFICE_HOUR_SLOTS;

  async function toggleSlot(date: number, month: number, year: number, timeSlot: string) {
    // Convert to 24-hour format
    const [time, period] = timeSlot.split(" ");
    let hour = parseInt(time);
    if (period === "PM" && hour !== 12) hour += 12;
    if (period === "AM" && hour === 12) hour = 0;
    
    // Build the UTC ISO string the backend expects from the clinic-time cell
    const day = { year, month, day: date };
    const utcSlotString = zonedTimeToDate(day, hour, timeZone).toISOString();

    // Clinic-time key used only for matching calendar cells against stored UTC slot times
    const cellTimeString = cellKey(day, hour);
    const existingSlot = availability.find(a => clinicSlotKey(parseServerDate(a.slot_time), timeZone) === cellTimeString);
    
    try {
      if (existingSlot?.status === "BLOCKED") {
        // Unblock the slot (unblocking clears the block reason, so there is nothing to ask for)
        if (!window.confirm("Unblock this slot? Patients will be able to book it again.")) {
          return;
        }
        const response = await api.upsertDoctorAvailability(currentDoctor.id, utcSlotString, true, auth.session.accessToken);
        setMessage("Slot unblocked successfully");
        setMessageType("success");
      } else if (existingSlot?.status === "AVAILABLE") {
        // Block the available slot
        const blockReason = window.prompt("Enter reason for blocking this slot:");
        if (blockReason === null) {
          // User cancelled
          return;
        }
        const response = await api.upsertDoctorAvailability(currentDoctor.id, utcSlotString, false, auth.session.accessToken, blockReason);
        setMessage("Slot blocked successfully");
        setMessageType("success");
      } else {
        // Add the slot as available
        const response = await api.upsertDoctorAvailability(currentDoctor.id, utcSlotString, true, auth.session.accessToken);
        setMessage("Slot added successfully");
        setMessageType("success");
      }
      
      // Refresh availability with a small delay to ensure backend processing
      await new Promise(resolve => setTimeout(resolve, 500));
      await loadAvailability();
    } catch (error) {
      console.error("Failed to update slot:", error);
      setMessage(parseErrorMessage(error));
      setMessageType("error");
    }
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {!doctor && <h2>Manage Availability</h2>}
      
      {doctor ? (
        <div className="card" style={{ padding: '20px' }}>
          <h3>Doctor Details</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div><strong>Name:</strong> {doctor.name}</div>
            <div><strong>Specialization:</strong> {doctor.specialty || 'N/A'}</div>
            <div><strong>License Number:</strong> {doctor.license_number || 'N/A'}</div>
          </div>
        </div>
      ) : (
        <DoctorDetails session={auth.session} auth={auth} />
      )}
      
      <div className="card" style={{ padding: '20px' }}>
        <div className="calendar-nav" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <button 
            onClick={() => setWeekOffset(Math.max(0, weekOffset - 1))} 
            disabled={weekOffset === 0}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              fontWeight: '500',
              backgroundColor: weekOffset === 0 ? '#94a3b8' : '#42b5f5',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: weekOffset === 0 ? 'not-allowed' : 'pointer'
            }}
          >
            Previous Week
          </button>
          <span style={{ fontSize: '16px', fontWeight: '500', color: '#eef8ff', textAlign: 'center' }}>
            Week of {calendar[0]?.month}/{calendar[0]?.date} - {calendar[6]?.month}/{calendar[6]?.date}
            <ClinicTimeNote />
          </span>
          <button 
            onClick={() => setWeekOffset(Math.min(MAX_WEEK_OFFSET, weekOffset + 1))}
            disabled={weekOffset === MAX_WEEK_OFFSET}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              fontWeight: '500',
              backgroundColor: weekOffset === MAX_WEEK_OFFSET ? '#94a3b8' : '#42b5f5',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: weekOffset === MAX_WEEK_OFFSET ? 'not-allowed' : 'pointer'
            }}
          >
            Next Week
          </button>
        </div>
        
        {message && (
          <div style={{ 
            padding: '12px', 
            margin: '16px 0', 
            backgroundColor: messageType === "error" ? 'rgba(255, 144, 171, 0.1)' : 'rgba(66, 181, 245, 0.1)', 
            color: messageType === "error" ? '#ff90ab' : '#42b5f5', 
            borderRadius: '8px',
            textAlign: 'center',
            border: messageType === "error" ? '1px solid #ff90ab' : '1px solid #42b5f5'
          }}>
            {message}
          </div>
        )}
        
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#b4cce2' }}>
            Loading availability...
          </div>
        ) : (
          <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '14px' }}>
            <thead>
              <tr>
                <th style={{ padding: '8px', textAlign: 'center', minWidth: '80px', backgroundColor: '#1e293b', color: '#eef8ff' }}>Time</th>
                {calendar.map(col => (
                  <th key={col.day} style={{ padding: '8px', textAlign: 'center', minWidth: '120px', backgroundColor: '#1e293b', color: '#eef8ff' }}>
                    <div style={{ fontWeight: '600' }}>{col.day}</div>
                    <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                      {String(col.month).padStart(2, '0')}/{String(col.date).padStart(2, '0')}/{col.year}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {timeSlots.map((slot) => (
                <tr key={slot}>
                  <td style={{ padding: '8px', textAlign: 'center', fontWeight: 'bold', minWidth: '80px', backgroundColor: '#1e293b', color: '#eef8ff' }}>{slot}</td>
                  {calendar.map((col, colIdx) => {
                    const isSlotPast = col.isPast || (sameDay({ year: col.year, month: col.month, day: col.date }, today) && (() => {
                      const [time, period] = slot.split(" ");
                      let hour = parseInt(time);
                      if (period === "PM" && hour !== 12) hour += 12;
                      if (period === "AM" && hour === 12) hour = 0;
                      return hour <= currentHour;
                    })());
                    
                    const isoString = `${col.year.toString().padStart(4, '0')}-${(col.month).toString().padStart(2, '0')}-${col.date.toString().padStart(2, '0')}T${(() => {
                      const [time, period] = slot.split(" ");
                      let hour = parseInt(time);
                      if (period === "PM" && hour !== 12) hour += 12;
                      if (period === "AM" && hour === 12) hour = 0;
                      return hour.toString().padStart(2, '0');
                    })()}:00:00`;
                    
                    const slotAvailability = availability.find(a => clinicSlotKey(parseServerDate(a.slot_time), timeZone) === isoString);
                    const status = slotAvailability?.status || "EMPTY";
                    
                    return (
                      <td key={colIdx} style={{ padding: '8px', textAlign: 'center', minWidth: '120px', verticalAlign: 'top' }}>
                        {!isSlotPast && (
                          <button
                            className={`time-slot ${
                              status === "BOOKED" ? "patient-booked-slot" : 
                              status === "BLOCKED" ? "booked-slot" : 
                              status === "EMPTY" ? "empty-slot" :
                              "available-slot"
                            }`}
                            onClick={() => status !== "BOOKED" && toggleSlot(col.date, col.month, col.year, slot)}
                            disabled={status === "BOOKED"}
                            style={{
                              ...(status === "EMPTY" && {
                                border: '2px dashed #42b5f5',
                                backgroundColor: 'rgba(66, 181, 245, 0.1)',
                                color: '#42b5f5',
                                fontSize: '12px',
                                fontWeight: '500',
                                padding: '8px 4px',
                                minHeight: '40px',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                borderRadius: '4px'
                              }),
                              ...(status === "AVAILABLE" && {
                                backgroundColor: 'rgba(73, 215, 194, 0.2)',
                                border: '2px solid #49d7c2',
                                color: '#49d7c2',
                                fontSize: '12px',
                                fontWeight: '500',
                                padding: '8px 4px',
                                minHeight: '40px',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                borderRadius: '4px'
                              }),
                              ...(status === "BLOCKED" && {
                                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                                border: '2px solid #ef4444',
                                color: '#ef4444',
                                fontSize: '12px',
                                fontWeight: '500',
                                padding: '8px 4px',
                                minHeight: '40px',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                borderRadius: '4px'
                              }),
                              ...(status === "BOOKED" && {
                                backgroundColor: 'rgba(251, 146, 60, 0.2)',
                                border: '2px solid #fb923c',
                                color: '#fb923c',
                                fontSize: '12px',
                                fontWeight: '500',
                                padding: '8px 4px',
                                minHeight: '40px',
                                cursor: 'not-allowed',
                                transition: 'all 0.2s ease',
                                borderRadius: '4px'
                              })
                            }}
                            onMouseEnter={(e) => {
                              if (status === "EMPTY") {
                                e.currentTarget.style.backgroundColor = 'rgba(66, 181, 245, 0.2)';
                                e.currentTarget.style.transform = 'scale(1.02)';
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (status === "EMPTY") {
                                e.currentTarget.style.backgroundColor = 'rgba(66, 181, 245, 0.1)';
                                e.currentTarget.style.transform = 'scale(1)';
                              }
                            }}
                          >
                            {status === "BOOKED" ? "Patient Booked" : 
                             status === "BLOCKED" ? "Blocked" : 
                             status === "EMPTY" ? "Click to Add" : 
                             "Available"}
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
