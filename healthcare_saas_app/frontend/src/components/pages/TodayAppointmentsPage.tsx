/**
 * Today Appointments Page Component
 * Displays today's appointments for doctors with confirmation functionality
 * Shows confirmed and scheduled appointments for the current day
 */

import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { parseServerDate } from "../../utils";
import type { SessionState } from "../../types/app";
import { RescheduleAppointmentModal, type RescheduleTarget } from "../common/RescheduleAppointmentModal";

interface EnhancedAppointment {
  id: string;
  time: string;
  patient_name: string;
  reason: string;
  status: string;
  patient_phone?: string;
  patient_id?: string;
}

// Phone formatting function
function formatPhoneNumber(phone: string): string {
  if (!phone) return 'N/A';
  // Remove all non-digit characters
  const cleaned = phone.replace(/\D/g, '');
  
  // Format based on length
  if (cleaned.length === 10) {
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  } else if (cleaned.length > 10) {
    // Handle country code
    return `+${cleaned.slice(0, cleaned.length - 10)} (${cleaned.slice(-10, -7)}) ${cleaned.slice(-7, -4)}-${cleaned.slice(-4)}`;
  }
  return phone; // Return original if can't format
}

interface TodayAppointmentsPageProps {
  auth: any;
  userData: any;
  appointments: any;
}

// DoctorDetails component (same as original)
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
          <strong>Phone:</strong> {
            formatPhoneNumber(
              doctorData?.phone || 
              doctorData?.phone_number || 
              doctorData?.phoneNumber || 
              doctorData?.contact_phone || 
              doctorData?.contactPhone || 
              doctorData?.mobile || 
              doctorData?.contact || 
              ''
            )
          }
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

export function TodayAppointmentsPage({ auth, userData, appointments }: TodayAppointmentsPageProps) {
  const [todayAppointments, setTodayAppointments] = useState<Array<{ id: string; doctor_id: string; time: string; patient_name: string; reason: string; status: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [rescheduleTarget, setRescheduleTarget] = useState<RescheduleTarget | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  // Fetch, keep confirmed and scheduled appointments, and sort by time
  const refreshTodayAppointments = async () => {
    const data = await api.getTodayAppointments(auth.session.accessToken);
    const validAppointments = data.filter(apt => apt.status === 'CONFIRMED' || apt.status === 'SCHEDULED');
    validAppointments.sort((a, b) => parseServerDate(a.time).getTime() - parseServerDate(b.time).getTime());
    setTodayAppointments(validAppointments);
  };

  useEffect(() => {
    const loadTodayAppointments = async () => {
      setLoading(true);
      try {
        await refreshTodayAppointments();
      } catch (err) {
        setError("Failed to load today's appointments");
        console.error("Error loading appointments:", err);
      } finally {
        setLoading(false);
      }
    };

    loadTodayAppointments();
  }, [auth.session.accessToken]);

  const formatTime = (timeStr: string) => {
    const date = parseServerDate(timeStr);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  };

  const handleConfirmAppointment = async (appointmentId: string) => {
    if (!window.confirm("Are you sure you want to confirm this appointment?")) {
      return;
    }
    
    setConfirmingId(appointmentId);
    try {
      await api.confirmAppointment(appointmentId, auth.session.accessToken);
      
      // Refresh the appointments list
      await refreshTodayAppointments();
      
      alert("Appointment confirmed successfully");
    } catch (error) {
      console.error("Failed to confirm appointment:", error);
      alert("Failed to confirm appointment. Please try again.");
    } finally {
      setConfirmingId(null);
    }
  };

  const handleCancelAppointment = async (appointmentId: string) => {
    if (!window.confirm("Are you sure you want to cancel this appointment?")) {
      return;
    }

    setCancellingId(appointmentId);
    try {
      await api.cancelAppointment(auth.session.accessToken, appointmentId);
      await refreshTodayAppointments();
      alert("Appointment cancelled successfully");
    } catch (error) {
      console.error("Failed to cancel appointment:", error);
      alert("Failed to cancel appointment. Please try again.");
    } finally {
      setCancellingId(null);
    }
  };

  return (
    <section>
      <h2>Today's Appointments</h2>
      
      <DoctorDetails session={auth.session} auth={auth} />
      
      <div className="card" style={{ padding: '20px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#b4cce2' }}>
            Loading today's appointments...
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#ff90ab' }}>
            {error}
          </div>
        ) : todayAppointments.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#b4cce2' }}>
            No appointments for today
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {todayAppointments.map((appointment) => (
              <div key={appointment.id} style={{ 
                border: `1px solid ${appointment.status === 'CONFIRMED' ? 'rgba(73, 215, 194, 0.36)' : 'rgba(66, 181, 245, 0.36)'}`, 
                borderRadius: '8px', 
                padding: '16px',
                backgroundColor: 'rgba(9, 32, 52, 0.82)'
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: '16px', alignItems: 'center' }}>
                  <div style={{ 
                    backgroundColor: appointment.status === 'CONFIRMED' ? '#49d7c2' : '#42b5f5', 
                    color: 'white', 
                    padding: '8px 12px', 
                    borderRadius: '6px',
                    fontSize: '14px',
                    fontWeight: '500',
                    textAlign: 'center',
                    minWidth: '100px'
                  }}>
                    {formatTime(appointment.time)}
                  </div>
                  <div style={{ flex: 1 }}>
                    <h4 style={{ margin: '0 0 8px 0', color: '#eef8ff', fontSize: '16px' }}>
                      {appointment.patient_name}
                    </h4>
                    {appointment.reason && (
                      <p style={{ margin: '0 0 4px 0', color: '#94a3b8', fontSize: '14px' }}>
                        <strong>Reason:</strong> {appointment.reason}
                      </p>
                    )}
                    <div style={{ 
                      display: 'inline-block',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: '500',
                      backgroundColor: appointment.status === 'CONFIRMED' ? 'rgba(73, 215, 194, 0.2)' : 'rgba(66, 181, 245, 0.2)',
                      color: appointment.status === 'CONFIRMED' ? '#49d7c2' : '#42b5f5'
                    }}>
                      {appointment.status}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {appointment.status === 'SCHEDULED' && (
                      <button
                        onClick={() => handleConfirmAppointment(appointment.id)}
                        disabled={confirmingId === appointment.id}
                        style={{
                          padding: '6px 12px',
                          background: confirmingId === appointment.id ? '#94a3b8' : '#42b5f5',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: '500',
                          cursor: confirmingId === appointment.id ? 'not-allowed' : 'pointer'
                        }}
                      >
                        {confirmingId === appointment.id ? 'Confirming...' : 'Confirm'}
                      </button>
                    )}
                    {(appointment.status === 'SCHEDULED' || appointment.status === 'CONFIRMED') && (
                      <button
                        onClick={() => setRescheduleTarget({
                          id: appointment.id,
                          doctorId: appointment.doctor_id,
                          appointmentTime: appointment.time,
                          patientName: appointment.patient_name,
                          reason: appointment.reason,
                          status: appointment.status
                        })}
                        style={{
                          padding: '6px 12px',
                          background: '#f0a020',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: '500',
                          cursor: 'pointer'
                        }}
                      >
                        Reschedule
                      </button>
                    )}
                    {(appointment.status === 'SCHEDULED' || appointment.status === 'CONFIRMED') && (
                      <button
                        onClick={() => handleCancelAppointment(appointment.id)}
                        disabled={cancellingId === appointment.id}
                        style={{
                          padding: '6px 12px',
                          background: cancellingId === appointment.id ? '#94a3b8' : '#dc3545',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: '500',
                          cursor: cancellingId === appointment.id ? 'not-allowed' : 'pointer'
                        }}
                      >
                        {cancellingId === appointment.id ? 'Cancelling...' : 'Cancel'}
                      </button>
                    )}
                    <Link
                      to={`/doctors/consultation/${appointment.id}`}
                      // Only confirmed appointments can be consulted (the server enforces this too)
                      onClick={(e) => { if (appointment.status !== 'CONFIRMED') e.preventDefault(); }}
                      aria-disabled={appointment.status !== 'CONFIRMED'}
                      title={appointment.status === 'CONFIRMED' ? undefined : 'Confirm the appointment to start the consultation'}
                      style={{
                        display: 'inline-block',
                        padding: '8px 16px',
                        backgroundColor: appointment.status === 'CONFIRMED' ? '#49d7c2' : '#94a3b8',
                        color: 'white',
                        textDecoration: 'none',
                        borderRadius: '6px',
                        fontSize: '14px',
                        fontWeight: '500',
                        cursor: appointment.status === 'CONFIRMED' ? 'pointer' : 'not-allowed',
                        opacity: appointment.status === 'CONFIRMED' ? 1 : 0.5
                      }}
                    >
                      Consultation
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {rescheduleTarget && (
        <RescheduleAppointmentModal
          target={rescheduleTarget}
          accessToken={auth.session.accessToken}
          onClose={() => setRescheduleTarget(null)}
          onRescheduled={refreshTodayAppointments}
        />
      )}
    </section>
  );
}
