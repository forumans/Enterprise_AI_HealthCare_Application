/**
 * Manage Availability Page Component
 * Allows doctors to manage their available time slots for appointments
 * Follows the same patterns as the original DoctorManageAvailabilityPanel
 */

import React, { useState, useEffect } from "react";
import { api } from "../../api";
import { useAuthContext } from "../../contexts/AuthContext";
import { parseErrorMessage } from "../../utils";
import type { SessionState } from "../../types/app";

interface ManageAvailabilityPageProps {
  auth: any;
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
        console.log('🔍 DEBUG: Doctor data from /doctor/profile:', data);
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

export function ManageAvailabilityPage({ auth }: ManageAvailabilityPageProps) {
  const [weekOffset, setWeekOffset] = useState(0);
  const [availability, setAvailability] = useState<Array<{ slot_time: string; status: "AVAILABLE" | "BOOKED" | "BLOCKED" }>>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"success" | "error" | "">("");
  const [currentDoctor, setCurrentDoctor] = useState<any>(null);

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
  }, [weekOffset, auth.session.accessToken]);

  async function loadAvailability() {
    if (!auth.session.accessToken) {
      setMessage("Authentication required");
      setMessageType("error");
      return;
    }
    
    setLoading(true);
    try {
      // Get current doctor's information
      const doctor = await api.getDoctorMe(auth.session.accessToken);
      setCurrentDoctor(doctor);
      
      // Fetch all availability for the current doctor
      const availabilityResponse = await api.listAllDoctorAvailability(doctor.id, auth.session.accessToken);
      setAvailability(availabilityResponse);
    } catch (error) {
      console.error("Failed to load availability:", error);
      setMessage(parseErrorMessage(error));
      setMessageType("error");
    } finally {
      setLoading(false);
    }
  }

  // Generate calendar similar to PatientAppointmentsPanel
  const today = new Date();
  const weekDays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const calendar: Array<{ day: string; date: number; month: number; year: number; isWeekend: boolean; isPast: boolean }> = [];
  let offset = weekOffset * 7;
  const startOfWeek = new Date(today);
  startOfWeek.setDate(today.getDate() - today.getDay() + 1 + offset);

  for (let i = 0; i < 7; i++) {
    const current = new Date(startOfWeek);
    current.setDate(startOfWeek.getDate() + i);
    calendar.push({
      day: weekDays[i],
      date: current.getDate(),
      month: current.getMonth() + 1,
      year: current.getFullYear(),
      isWeekend: i >= 5,  // Saturday=5, Sunday=6
      isPast: current < today && current.toDateString() !== today.toDateString()
    });
  }

  const timeSlots = [
    "8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"
  ];

  async function toggleSlot(date: number, month: number, year: number, timeSlot: string) {
    // Convert to 24-hour format
    const [time, period] = timeSlot.split(" ");
    let hour = parseInt(time);
    if (period === "PM" && hour !== 12) hour += 12;
    if (period === "AM" && hour === 12) hour = 0;
    
    // Create local datetime and convert to UTC
    const localDateTime = new Date(year, month - 1, date, hour, 0, 0);
    const localTimeString = `${year.toString().padStart(4, '0')}-${(month).toString().padStart(2, '0')}-${date.toString().padStart(2, '0')}T${hour.toString().padStart(2, '0')}:00:00`;
    
    // Try to find the slot in different formats
    const existingSlot = availability.find(a => {
      // Normalize both to local time format for comparison
      const slotTime = new Date(a.slot_time);
      const slotTimeString = `${slotTime.getFullYear().toString().padStart(4, '0')}-${(slotTime.getMonth() + 1).toString().padStart(2, '0')}-${slotTime.getDate().toString().padStart(2, '0')}T${slotTime.getHours().toString().padStart(2, '0')}:00:00`;
      return slotTimeString === localTimeString;
    });
    
    try {
      if (existingSlot?.status === "BLOCKED") {
        // Unblock the slot
        const blockReason = window.prompt("Enter reason for unblocking this slot:");
        if (blockReason === null) {
          // User cancelled
          return;
        }
        const response = await api.upsertDoctorAvailability(currentDoctor.id, localTimeString, true, auth.session.accessToken, blockReason);
        setMessage("Slot unblocked successfully");
        setMessageType("success");
      } else if (existingSlot?.status === "AVAILABLE") {
        // Block the available slot
        const blockReason = window.prompt("Enter reason for blocking this slot:");
        if (blockReason === null) {
          // User cancelled
          return;
        }
        const response = await api.upsertDoctorAvailability(currentDoctor.id, localTimeString, false, auth.session.accessToken, blockReason);
        setMessage("Slot blocked successfully");
        setMessageType("success");
      } else {
        // Add the slot as available
        const response = await api.upsertDoctorAvailability(currentDoctor.id, localTimeString, true, auth.session.accessToken);
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
      <h2>Manage Availability</h2>
      
      <DoctorDetails session={auth.session} auth={auth} />
      
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
          <span style={{ fontSize: '16px', fontWeight: '500', color: '#eef8ff' }}>
            Week of {calendar[0]?.month}/{calendar[0]?.date} - {calendar[6]?.month}/{calendar[6]?.date}
          </span>
          <button 
            onClick={() => setWeekOffset(weekOffset + 1)}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              fontWeight: '500',
              backgroundColor: '#42b5f5',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
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
                    const isSlotPast = col.isPast || (col.date === today.getDate() && col.month === today.getMonth() + 1 && col.year === today.getFullYear() && (() => {
                      const [time, period] = slot.split(" ");
                      let hour = parseInt(time);
                      if (period === "PM" && hour !== 12) hour += 12;
                      if (period === "AM" && hour === 12) hour = 0;
                      return hour <= today.getHours();
                    })());
                    
                    const isoString = `${col.year.toString().padStart(4, '0')}-${(col.month).toString().padStart(2, '0')}-${col.date.toString().padStart(2, '0')}T${(() => {
                      const [time, period] = slot.split(" ");
                      let hour = parseInt(time);
                      if (period === "PM" && hour !== 12) hour += 12;
                      if (period === "AM" && hour === 12) hour = 0;
                      return hour.toString().padStart(2, '0');
                    })()}:00:00`;
                    
                    const slotAvailability = availability.find(a => {
                      // Normalize both to local time format for comparison
                      const slotTime = new Date(a.slot_time);
                      const slotTimeString = `${slotTime.getFullYear().toString().padStart(4, '0')}-${(slotTime.getMonth() + 1).toString().padStart(2, '0')}-${slotTime.getDate().toString().padStart(2, '0')}T${slotTime.getHours().toString().padStart(2, '0')}:00:00`;
                      return slotTimeString === isoString;
                    });
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
