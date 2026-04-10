/**
 * Patient Prescriptions Page Component
 * Displays comprehensive prescription and medical record information for the logged-in patient
 * Follows the same patterns as other patient pages with professional medical software styling
 */

import React, { useState, useEffect } from "react";
import { api } from "../../api";
import { useAuthContext } from "../../contexts/AuthContext";
import { parseErrorMessage } from "../../utils";
import type { SessionState } from "../../types/app";

interface PatientPrescriptionsPageProps {
  auth: any;
}

interface PrescriptionRecord {
  appointment_time: string;
  patient_name?: string;
  doctor_name: string;
  appointment_status: string;
  appointment_note: string;
  symptoms: string;
  diagnosis: string;
  lab_results: string;
  medication_details: string;
  pharmacy_name: string;
  appointment_created_at: string;
  status?: string;
}

export function PatientPrescriptionsPage({ auth }: PatientPrescriptionsPageProps) {
  const { status, setStatus } = useAuthContext();
  const [prescriptions, setPrescriptions] = useState<PrescriptionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [patientInfo, setPatientInfo] = useState<any>(null);

  // Clear any existing status messages when navigating to prescriptions page
  useEffect(() => {
    setStatus("");
  }, [setStatus]);

  // Load patient prescriptions on component mount
  useEffect(() => {
    const loadPrescriptions = async () => {
      if (!auth.session.accessToken) {
        setError("Authentication required");
        setLoading(false);
        return;
      }

      try {
        console.log('🔍 DEBUG: Loading patient prescriptions using /patient/prescriptions-full endpoint...');
        
        // Fetch patient information and prescriptions in parallel
        const [patientData, prescriptionsData] = await Promise.all([
          api.getCurrentPatient(auth.session.accessToken),
          api.patientPrescriptionsFull(auth.session.accessToken)
        ]);
        
        console.log('🔍 DEBUG: Patient data received:', patientData);
        console.log('🔍 DEBUG: Patient prescriptions data received:', prescriptionsData);
        console.log('🔍 DEBUG: Number of prescriptions:', prescriptionsData.length);
        
        if (prescriptionsData.length > 0) {
          console.log('🔍 DEBUG: First prescription full structure:', JSON.stringify(prescriptionsData[0], null, 2));
          console.log('🔍 DEBUG: Available fields in first prescription:', Object.keys(prescriptionsData[0]));
        }
        
        // Set patient info and prescriptions
        setPatientInfo(patientData);
        setPrescriptions(prescriptionsData);
        setError("");
      } catch (error) {
        console.error("Failed to load prescriptions:", error);
        setError(parseErrorMessage(error));
      } finally {
        setLoading(false);
      }
    };

    loadPrescriptions();
  }, [auth.session.accessToken]);

  // Format date for display
  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (error) {
      return dateStr;
    }
  };

  // Format date only (without time)
  const formatDateOnly = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch (error) {
      return dateStr;
    }
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>My Prescriptions & Medical Records</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        View your completed appointments, prescriptions, and medical history
      </p>

      {/* Status/Error Messages */}
      {status && (
        <div className="status" style={{ 
          marginBottom: '20px', 
          color: status.includes("success") ? '#49d7c2' : '#ff90ab', 
          padding: '12px', 
          backgroundColor: status.includes("success") ? 'rgba(73, 215, 194, 0.1)' : 'rgba(255, 144, 171, 0.1)', 
          borderRadius: '4px', 
          border: status.includes("success") ? '1px solid #49d7c2' : '1px solid rgba(255, 144, 171, 0.3)' 
        }}>
          {status}
        </div>
      )}

      {error && (
        <div style={{ 
          padding: '12px', 
          marginBottom: '20px', 
          backgroundColor: 'rgba(255, 144, 171, 0.1)', 
          color: '#ff90ab', 
          borderRadius: '4px', 
          border: '1px solid rgba(255, 144, 171, 0.3)' 
        }}>
          {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#b4cce2' }}>
          Loading your prescriptions and medical records...
        </div>
      )}

      {/* Prescriptions Content */}
      {!loading && !error && (
        <>
          {/* Patient Details Section */}
          {patientInfo && (
            <div className="card" style={{ 
              padding: '20px', 
              marginBottom: '20px', 
              backgroundColor: '#1e293b', 
              border: '1px solid #3b82f6'
            }}>
              <h2 style={{ color: '#eef8ff', marginBottom: '16px', fontSize: '18px', fontWeight: '600' }}>
                Patient Information
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                <div>
                  <span style={{ color: '#94a3b8', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Name</span>
                  <p style={{ color: '#eef8ff', fontSize: '14px', fontWeight: '500', margin: '4px 0 0 0' }}>
                    {patientInfo.name || 'N/A'}
                  </p>
                </div>
                <div>
                  <span style={{ color: '#94a3b8', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Email</span>
                  <p style={{ color: '#eef8ff', fontSize: '14px', fontWeight: '500', margin: '4px 0 0 0' }}>
                    {patientInfo.email || 'N/A'}
                  </p>
                </div>
                <div>
                  <span style={{ color: '#94a3b8', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Phone</span>
                  <p style={{ color: '#eef8ff', fontSize: '14px', fontWeight: '500', margin: '4px 0 0 0' }}>
                    {patientInfo.phone || 'N/A'}
                  </p>
                </div>
                <div>
                  <span style={{ color: '#94a3b8', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Date of Birth</span>
                  <p style={{ color: '#eef8ff', fontSize: '14px', fontWeight: '500', margin: '4px 0 0 0' }}>
                    {patientInfo.date_of_birth ? new Date(patientInfo.date_of_birth).toLocaleDateString() : 'N/A'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <div className="card" style={{ padding: '16px', backgroundColor: '#1e293b', border: '1px solid #3b82f6' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                Total Prescriptions
              </div>
              <div style={{ color: '#eef8ff', fontSize: '24px', fontWeight: 'bold' }}>
                {prescriptions.length}
              </div>
            </div>
            <div className="card" style={{ padding: '16px', backgroundColor: '#1e293b', border: '1px solid #3b82f6' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                Completed Appointments
              </div>
              <div style={{ color: '#eef8ff', fontSize: '24px', fontWeight: 'bold' }}>
                {prescriptions.filter(p => p.appointment_status === 'COMPLETED').length}
              </div>
            </div>
            <div className="card" style={{ padding: '16px', backgroundColor: '#1e293b', border: '1px solid #3b82f6' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                Active Medications
              </div>
              <div style={{ color: '#eef8ff', fontSize: '24px', fontWeight: 'bold' }}>
                {prescriptions.filter(p => p.medication_details && p.medication_details !== '').length}
              </div>
            </div>
          </div>

          {/* Prescriptions Table */}
          <div className="card" style={{ padding: '20px', backgroundColor: '#1e293b', border: '1px solid #3b82f6' }}>
          {prescriptions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#b4cce2' }}>
              <p>No completed appointments or prescriptions found.</p>
              <p style={{ fontSize: '14px', marginTop: '8px' }}>
                Your prescriptions and medical records will appear here after you complete appointments.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '14px' }}>
                <thead>
                  <tr>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Appointment Time
                    </th>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Doctor
                    </th>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Status
                    </th>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Notes
                    </th>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Symptoms
                    </th>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Diagnosis
                    </th>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Lab Results
                    </th>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Medication
                    </th>
                    <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                      Pharmacy
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {prescriptions.map((record, index) => (
                    <tr key={index} style={{ backgroundColor: index % 2 === 0 ? 'transparent' : 'rgba(30, 41, 59, 0.5)' }}>
                      <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        <div>
                          <strong>{formatDate(record.appointment_time)}</strong>
                        </div>
                      </td>
                      <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        {record.doctor_name || 'N/A'}
                      </td>
                      <td style={{ padding: '12px', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        <span style={{
                          padding: '4px 8px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: '500',
                          backgroundColor: record.appointment_status === 'COMPLETED' ? 'rgba(73, 215, 194, 0.2)' : 'rgba(148, 163, 184, 0.2)',
                          color: record.appointment_status === 'COMPLETED' ? '#49d7c2' : '#94a3b8'
                        }}>
                          {record.appointment_status}
                        </span>
                      </td>
                      <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        {record.appointment_note || '-'}
                      </td>
                      <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        {record.symptoms || '-'}
                      </td>
                      <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        {record.diagnosis || '-'}
                      </td>
                      <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        {record.lab_results || '-'}
                      </td>
                      <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        {record.medication_details || '-'}
                      </td>
                      <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155', verticalAlign: 'top' }}>
                        {record.pharmacy_name || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        </>
      )}
    </section>
  );
}
