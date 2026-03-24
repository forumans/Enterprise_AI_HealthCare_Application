/**
 * Patient Appointments Page Component
 * Displays patient's upcoming and past appointments
 * Includes calendar for booking new appointments
 * Shows appointment details and allows cancellation
 */

import React, { useState, useEffect } from "react";
import { api } from "../../api";
import type { SessionState, AppointmentRow } from "../../types/app";

interface PatientAppointmentsPageProps {
  auth: any;
  appointments: any;
  userData: any;
}

export function PatientAppointmentsPage({ auth, appointments, userData }: PatientAppointmentsPageProps) {
  const [loading, setLoading] = useState(false);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [patientDetails, setPatientDetails] = useState<any>(null);
  const [showAllPastAppointments, setShowAllPastAppointments] = useState(false);
  
  // Booking functionality state
  const [doctors, setDoctors] = useState<Array<{ id: string; name: string; specialty?: string; license_number?: string }>>([]);
  const [doctorsError, setDoctorsError] = useState("");
  const [weekOffset, setWeekOffset] = useState(0);
  const [selectedDoctorId, setSelectedDoctorId] = useState<string | null>(null);
  const [selectedDoctor, setSelectedDoctor] = useState<{ id: string; name: string; specialty?: string; license_number?: string } | null>(null);
  const [doctorAvailability, setDoctorAvailability] = useState<Array<{ slot_time: string; status: "AVAILABLE" | "BOOKED" | "BLOCKED" }>>([]);
  const [availabilityRefreshKey, setAvailabilityRefreshKey] = useState(0);
  const [bookedAppointments, setBookedAppointments] = useState<Array<{ slot_time: string }>>([]);
  const [appointmentReason, setAppointmentReason] = useState("");
  const [patientAppointments, setPatientAppointments] = useState<Array<any>>([]);

  useEffect(() => {
    // Load patient appointments and doctors
    const loadPatientData = async () => {
      setLoading(true);
      try {
        await appointments.loadPatientAppointments();
        await userData.loadPatientDetails();
        
        // Load doctors
        console.log('Loading doctors with token:', auth.session.accessToken ? 'Token present' : 'No token');
        api.listDoctors(auth.session.accessToken)
          .then(data => {
            console.log('Doctors loaded:', data);
            setDoctors(data);
          })
          .catch((error) => {
            console.error('Failed to load doctors:', error);
            setDoctorsError("Failed to load doctors.");
          });
          
        // Load patient appointments
        if (auth.session.accessToken) {
          api.listAllAppointments(auth.session.accessToken)
            .then(data => {
              setPatientAppointments(data);
            })
            .catch((err) => {
              console.error("Failed to load patient appointments:", err);
            });
        }
      } catch (error) {
        console.error("Failed to load patient data:", error);
      } finally {
        setLoading(false);
      }
    };

    if (auth.session.accessToken) {
      loadPatientData();
    }
  }, [auth.session.accessToken]);

  // Update selected doctor details when selection changes
  useEffect(() => {
    if (selectedDoctorId && doctors.length > 0) {
      const doctor = doctors.find(d => d.id === selectedDoctorId);
      setSelectedDoctor(doctor || null);
    }
  }, [selectedDoctorId, doctors]);

  // Load doctor availability when selection changes or refresh key changes
  useEffect(() => {
    if (selectedDoctorId && auth.session.accessToken) {
      api.listAllDoctorAvailability(selectedDoctorId, auth.session.accessToken)
        .then(data => {
          setDoctorAvailability(data);
        })
        .catch((err) => {
          console.error("Failed to load doctor availability:", err);
          setDoctorAvailability([]);
        });
    } else {
      setDoctorAvailability([]);
    }
  }, [selectedDoctorId, auth.session.accessToken, availabilityRefreshKey]);

  // Filter and sort upcoming and past appointments
  const upcomingAppointments = appointments.appointments
    .filter((apt: AppointmentRow) => new Date(apt.appointment_time) > new Date())
    .sort((a: AppointmentRow, b: AppointmentRow) => new Date(a.appointment_time).getTime() - new Date(b.appointment_time).getTime());

  const pastAppointments = appointments.appointments
    .filter((apt: AppointmentRow) => new Date(apt.appointment_time) <= new Date())
    .sort((a: AppointmentRow, b: AppointmentRow) => new Date(b.appointment_time).getTime() - new Date(a.appointment_time).getTime());

  // Limit past appointments to 5 unless "show more" is clicked
  const displayedPastAppointments = showAllPastAppointments 
    ? pastAppointments 
    : pastAppointments.slice(0, 5);

  // Format date for display
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Handle appointment cancellation
  const handleCancelAppointment = async (appointmentId: string) => {
    if (!window.confirm("Are you sure you want to cancel this appointment?")) {
      return;
    }

    setCancellingId(appointmentId);
    try {
      await api.cancelAppointment(auth.session.accessToken, appointmentId);
      
      // Refresh appointments
      await appointments.loadPatientAppointments();
      
      // Remove the cancelled appointment from bookedAppointments state
      const cancelledAppointment = patientAppointments.find(apt => apt.id === appointmentId);
      if (cancelledAppointment) {
        setBookedAppointments(prev => prev.filter(apt => apt.slot_time !== cancelledAppointment.appointment_time));
      }
      
      // Also refresh the local patientAppointments state
      api.listAllAppointments(auth.session.accessToken)
        .then(data => {
          setPatientAppointments(data);
        })
        .catch((err) => {
          console.error("Failed to refresh appointments:", err);
        });
      
      // Refresh the availability to show the slot as available again
      if (selectedDoctorId) {
        api.listAllDoctorAvailability(selectedDoctorId, auth.session.accessToken)
          .then(data => {
            setDoctorAvailability(data);
            // Force calendar re-render
            setAvailabilityRefreshKey(prev => prev + 1);
          })
          .catch((err) => {
            console.error("Failed to refresh availability:", err);
          });
      }
      
      alert("Appointment cancelled successfully");
    } catch (error) {
      console.error("Failed to cancel appointment:", error);
      alert("Failed to cancel appointment. Please try again.");
    } finally {
      setCancellingId(null);
    }
  };

  // Calendar functionality
  const today = new Date();
  const weekDays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const calendar: Array<{ day: string; date: number; month: number; year: number; isWeekend: boolean; isPast: boolean }> = [];
  
  const startDate = new Date(today);
  startDate.setDate(today.getDate() + weekOffset * 7);
  for (let i = 0; i < 7; i++) {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + i);
    const dayName = weekDays[date.getDay()];
    const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const isPast = date.getTime() < todayMidnight.getTime();
    calendar.push({ day: dayName, date: date.getDate(), month: date.getMonth() + 1, year: date.getFullYear(), isWeekend: date.getDay() === 0 || date.getDay() === 6, isPast });
  }

  const handlePrevWeek = () => setWeekOffset(o => Math.max(0, o - 1));
  const handleNextWeek = () => setWeekOffset(o => Math.min(4, o + 1));
  const timeSlots = ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"];
  const currentHour = today.getHours();

  const handleBookAppointment = async (isoString: string) => {
    if (!appointmentReason.trim()) {
      alert("Please provide a reason for the appointment.");
      return;
    }
    
    if (!selectedDoctorId) {
      alert("Please select a doctor.");
      return;
    }

    try {
      const result = await api.bookAppointment(auth.session.accessToken, {
        doctor_id: selectedDoctorId,
        slot: isoString,
        reason: appointmentReason.trim()
      });
      
      // Add to booked appointments state
      setBookedAppointments(prev => [...prev, { slot_time: isoString }]);
      // Clear the reason after successful booking
      setAppointmentReason("");
      
      // Refresh the availability to show the slot as booked
      api.listAllDoctorAvailability(selectedDoctorId, auth.session.accessToken)
        .then(data => {
          setDoctorAvailability(data);
        })
        .catch((err) => {
          console.error("Failed to refresh availability:", err);
        });
      
      // Refresh patient appointments - both local state and appointments hook
      api.listAllAppointments(auth.session.accessToken)
        .then(data => {
          setPatientAppointments(data);
        })
        .catch((err) => {
          console.error("Failed to refresh appointments:", err);
        });
      
      // Also refresh the appointments hook to update the My Appointments table
      await appointments.loadPatientAppointments();
        
      alert("Appointment booked successfully!");
    } catch (error) {
      console.error("Failed to book appointment:", error);
      alert("Failed to book appointment. Please try again.");
    }
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Schedule / Cancel Appointment</h2>
      
      {/* Patient Details */}
      {userData.patientDetails && (
        <div className="card" style={{ padding: '16px' }}>
          <h3 style={{ margin: '0 0 12px 0', color: '#dff2ff' }}>Patient Information</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Name</label>
              <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>{userData.patientDetails.full_name}</p>
            </div>
            <div>
              <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Phone</label>
              <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>{userData.patientDetails.phone}</p>
            </div>
            <div>
              <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Insurance</label>
              <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>
                {userData.patientDetails.insurance_provider && userData.patientDetails.insurance_policy_number 
                  ? `${userData.patientDetails.insurance_provider} - ${userData.patientDetails.insurance_policy_number}`
                  : userData.patientDetails.insurance_provider || userData.patientDetails.insurance_policy_number || 'Not specified'
                }
              </p>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="card" style={{ padding: '40px', textAlign: 'center', color: '#b4cce2' }}>
          Loading appointments...
        </div>
      ) : (
        <>
          {/* Booking Section */}
          <div className="card" style={{ padding: '16px' }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>Book New Appointment</h3>
            
            {/* Doctor Selection */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>
                Select Doctor <span style={{ color: '#ff90ab' }}>*</span>
              </label>
              <select
                value={selectedDoctorId || ''}
                onChange={(e) => setSelectedDoctorId(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '11px 12px',
                  borderRadius: '10px',
                  border: '1px solid rgba(136, 194, 227, 0.36)',
                  fontSize: '14px',
                  backgroundColor: 'rgba(9, 35, 55, 0.82)',
                  color: '#eef8ff'
                }}
              >
                <option value="" disabled>Select a doctor</option>
                {doctors.map(doctor => (
                  <option key={doctor.id} value={doctor.id}>
                    {doctor.name} - {doctor.specialty || 'General Practice'}
                  </option>
                ))}
              </select>
              {doctorsError && (
                <div style={{ color: '#ff90ab', fontSize: '12px', marginTop: '4px' }}>
                  {doctorsError}
                </div>
              )}
            </div>

            {/* Appointment Reason */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>
                Appointment Reason <span style={{ color: '#ff90ab' }}>*</span>
              </label>
              <textarea
                value={appointmentReason}
                onChange={(e) => setAppointmentReason(e.target.value)}
                placeholder="Please describe the reason for your appointment..."
                rows={3}
                style={{
                  width: '100%',
                  padding: '11px 12px',
                  borderRadius: '10px',
                  border: '1px solid rgba(136, 194, 227, 0.36)',
                  fontSize: '14px',
                  backgroundColor: 'rgba(9, 35, 55, 0.82)',
                  color: '#eef8ff',
                  resize: 'vertical'
                }}
              />
            </div>

            {/* Calendar */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <button
                  onClick={handlePrevWeek}
                  disabled={weekOffset === 0}
                  style={{
                    padding: '8px 16px',
                    background: weekOffset === 0 ? '#94a3b8' : '#42b5f5',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: weekOffset === 0 ? 'not-allowed' : 'pointer',
                    fontSize: '14px'
                  }}
                >
                  Previous Week
                </button>
                <h4 style={{ margin: 0, color: '#eaf5ff' }}>
                  Week of {calendar[0]?.month}/{calendar[0]?.date} - {calendar[6]?.month}/{calendar[6]?.date}
                </h4>
                <button
                  onClick={handleNextWeek}
                  disabled={weekOffset === 4}
                  style={{
                    padding: '8px 16px',
                    background: weekOffset === 4 ? '#94a3b8' : '#42b5f5',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: weekOffset === 4 ? 'not-allowed' : 'pointer',
                    fontSize: '14px'
                  }}
                >
                  Next Week
                </button>
              </div>

              <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                <thead>
                  <tr style={{ backgroundColor: 'rgba(9, 35, 55, 0.82)' }}>
                    {calendar.map(col => (
                      <th key={col.day} style={{ 
                        padding: '12px 8px', 
                        textAlign: 'center',
                        border: '1px solid rgba(136, 194, 227, 0.36)',
                        color: col.isPast ? '#94a3b8' : '#42b5f5',
                        fontSize: '12px',
                        fontWeight: 'bold'
                      }}>
                        <div>{col.day}</div>
                        <div style={{ fontSize: '10px', marginTop: '4px' }}>
                          {String(col.month).padStart(2, '0')}/{String(col.date).padStart(2, '0')}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    {calendar.map(col => (
                      <td key={col.day} style={{ 
                        border: '1px solid rgba(136, 194, 227, 0.36)',
                        padding: '4px',
                        verticalAlign: 'top',
                        backgroundColor: col.isPast ? 'rgba(148, 163, 184, 0.1)' : 'transparent'
                      }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {timeSlots.map(slot => {
                            const hour = parseInt(slot.split(":")[0]);
                            const isAm = slot.includes("AM");
                            const slotHour24 = isAm ? (hour === 12 ? 0 : hour) : (hour === 12 ? 12 : hour + 12);
                            const colDate = new Date(col.year, col.month - 1, col.date);
                            const isToday = colDate.toDateString() === today.toDateString();
                            const isSlotPast = col.isPast || (isToday && (slotHour24 <= currentHour));

                            // Check availability for this slot
                            const isoString = `${col.year.toString().padStart(4, '0')}-${(col.month).toString().padStart(2, '0')}-${col.date.toString().padStart(2, '0')}T${slotHour24.toString().padStart(2, '0')}:00:00`;
                            
                            // Check if this slot is already booked by the patient
                            const isPatientBooked = patientAppointments.some(apt => {
                              const aptTime = new Date(apt.appointment_time);
                              const slotTime = new Date(isoString);
                              const isSameTime = Math.abs(aptTime.getTime() - slotTime.getTime()) < 60000;
                              return isSameTime && (apt.status === 'SCHEDULED' || apt.status === 'CONFIRMED');
                            });
                            
                            // Check if this slot is available for the selected doctor
                            const slotAvailability = doctorAvailability.find(a => a.slot_time === isoString);
                            const isAvailable = !isPatientBooked && selectedDoctorId && slotAvailability && slotAvailability.status === "AVAILABLE";
                            
                            // Check if slot is booked
                            const isBooked = bookedAppointments.some(a => a.slot_time === isoString);

                            return (
                              <div
                                key={slot}
                                style={{
                                  padding: '4px 6px',
                                  borderRadius: '4px',
                                  fontSize: '11px',
                                  textAlign: 'center',
                                  cursor: isAvailable && !isSlotPast && !isBooked && !isPatientBooked ? 'pointer' : 'default',
                                  backgroundColor: isSlotPast ? '#2a2a2a' :
                                    isPatientBooked ? '#dc3545' :
                                    isBooked ? '#dc3545' :
                                    isAvailable ? '#28a745' :
                                    '#6c757d',
                                  color: 'white',
                                  fontWeight: '500',
                                  opacity: isSlotPast ? 0.5 : 1
                                }}
                                onClick={() => {
                                  if (isAvailable && !isSlotPast && selectedDoctorId && !isBooked && !isPatientBooked) {
                                    handleBookAppointment(isoString);
                                  }
                                }}
                              >
                                {slot}
                              </div>
                            );
                          })}
                        </div>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>

              <div style={{ marginTop: '16px', display: 'flex', gap: '16px', fontSize: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '12px', height: '12px', backgroundColor: '#28a745', borderRadius: '2px' }}></div>
                  <span style={{ color: '#b4cce2' }}>Available</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '12px', height: '12px', backgroundColor: '#dc3545', borderRadius: '2px' }}></div>
                  <span style={{ color: '#b4cce2' }}>Booked</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '12px', height: '12px', backgroundColor: '#6c757d', borderRadius: '2px' }}></div>
                  <span style={{ color: '#b4cce2' }}>Unavailable</span>
                </div>
              </div>
            </div>
          </div>

          {/* Existing Appointments */}
          <div className="card" style={{ padding: '16px' }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>
              My Appointments
            </h3>
            
            {/* Upcoming Appointments */}
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ margin: '0 0 12px 0', color: '#42b5f5', fontSize: '16px' }}>
                Upcoming ({upcomingAppointments.length})
              </h4>
              {upcomingAppointments.length === 0 ? (
                <p style={{ color: '#b4cce2', textAlign: 'center', padding: '20px' }}>
                  No upcoming appointments scheduled
                </p>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                    <thead>
                      <tr style={{ backgroundColor: 'rgba(9, 35, 55, 0.82)' }}>
                        <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Date & Time</th>
                        <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Doctor</th>
                        <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Notes</th>
                        <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Status</th>
                        <th style={{ padding: '12px', textAlign: 'center', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {upcomingAppointments.map((apt: AppointmentRow) => (
                        <tr key={apt.id} style={{ backgroundColor: 'rgba(9, 32, 52, 0.82)' }}>
                          <td style={{ padding: '12px', color: '#eef8ff', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                            {formatDate(apt.appointment_time)}
                          </td>
                          <td style={{ padding: '12px', color: '#eef8ff', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                            {apt.doctor_name || 'Doctor'}
                          </td>
                          <td style={{ padding: '12px', color: '#eef8ff', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                            {apt.notes || 'No notes'}
                          </td>
                          <td style={{ padding: '12px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                            <span style={{ 
                              color: apt.status === 'CANCELLED' ? '#ff90ab' : '#49d7c2',
                              fontWeight: '500',
                              fontSize: '14px'
                            }}>
                              {apt.status}
                            </span>
                          </td>
                          <td style={{ padding: '12px', textAlign: 'center', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                            {apt.status === 'SCHEDULED' && (
                              <button
                                onClick={() => handleCancelAppointment(apt.id)}
                                disabled={cancellingId === apt.id}
                                style={{
                                  background: cancellingId === apt.id ? '#94a3b8' : '#dc3545',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  padding: '6px 12px',
                                  fontSize: '12px',
                                  cursor: 'pointer',
                                  fontWeight: '500'
                                }}
                              >
                                {cancellingId === apt.id ? 'Cancelling...' : 'Cancel'}
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Past Appointments */}
            <div>
              <h4 style={{ margin: '0 0 12px 0', color: '#42b5f5', fontSize: '16px' }}>
                Past ({showAllPastAppointments ? pastAppointments.length : displayedPastAppointments.length}{!showAllPastAppointments && pastAppointments.length > 5 ? ` of ${pastAppointments.length}` : ''})
              </h4>
              {displayedPastAppointments.length === 0 ? (
                <p style={{ color: '#b4cce2', textAlign: 'center', padding: '20px' }}>
                  No past appointments
                </p>
              ) : (
                <>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                      <thead>
                        <tr style={{ backgroundColor: 'rgba(9, 35, 55, 0.82)' }}>
                          <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Date & Time</th>
                          <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Doctor</th>
                          <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Notes</th>
                          <th style={{ padding: '12px', textAlign: 'left', color: '#42b5f5', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {displayedPastAppointments.map((apt: AppointmentRow) => (
                          <tr key={apt.id} style={{ backgroundColor: 'rgba(9, 32, 52, 0.82)', opacity: '0.8' }}>
                            <td style={{ padding: '12px', color: '#b4cce2', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                              {formatDate(apt.appointment_time)}
                            </td>
                            <td style={{ padding: '12px', color: '#b4cce2', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                              {apt.doctor_name || 'Doctor'}
                            </td>
                            <td style={{ padding: '12px', color: '#b4cce2', fontSize: '14px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                              {apt.notes || 'No notes'}
                            </td>
                            <td style={{ padding: '12px', border: '1px solid rgba(136, 194, 227, 0.36)' }}>
                              <span style={{ 
                                color: apt.status === 'CANCELLED' ? '#ff90ab' : '#49d7c2',
                                fontWeight: '500',
                                fontSize: '14px'
                              }}>
                                {apt.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  
                  {/* Show More/Less Button */}
                  {pastAppointments.length > 5 && (
                    <div style={{ textAlign: 'center', marginTop: '16px' }}>
                      <button
                        onClick={() => setShowAllPastAppointments(!showAllPastAppointments)}
                        style={{
                          background: '#42b5f5',
                          color: 'white',
                          border: 'none',
                          borderRadius: '6px',
                          padding: '8px 16px',
                          fontSize: '14px',
                          cursor: 'pointer',
                          fontWeight: '500',
                          transition: 'background-color 0.2s'
                        }}
                        onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#3699d6'}
                        onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#42b5f5'}
                      >
                        {showAllPastAppointments 
                          ? `Show Less (${pastAppointments.length - 5} hidden)` 
                          : `Show More (${pastAppointments.length - 5} more)`
                        }
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
