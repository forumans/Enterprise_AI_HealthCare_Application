/**
 * Doctor Appointments Page Component
 * Displays weekly calendar view of doctor appointments with patient details
 * Handles appointment confirmation and patient selection
 */

import React, { useState, useEffect } from "react";
import { api } from "../../api";
import { parseServerDate } from "../../utils";
import type { SessionState, DoctorAppointmentRow } from "../../types/app";
import { RescheduleAppointmentModal, type RescheduleTarget } from "../common/RescheduleAppointmentModal";

interface DoctorAppointmentsPageProps {
  auth: any;
  appointments: any;
}

// Reusable Doctor Details Component
function DoctorDetails({ session, style }: { session: SessionState; style?: React.CSSProperties }) {
  const [currentDoctor, setCurrentDoctor] = useState<any>(null);
  
  React.useEffect(() => {
    if (!session.accessToken) {
      return;
    }

    let isMounted = true;

    const loadCurrentDoctor = async () => {
      try {
        const doctor = await api.getDoctorMe(session.accessToken);
        if (isMounted) {
          setCurrentDoctor(doctor);
        }
      } catch (error) {
        console.error("Failed to fetch current doctor:", error);
      }
    };

    loadCurrentDoctor();

    return () => {
      isMounted = false;
    };
  }, [session.accessToken]);

  if (!currentDoctor) {
    return null;
  }

  return (
    <div className="card" style={{ 
      marginBottom: '20px', 
      padding: '16px', 
      backgroundColor: 'rgba(9, 35, 55, 0.82)',
      ...style 
    }}>
      <h3 style={{ margin: '0 0 12px 0', color: '#dff2ff' }}>Doctor Information</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '12px' }}>
        <div>
          <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Name</label>
          <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>{currentDoctor.name}</p>
        </div>
        <div>
          <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>Specialty</label>
          <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>{currentDoctor.specialty || 'Not specified'}</p>
        </div>
        <div>
          <label style={{ fontSize: '14px', fontWeight: '700', color: '#d6ebfb', display: 'block', marginBottom: '4px' }}>License Number</label>
          <p style={{ margin: '0', fontSize: '14px', color: '#e8f6ff' }}>{currentDoctor.license_number || 'Not specified'}</p>
        </div>
      </div>
    </div>
  );
}

export function DoctorAppointmentsPage({ auth, appointments }: DoctorAppointmentsPageProps) {
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentWeekStart, setCurrentWeekStart] = useState(() => {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek; // Sunday=0, Monday=1
    const monday = new Date(today);
    monday.setDate(today.getDate() + mondayOffset);
    return monday;
  });
  const [selectedPatient, setSelectedPatient] = useState<DoctorAppointmentRow | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<RescheduleTarget | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  // Load the displayed week's appointments (Monday passed as MM/DD/YYYY)
  const reloadWeek = async () => {
    const month = String(currentWeekStart.getMonth() + 1).padStart(2, '0');
    const day = String(currentWeekStart.getDate()).padStart(2, '0');
    const year = currentWeekStart.getFullYear();
    await appointments.loadDoctorData(`${month}/${day}/${year}`);
  };

  // Load appointments when component mounts or week changes
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await reloadWeek();
      setLoading(false);
    };
    
    loadData();
  }, [currentWeekStart]);
  
  // Generate calendar days (Sunday to Saturday)
  const generateCalendarDays = () => {
    const days = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(currentWeekStart);
      date.setDate(currentWeekStart.getDate() + i);
      days.push(date);
    }
    return days;
  };
  
  const calendarDays = generateCalendarDays();
  
  // Navigate weeks
  const navigateWeek = (direction: 'prev' | 'next') => {
    const newStart = new Date(currentWeekStart);
    newStart.setDate(currentWeekStart.getDate() + (direction === 'next' ? 7 : -7));
    
    setCurrentWeekStart(newStart);
    setSelectedPatient(null);
  };
  
  // Group appointments by date and time
  const getAppointmentsForDate = (date: Date) => {
    return appointments.doctorAppointments.filter((apt: DoctorAppointmentRow) => {
      const aptDate = parseServerDate(apt.time);
      return aptDate.getFullYear() === date.getFullYear() &&
        aptDate.getMonth() === date.getMonth() &&
        aptDate.getDate() === date.getDate();
    });
  };

  // Format time for display
  const formatTime = (timeStr: string) => {
    const date = parseServerDate(timeStr);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  };
  
  // Handle patient click
  const handlePatientClick = (appointment: DoctorAppointmentRow) => {
    setSelectedPatient(appointment);
  };

  // Handle confirm appointment
  const handleConfirmAppointment = async (appointmentId: string) => {
    if (!window.confirm("Are you sure you want to confirm this appointment?")) {
      return;
    }
    
    setConfirmingId(appointmentId);
    try {
      await api.confirmAppointment(appointmentId, auth.session.accessToken);
      
      // Refresh the appointments list
      await reloadWeek();
      
      alert("Appointment confirmed successfully");
    } catch (error) {
      console.error("Failed to confirm appointment:", error);
      alert("Failed to confirm appointment. Please try again.");
    } finally {
      setConfirmingId(null);
    }
  };
  
  // Handle cancel appointment
  const handleCancelAppointment = async (appointmentId: string) => {
    if (!window.confirm("Are you sure you want to cancel this appointment?")) {
      return;
    }

    setCancellingId(appointmentId);
    try {
      await api.cancelAppointment(auth.session.accessToken, appointmentId);
      if (selectedPatient?.id === appointmentId) {
        setSelectedPatient(null);
      }
      await reloadWeek();
      alert("Appointment cancelled successfully");
    } catch (error) {
      console.error("Failed to cancel appointment:", error);
      alert("Failed to cancel appointment. Please try again.");
    } finally {
      setCancellingId(null);
    }
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Weekly Appointments</h2>
      
      <DoctorDetails session={auth.session} />
      
      {/* Patient Details Section - Above Calendar Header */}
      {selectedPatient && (
        <div className="card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ margin: 0, color: '#eaf5ff' }}>Patient Details</h3>
            <button
              onClick={() => setSelectedPatient(null)}
              style={{
                background: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 12px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              ✕ Close
            </button>
          </div>
          <div style={{ display: 'flex', gap: '30px', alignItems: 'center' }}>
            <div>
              <strong style={{ color: '#42b5f5', fontSize: '12px', textTransform: 'uppercase' }}>Patient Name:</strong>
              <p style={{ margin: '4px 0 0 0', color: '#eef8ff', fontSize: '14px' }}>{selectedPatient.patient_name}</p>
            </div>
            <div>
              <strong style={{ color: '#42b5f5', fontSize: '12px', textTransform: 'uppercase' }}>Date/Time:</strong>
              <p style={{ margin: '4px 0 0 0', color: '#eef8ff', fontSize: '14px' }}>
                {(() => {
                  const date = parseServerDate(selectedPatient.time);
                  const month = String(date.getMonth() + 1).padStart(2, '0');
                  const day = String(date.getDate()).padStart(2, '0');
                  const year = date.getFullYear();
                  const hours = date.getHours();
                  const minutes = String(date.getMinutes()).padStart(2, '0');

                  const formattedTime = `${hours % 12 === 0 ? 12 : hours % 12}:${minutes} ${hours >= 12 ? 'PM' : 'AM'}`;

                  return `${month}/${day}/${year} ${formattedTime}`;
                })()}
              </p>
            </div>
            <div>
              <strong style={{ color: '#42b5f5', fontSize: '12px', textTransform: 'uppercase' }}>Status:</strong>
              <p style={{ margin: '4px 0 0 0', color: '#eef8ff', fontSize: '14px' }}>{selectedPatient.status}</p>
            </div>
            {selectedPatient.symptoms && (
              <div style={{ flex: '1' }}>
                <strong style={{ color: '#42b5f5', fontSize: '12px', textTransform: 'uppercase' }}>Symptoms:</strong>
                <p style={{ margin: '4px 0 0 0', color: '#eef8ff', fontSize: '14px' }}>{selectedPatient.symptoms}</p>
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Week Navigation */}
      <div className="card" style={{ padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button 
            onClick={() => navigateWeek('prev')}
            style={{
              padding: '8px 16px',
              background: '#42b5f5',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            ← Previous Week
          </button>
          <h3 style={{ margin: 0, color: '#eaf5ff' }}>
            {calendarDays[0].toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} - 
            {calendarDays[6].toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          </h3>
          <button 
            onClick={() => navigateWeek('next')}
            style={{
              padding: '8px 16px',
              background: '#42b5f5',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Next Week →
          </button>
        </div>
      </div>
      
      {/* Calendar Grid - Full Width */}
      <div className="card" style={{ padding: '16px', flex: '1' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#b4cce2' }}>
            Loading appointments...
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '10px', minHeight: '400px' }}>
            {calendarDays.map((date, index) => {
              const dayAppointments = getAppointmentsForDate(date);
              const isToday = date.toDateString() === new Date().toDateString();
              
              return (
                <div 
                  key={index}
                  style={{
                    border: `1px solid ${isToday ? '#42b5f5' : 'rgba(136, 194, 227, 0.36)'}`,
                    borderRadius: '8px',
                    padding: '12px',
                    background: isToday ? 'rgba(66, 181, 245, 0.1)' : 'rgba(9, 32, 52, 0.82)',
                    minHeight: '200px'
                  }}
                >
                  <h4 style={{ 
                    margin: '0 0 10px 0', 
                    color: isToday ? '#42b5f5' : '#eaf5ff',
                    fontSize: '14px'
                  }}>
                    {date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                  </h4>
                  <div style={{ fontSize: '12px' }}>
                    {dayAppointments.length === 0 ? (
                      <span style={{ color: '#b4cce2' }}>No appointments</span>
                    ) : (
                      dayAppointments.map((apt: DoctorAppointmentRow, aptIndex: number) => (
                        <div key={aptIndex} style={{ marginBottom: '10px' }}>
                          <div style={{ color: '#b4cce2', fontSize: '13px', fontWeight: '500' }}>
                            {formatTime(apt.time)}
                          </div>
                          <button
                            onClick={() => handlePatientClick(apt)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#42b5f5',
                              textDecoration: 'underline',
                              cursor: 'pointer',
                              padding: '0',
                              fontSize: '14px',
                              textAlign: 'left',
                              fontWeight: '500'
                            }}
                          >
                            {apt.patient_name}
                          </button>
                          {apt.status && (
                            <div style={{ 
                              fontSize: '12px', 
                              color: apt.status === 'CANCELLED' ? '#ff90ab' : '#49d7c2',
                              marginTop: '3px',
                              fontWeight: '500'
                            }}>
                              {apt.status}
                            </div>
                          )}
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px 6px', marginTop: '5px' }}>
                            {apt.status === 'SCHEDULED' && (
                              <button
                                onClick={() => handleConfirmAppointment(apt.id)}
                                disabled={confirmingId === apt.id}
                                style={{
                                  background: confirmingId === apt.id ? '#94a3b8' : '#42b5f5',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  padding: '3px 10px',
                                  fontSize: '11px',
                                  cursor: 'pointer',
                                  fontWeight: '500'
                                }}
                              >
                                {confirmingId === apt.id ? 'Confirming...' : 'Confirm'}
                              </button>
                            )}
                            {(apt.status === 'SCHEDULED' || apt.status === 'CONFIRMED') && (
                              <button
                                onClick={() => setRescheduleTarget({
                                  id: apt.id,
                                  doctorId: apt.doctor_id,
                                  appointmentTime: apt.time,
                                  patientName: apt.patient_name,
                                  reason: apt.symptoms,
                                  status: apt.status
                                })}
                                style={{
                                  background: '#f0a020',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  padding: '3px 10px',
                                  fontSize: '11px',
                                  cursor: 'pointer',
                                  fontWeight: '500'
                                }}
                              >
                                Reschedule
                              </button>
                            )}
                            {(apt.status === 'SCHEDULED' || apt.status === 'CONFIRMED') && (
                              <button
                                onClick={() => handleCancelAppointment(apt.id)}
                                disabled={cancellingId === apt.id}
                                style={{
                                  background: cancellingId === apt.id ? '#94a3b8' : '#dc3545',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  padding: '3px 10px',
                                  fontSize: '11px',
                                  cursor: 'pointer',
                                  fontWeight: '500'
                                }}
                              >
                                {cancellingId === apt.id ? 'Cancelling...' : 'Cancel'}
                              </button>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {rescheduleTarget && (
        <RescheduleAppointmentModal
          target={rescheduleTarget}
          accessToken={auth.session.accessToken}
          onClose={() => setRescheduleTarget(null)}
          onRescheduled={async () => {
            setSelectedPatient(null);
            await reloadWeek();
          }}
        />
      )}
    </section>
  );
}
