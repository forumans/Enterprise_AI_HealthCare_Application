/**
 * ConsultationForm Component
 * Handles the patient consultation form for doctors
 * Includes symptoms, diagnosis, lab results, and prescription fields
 */

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { parseErrorMessage, delay } from "../../utils";
import { APPOINTMENT_STATUS_REDIRECT_DELAY } from "../../constants";
import type { SessionState, ConsultationState } from "../../types/app";

interface ConsultationFormProps {
  session: SessionState;
  appointmentId: string;
}

export function ConsultationForm({ session, appointmentId }: ConsultationFormProps) {
  const navigate = useNavigate();
  
  // Form state
  const [consultationState, setConsultationState] = useState<ConsultationState>({
    symptoms: "",
    diagnosis: "",
    labResults: "",
    medication: "",
    dosage: "",
    instructions: ""
  });

  // UI state
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [appointment, setAppointment] = useState<any>(null);
  const [pharmacies, setPharmacies] = useState<Array<{id: string; name: string; address: string; phone: string}>>([]);
  const [selectedPharmacy, setSelectedPharmacy] = useState<string>("");

  // Load appointment details and pharmacies
  useEffect(() => {
    async function loadData() {
      try {
        const [details, pharmaciesData] = await Promise.all([
          api.getAppointmentDetails(appointmentId, session.accessToken),
          api.getPharmacies(session.accessToken)
        ]);
        setAppointment(details);
        setPharmacies(pharmaciesData);
        console.log('🔍 DEBUG: Loaded pharmacies:', pharmaciesData);
        console.log('🔍 DEBUG: Number of pharmacies loaded:', pharmaciesData.length);
      } catch (err: any) {
        console.error('🔍 DEBUG: Error loading appointment details:', err);
        const errorMessage = parseErrorMessage(err);
        
        // Check if this is an "Appointment not found" error
        if (errorMessage === "Appointment not found") {
          // Show error message without redirecting
          setError("Appointment was cancelled by the patient. Cannot start consultation.");
        } else {
          setError(errorMessage);
        }
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [appointmentId, session.accessToken, navigate]);

  /**
   * Handles cancel button click
   */
  const handleCancel = () => {
    navigate("/doctors/today-appointments");
  };

  /**
   * Handles form submission for consultation
   */
  const handleSubmitConsultation = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!consultationState.symptoms || !consultationState.diagnosis) {
      setError("Please fill in at least symptoms and diagnosis fields");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      let medicalRecordId = null;
      
      // Try to create medical record first
      try {
        const medicalRecordResponse = await api.createMedicalRecord({
          patient_id: appointment.patient_id,
          diagnosis: consultationState.diagnosis,
          notes: consultationState.symptoms || "No specific symptoms noted",
          lab_results: consultationState.labResults || null
        }, session.accessToken);
        console.log("Medical record created successfully");
        medicalRecordId = medicalRecordResponse.id;
      } catch (medicalRecordError: any) {
        // If medical record already exists (409), we need to get the existing record ID
        if (medicalRecordError.message?.includes("Medical record already exists for appointment")) {
          console.log("Medical record already exists, fetching existing record");
          setSuccess("Medical record already exists. Fetching existing record...");
          
          // Get the existing medical record for this appointment
          try {
            const existingRecords = await api.getMedicalRecordByAppointment(appointmentId, session.accessToken);
            if (existingRecords && existingRecords.length > 0) {
              medicalRecordId = existingRecords[0].id;
              console.log("Found existing medical record ID:", medicalRecordId);
            }
          } catch (fetchError) {
            console.error("Failed to fetch existing medical record:", fetchError);
          }
        } else {
          // For other errors, re-throw
          throw medicalRecordError;
        }
      }

      // Create prescription if medication is provided and we have a medical record ID
      if (consultationState.medication && consultationState.dosage && medicalRecordId) {
        console.log("Creating prescription with medical record ID:", medicalRecordId);
        await api.createPrescription({
          medical_record_id: medicalRecordId,
          medication_details: `${consultationState.medication} - ${consultationState.dosage}. ${consultationState.instructions || "Take as prescribed"}`,
          pharmacy_id: selectedPharmacy || null
        }, session.accessToken);
        console.log("Prescription created successfully");
      } else if (consultationState.medication && consultationState.dosage) {
        console.log("Cannot create prescription - no medical record ID available");
      }

      // Mark appointment as completed
      await api.completeAppointment(appointmentId, session.accessToken);

      setSuccess("Consultation completed successfully!");
      
      // Redirect after a delay
      await delay(APPOINTMENT_STATUS_REDIRECT_DELAY);
      navigate("/doctors/today-appointments");

    } catch (err) {
      setError("Failed to save consultation details");
      console.error("Error saving consultation:", err);
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * Updates consultation state
   */
  const updateConsultationState = (field: keyof ConsultationState, value: string) => {
    setConsultationState(prev => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <section>
        <h2>Consultation</h2>
        <div className="card" style={{ padding: '40px', textAlign: 'center', color: '#b4cce2' }}>
          Loading appointment details...
        </div>
      </section>
    );
  }

  // Check if this is an "Appointment not found" error scenario
  const isAppointmentNotFoundError = error === "Appointment was cancelled by the patient. Cannot start consultation.";

  return (
    <section>
      <h2>Patient Consultation</h2>
      
      {appointment && !isAppointmentNotFoundError && (
        <div className="card" style={{ marginBottom: '20px', padding: '20px' }}>
          <h3 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>Appointment Details</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div>
              <strong style={{ color: '#42b5f5' }}>Patient:</strong>
              <p style={{ margin: '4px 0 0 0', color: '#eef8ff' }}>{appointment.patient_name}</p>
            </div>
            <div>
              <strong style={{ color: '#42b5f5' }}>Date & Time:</strong>
              <p style={{ margin: '4px 0 0 0', color: '#eef8ff' }}>
                {new Date(appointment.time).toLocaleString('en-US', { 
                  weekday: 'short', 
                  month: 'short', 
                  day: 'numeric', 
                  hour: '2-digit', 
                  minute: '2-digit'
                })}
              </p>
            </div>
            <div>
              <strong style={{ color: '#42b5f5' }}>Reason for Visit:</strong>
              <p style={{ margin: '4px 0 0 0', color: '#eef8ff' }}>{appointment.notes || 'No reason provided'}</p>
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: '20px' }}>
        <h3 style={{ margin: '0 0 20px 0', color: '#eaf5ff' }}>Consultation Details</h3>
        
        {error && (
          <div style={{ 
            padding: '12px', 
            margin: '0 0 16px 0', 
            backgroundColor: isAppointmentNotFoundError ? '#ff90ab40' : '#ff90ab20', 
            color: '#ff90ab', 
            borderRadius: '6px',
            border: '1px solid #ff90ab',
            fontSize: isAppointmentNotFoundError ? '16px' : '14px',
            fontWeight: isAppointmentNotFoundError ? 'bold' : 'normal'
          }}>
            {error}
            {isAppointmentNotFoundError && (
              <div style={{ marginTop: '12px', fontSize: '14px', fontWeight: 'normal' }}>
                Please navigate back to your appointments list to continue.
              </div>
            )}
          </div>
        )}

        {success && (
          <div style={{ 
            padding: '12px', 
            margin: '0 0 16px 0', 
            backgroundColor: '#49d7c220', 
            color: '#49d7c2', 
            borderRadius: '6px',
            border: '1px solid #49d7c2'
          }}>
            {success}
          </div>
        )}

        {/* Only show the form if NOT an appointment not found error */}
        {!isAppointmentNotFoundError && (
          <form onSubmit={handleSubmitConsultation} className="form-stack">
            <div className="form-field">
              <label className="label-row">
                Symptoms <span style={{ color: '#ff90ab' }}>*</span>
              </label>
              <textarea
                value={consultationState.symptoms}
                onChange={(e) => updateConsultationState('symptoms', e.target.value)}
                placeholder="Enter patient symptoms..."
                rows={4}
                required
                style={{
                  width: '100%',
                  padding: '11px 12px',
                  borderRadius: '10px',
                  border: '1px solid var(--border)',
                  fontSize: '14px',
                  backgroundColor: 'rgba(9, 35, 55, 0.82)',
                  color: '#eef8ff',
                  resize: 'vertical',
                  fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
                }}
              />
            </div>

            <div className="form-field">
              <label className="label-row">
                Diagnosis <span style={{ color: '#ff90ab' }}>*</span>
              </label>
              <textarea
                value={consultationState.diagnosis}
                onChange={(e) => updateConsultationState('diagnosis', e.target.value)}
                placeholder="Enter diagnosis..."
                rows={3}
                required
                style={{
                  width: '100%',
                  padding: '11px 12px',
                  borderRadius: '10px',
                  border: '1px solid var(--border)',
                  fontSize: '14px',
                  backgroundColor: 'rgba(9, 35, 55, 0.82)',
                  color: '#eef8ff',
                  resize: 'vertical',
                  fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
                }}
              />
            </div>

            <div className="form-field">
              <label className="label-row">
                Lab Results
              </label>
              <textarea
                value={consultationState.labResults}
                onChange={(e) => updateConsultationState('labResults', e.target.value)}
                placeholder="Enter lab results (if any)..."
                rows={3}
                style={{
                  width: '100%',
                  padding: '11px 12px',
                  borderRadius: '10px',
                  border: '1px solid var(--border)',
                  fontSize: '14px',
                  backgroundColor: 'rgba(9, 35, 55, 0.82)',
                  color: '#eef8ff',
                  resize: 'vertical',
                  fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
                }}
              />
            </div>

            <div style={{ 
              border: '1px solid rgba(136, 194, 227, 0.36)', 
              borderRadius: '8px', 
              padding: '16px', 
              margin: '20px 0' 
            }}>
              <h4 style={{ margin: '0 0 16px 0', color: '#eaf5ff' }}>Prescription (Optional)</h4>
              
              <div className="form-field">
                <label className="label-row">
                  Medication
                </label>
                <input
                  type="text"
                  value={consultationState.medication}
                  onChange={(e) => updateConsultationState('medication', e.target.value)}
                  placeholder="Enter medication name..."
                  style={{
                    width: '100%',
                    padding: '11px 12px',
                    borderRadius: '10px',
                    border: '1px solid var(--border)',
                    fontSize: '14px',
                    backgroundColor: 'rgba(9, 35, 55, 0.82)',
                    color: '#eef8ff',
                    fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
                  }}
                />
              </div>

              <div className="form-field">
                <label className="label-row">
                  Dosage
                </label>
                <input
                  type="text"
                  value={consultationState.dosage}
                  onChange={(e) => updateConsultationState('dosage', e.target.value)}
                  placeholder="e.g., 500mg, 1 tablet, 5ml..."
                  style={{
                    width: '100%',
                    padding: '11px 12px',
                    borderRadius: '10px',
                    border: '1px solid var(--border)',
                    fontSize: '14px',
                    backgroundColor: 'rgba(9, 35, 55, 0.82)',
                    color: '#eef8ff',
                    fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
                  }}
                />
              </div>

              <div className="form-field">
                <label className="label-row">
                  Instructions
                </label>
                <textarea
                  value={consultationState.instructions}
                  onChange={(e) => updateConsultationState('instructions', e.target.value)}
                  placeholder="e.g., Take twice daily with food..."
                  rows={2}
                  style={{
                    width: '100%',
                    padding: '11px 12px',
                    borderRadius: '10px',
                    border: '1px solid var(--border)',
                    fontSize: '14px',
                    backgroundColor: 'rgba(9, 35, 55, 0.82)',
                    color: '#eef8ff',
                    resize: 'vertical',
                    fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
                  }}
                />
              </div>

              <div className="form-field">
                <label className="label-row">
                  Pharmacy
                </label>
                <select
                  value={selectedPharmacy}
                  onChange={(e) => {
                    console.log('🔍 DEBUG: Selected pharmacy:', e.target.value);
                    setSelectedPharmacy(e.target.value);
                  }}
                  style={{
                    width: '100%',
                    padding: '11px 12px',
                    borderRadius: '10px',
                    border: '1px solid var(--border)',
                    fontSize: '14px',
                    backgroundColor: 'rgba(9, 35, 55, 0.82)',
                    color: '#eef8ff',
                    fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
                  }}
                >
                  <option value="">Select a pharmacy (optional)</option>
                  {pharmacies.length === 0 ? (
                    <option value="" disabled>No pharmacies available</option>
                  ) : (
                    pharmacies.map((pharmacy) => (
                      <option key={pharmacy.id} value={pharmacy.id}>
                        {pharmacy.name} {pharmacy.address ? `- ${pharmacy.address}` : ''}
                      </option>
                    ))
                  )}
                </select>
                {pharmacies.length === 0 && (
                  <p style={{ 
                    margin: '4px 0 0 0', 
                    fontSize: '12px', 
                    color: '#94a3b8',
                    fontStyle: 'italic'
                  }}>
                    No pharmacies are currently available in the system.
                  </p>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', marginTop: '20px', width: '100%' }}>
            <button 
              type="submit" 
              className="button-primary" 
              disabled={submitting}
              style={{
                flex: 1,
                opacity: submitting ? 0.7 : 1,
                cursor: submitting ? 'not-allowed' : 'pointer',
                padding: '11px 12px',
                borderRadius: '10px',
                fontSize: '14px',
                fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
              }}
            >
              {submitting ? 'Saving...' : 'Complete Consultation'}
            </button>
            
            <button 
              type="button" 
              className="button-secondary" 
              onClick={handleCancel}
              disabled={submitting}
              style={{
                flex: 1,
                opacity: submitting ? 0.7 : 1,
                cursor: submitting ? 'not-allowed' : 'pointer',
                backgroundColor: '#64748b',
                border: '1px solid #475569',
                padding: '11px 12px',
                borderRadius: '10px',
                color: '#eef8ff',
                fontSize: '14px',
                fontFamily: '"Plus Jakarta Sans", "Segoe UI", sans-serif'
              }}
            >
              Cancel
            </button>
          </div>
          </form>
        )}
      </div>
    </section>
  );
}
