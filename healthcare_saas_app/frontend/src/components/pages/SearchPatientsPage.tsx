/**
 * Search Patients Page Component
 * Allows doctors to search for patients by name and view their medical history
 * Follows the same patterns as the original DoctorSearchPanel and PatientSearchResults
 */

import React, { useState, useEffect } from "react";
import { api } from "../../api";
import { useAuthContext } from "../../contexts/AuthContext";
import { parseErrorMessage } from "../../utils";
import { LabeledField } from "../common/LabeledField";
import type { SessionState, PatientSearchRow } from "../../types";

interface SearchPatientsPageProps {
  auth: any;
  appointments: any;
}

// DoctorDetails component (same as in other pages)
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

// PatientSearchResults component
function PatientSearchResults({ rows, session }: { rows: PatientSearchRow[]; session: SessionState }) {
  function calculateAge(dob: string): number {
    if (!dob) return 0; // Return 0 if no DOB
    
    try {
      const birthDate = new Date(dob);
      // Check if the date is valid
      if (isNaN(birthDate.getTime())) return 0;
      
      const today = new Date();
      let age = today.getFullYear() - birthDate.getFullYear();
      const monthDiff = today.getMonth() - birthDate.getMonth();
      if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
        age--;
      }
      return age;
    } catch (error) {
      console.error("Error calculating age:", error);
      return 0;
    }
  }

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

  // Extract unique patients
  const uniquePatients = rows.reduce((acc: any[], row) => {
    const existing = acc.find(p => p.id === row.id);
    if (!existing) {
      acc.push({
        id: row.id,
        name: row.name,
        phone: row.phone,
        dob: row.dob,
        gender: row.gender || 'N/A',
        address: row.address || ''
      });
    }
    return acc;
  }, []);

  // State to track which patient's prescriptions are currently displayed
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(
    uniquePatients.length > 0 ? uniquePatients[0].id : null
  );

  // State for additional prescriptions
  const [additionalPrescriptions, setAdditionalPrescriptions] = useState<PatientSearchRow[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showMore, setShowMore] = useState(false);

  // Filter rows to show only the selected patient's prescriptions (loaded from unified API)
  const allFilteredRows = selectedPatientId 
    ? rows.filter(row => row.id === selectedPatientId) // Only show prescriptions that were loaded from unified API
    : [];

  // Show loaded prescriptions only if they exist
  const displayRows = showMore && additionalPrescriptions.length > 0
    ? additionalPrescriptions // Show complete prescription data loaded from unified API
    : []; // Show nothing until prescriptions are loaded

  // Check if patient has more than 5 prescriptions
  const hasMorePrescriptions = selectedPatientId 
    ? allFilteredRows.length > 5
    : false;

  // Auto-select first patient when results change and load their prescriptions
  useEffect(() => {
    if (uniquePatients.length > 0 && !selectedPatientId) {
      setSelectedPatientId(uniquePatients[0].id);
      // Automatically load prescriptions for the first patient
      loadPrescriptionsForPatient(uniquePatients[0].id);
    }
  }, [uniquePatients, selectedPatientId]);

  // Function to load prescriptions for a specific patient
  const loadPrescriptionsForPatient = async (patientId: string) => {
    if (!session.accessToken) return;
    
    setLoadingMore(true);
    
    try {
      const allPrescriptions = await api.patientPrescriptionsFull(session.accessToken, patientId);
      
      // Convert the prescription data to match our existing structure
      const convertedPrescriptions = allPrescriptions.map(p => ({
        id: patientId,
        name: uniquePatients.find(p => p.id === patientId)?.name || 'Unknown',
        phone: uniquePatients.find(p => p.id === patientId)?.phone || '',
        dob: uniquePatients.find(p => p.id === patientId)?.dob || '',
        gender: uniquePatients.find(p => p.id === patientId)?.gender || '',
        address: uniquePatients.find(p => p.id === patientId)?.address || '',
        symptoms: p.symptoms,
        diagnosis: p.diagnosis,
        lab_results: p.lab_results,
        medication: p.medication_details,
        prescription_date: p.appointment_time,
        doctor_name: p.doctor_name,
        pharmacy_name: p.pharmacy_name,
        appointment_status: p.appointment_status,
        appointment_note: p.appointment_note,
      }));
      
      // Store the complete prescription data in additionalPrescriptions
      setAdditionalPrescriptions(convertedPrescriptions);
      setShowMore(true);
    } catch (error) {
      console.error("Error loading prescriptions:", error);
    } finally {
      setLoadingMore(false);
    }
  };

  // Get selected patient name
  const selectedPatient = uniquePatients.find(p => p.id === selectedPatientId);

  return (
    <div className="card" style={{ padding: '20px' }}>
      <h3>PATIENT DETAILS</h3>
      
      {/* Patient Summary Section */}
      {uniquePatients.length > 0 && (
        <div style={{ marginBottom: '20px', padding: '16px', backgroundColor: 'rgba(66, 181, 245, 0.05)', borderRadius: '8px' }}>
          {uniquePatients.map((patient) => (
            <div key={patient.id} style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap', fontSize: '13px' }}>
              <span>
                <button 
                  onClick={() => {
                    setSelectedPatientId(patient.id);
                    setShowMore(false);
                    setAdditionalPrescriptions([]);
                    // Load prescriptions for this patient
                    loadPrescriptionsForPatient(patient.id);
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: selectedPatientId === patient.id ? '#2793d3' : '#42b5f5',
                    textDecoration: selectedPatientId === patient.id ? 'underline' : 'none',
                    cursor: 'pointer',
                    padding: 0,
                    font: 'inherit',
                    fontWeight: selectedPatientId === patient.id ? 'bold' : 'normal',
                    fontSize: '13px'
                  }}
                  onMouseEnter={(e) => {
                    if (selectedPatientId !== patient.id) {
                      e.currentTarget.style.color = '#2793d3';
                      e.currentTarget.style.textDecoration = 'underline';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedPatientId !== patient.id) {
                      e.currentTarget.style.color = '#42b5f5';
                      e.currentTarget.style.textDecoration = 'none';
                    }
                  }}
                >
                  {patient.name}
                </button>
              </span>
              <span style={{ color: '#e8f6ff', fontSize: '13px' }}>
                Age: {calculateAge(patient.dob)}
              </span>
              <span style={{ color: '#e8f6ff', fontSize: '13px' }}>
                Gender: {patient.gender}
              </span>
              <span style={{ color: '#e8f6ff', fontSize: '13px' }}>
                Phone: {formatPhoneNumber(patient.phone)}
              </span>
              {patient.address && (
                <span style={{ color: '#e8f6ff', fontSize: '13px' }}>
                  Address: {patient.address}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      
      {displayRows.length === 0 && selectedPatientId && !loadingMore ? (
        <p style={{ color: '#94a3b8', textAlign: 'center', padding: '40px' }}>
          No prescription records found for {selectedPatient?.name || 'this patient'}.
        </p>
      ) : displayRows.length === 0 && selectedPatientId && loadingMore ? (
        <p style={{ color: '#94a3b8', textAlign: 'center', padding: '40px' }}>
          Loading prescription records...
        </p>
      ) : displayRows.length === 0 ? (
        <p style={{ color: '#94a3b8', textAlign: 'center', padding: '40px' }}>
          Select a patient to view their prescription records.
        </p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '14px' }}>
            <thead>
              <tr>
                <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>PRESCRIPTION DATE</th>
                <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>DOCTOR</th>
                <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>NOTES</th>
                <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>SYMPTOMS</th>
                <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>DIAGNOSIS</th>
                <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>LAB RESULTS</th>
                <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>MEDICATION</th>
                <th style={{ padding: '12px', textAlign: 'left', backgroundColor: '#1e293b', color: '#eef8ff', borderBottom: '1px solid #334155' }}>PHARMACY</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map((row, index) => (
                <tr key={`${row.id}-${row.prescription_date}-${index}`} style={{ backgroundColor: index % 2 === 0 ? 'transparent' : 'rgba(30, 41, 59, 0.5)' }}>
                  <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                    {row.prescription_date ? (
                      <div>
                        <div>{new Date(row.prescription_date).toLocaleDateString('en-US', { 
                          year: 'numeric',
                          month: 'short', 
                          day: 'numeric'
                        })}</div>
                        <div style={{ fontSize: '12px', color: '#b4cce2' }}>
                          {new Date(row.prescription_date).toLocaleTimeString('en-US', { 
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                      </div>
                    </div>
                  ) : '-'}
                </td>
                <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                    {row.doctor_name || 'Unknown'}
                  </td>
                  <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                    {(row as any).appointment_note || '-'}
                  </td>
                  <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                    {row.symptoms || '-'}
                  </td>
                <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                  {row.diagnosis || '-'}
                </td>
                <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                  {row.lab_results || '-'}
                </td>
                <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                  {row.medication || '-'}
                </td>
                <td style={{ padding: '12px', color: '#eef8ff', borderBottom: '1px solid #334155' }}>
                  {(row as any).pharmacy_name || '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}

      {loadingMore && (
        <div style={{ marginTop: '16px', textAlign: 'center' }}>
          <span style={{ color: '#eef8ff', fontSize: '13px' }}>Loading prescription data...</span>
        </div>
      )}
    </div>
  );
}

export function SearchPatientsPage({ auth, appointments }: SearchPatientsPageProps) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<PatientSearchRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [previousQuery, setPreviousQuery] = useState("");

  // Clear search results when query changes
  useEffect(() => {
    if (previousQuery && query !== previousQuery) {
      // Clear the rows when query changes
      setRows([]);
    }
    setPreviousQuery(query);
  }, [query, previousQuery]);

  async function searchPatients() {
    if (!auth.session.accessToken) {
      setError("Authentication required");
      return;
    }

    if (query.trim().length < 2) {
      setError("Please enter at least 2 characters to search.");
      return;
    }

    setLoading(true);
    setError("");
    
    try {
      const results = await api.searchPatients(auth.session.accessToken, query);
      setRows(results);
    } catch (error) {
      console.error("Search failed:", error);
      setError(parseErrorMessage(error));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    searchPatients();
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Search Patients</h2>
      
      <DoctorDetails session={auth.session} auth={auth} />
      
      <form className="card" style={{ padding: '20px' }} onSubmit={onSubmit}>
        <LabeledField 
          id="doctor-search" 
          label="Search Patient by Name" 
          helpText="Use at least first 2 letters of patient name." 
          value={query} 
          onChange={setQuery} 
          error={error} 
        />
        <button 
          type="submit"
          disabled={loading}
          style={{
            padding: '12px 24px',
            fontSize: '16px',
            fontWeight: '500',
            backgroundColor: loading ? '#94a3b8' : '#42b5f5',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: loading ? 'not-allowed' : 'pointer',
            marginTop: '16px'
          }}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>
      
      <PatientSearchResults rows={rows} session={auth.session} />
    </section>
  );
}
