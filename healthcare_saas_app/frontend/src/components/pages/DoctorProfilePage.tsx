/**
 * Doctor Profile Page Component
 * Allows doctors to update their personal and professional information
 * Follows the same patterns as the original DoctorProfilePanel
 */

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useAuthContext } from "../../contexts/AuthContext";
import { parseErrorMessage } from "../../utils";
import { LabeledField } from "../common/LabeledField";
import { StatusMessage } from "../common/StatusMessage";
import type { SessionState } from "../../types/app";

interface DoctorProfilePageProps {
  auth: any;
  userData: any;
}

interface FieldErrors {
  fullName?: string;
  phone?: string;
}

export function DoctorProfilePage({ auth, userData }: DoctorProfilePageProps) {
  const navigate = useNavigate();
  const { status, setStatus } = useAuthContext();
  
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);

  // Clear any existing status messages when navigating to profile page
  useEffect(() => {
    setStatus("");
  }, [setStatus]);

  // Load current doctor data on component mount
  useEffect(() => {
    const loadDoctorData = async () => {
      try {
        const data = await api.getDoctorProfile(auth.session.accessToken);
        
        setFullName(data.full_name || "");
        setPhone(data.phone || "");
        setSpecialty(data.specialty || "");
        setLicenseNumber(data.license_number || "");
      } catch (error) {
        console.error("Failed to load doctor profile:", error);
        setStatus(parseErrorMessage(error));
      }
    };

    if (auth.session.accessToken) {
      loadDoctorData();
    }
  }, [auth.session.accessToken, setStatus]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitAttempted(true);
    
    const nextErrors: FieldErrors = {};
    
    if (fullName.trim().length < 3) {
      nextErrors.fullName = "Name must be at least 3 characters.";
    }
    if (!/^\+?[0-9\-\s]{10,15}$/.test(phone)) {
      nextErrors.phone = "Phone should be 10-15 digits.";
    }
    
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    setLoading(true);
    try {
      const updatePayload = {
        fullName: fullName.trim(),
        phone: phone.trim(),
        specialty: specialty.trim() || undefined,
        licenseNumber: licenseNumber.trim() || undefined
      };
      
      await api.updateDoctorProfile(auth.session.accessToken, updatePayload);
      
      setStatus("Profile updated successfully!");
      setTimeout(() => {
        setStatus("");
        // Navigate to Today's Appointments page after successful update
        navigate("/doctors/today-appointments");
      }, 1500);
    } catch (error) {
      console.error("Failed to update profile:", error);
      setStatus(parseErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Update Profile</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        Update your personal and professional information
      </p>
      
      {status && (
        <StatusMessage 
          message={status} 
          type={status.includes("success") ? 'success' : 'error'} 
        />
      )}

      <form onSubmit={handleSubmit} className="form-stack">
        <LabeledField 
          id="profile-full-name" 
          label="Full Name" 
          helpText="Name must be 3-80 characters." 
          value={fullName} 
          onChange={setFullName} 
          error={submitAttempted ? errors.fullName : undefined} 
          autoComplete="off" 
        />
        
        <LabeledField 
          id="profile-phone" 
          label="Phone" 
          helpText="Use 10-15 digits. Country code allowed." 
          value={phone} 
          onChange={setPhone} 
          error={submitAttempted ? errors.phone : undefined} 
          autoComplete="off" 
        />
        
        <LabeledField 
          id="profile-specialty" 
          label="Specialty" 
          helpText="Medical specialty (optional)." 
          value={specialty} 
          onChange={setSpecialty} 
          autoComplete="off" 
        />
        
        <LabeledField 
          id="profile-license-number" 
          label="License Number" 
          helpText="Medical license number (optional)." 
          value={licenseNumber} 
          onChange={setLicenseNumber} 
          autoComplete="off" 
        />
        
        <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
          <button 
            type="submit" 
            disabled={loading}
            style={{
              flex: '1',
              padding: '12px 24px',
              fontSize: '16px',
              fontWeight: '500',
              backgroundColor: loading ? '#94a3b8' : '#42b5f5',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            {loading ? 'Updating...' : 'Update Profile'}
          </button>
          
          <button 
            type="button"
            onClick={() => navigate("/doctors/today-appointments")}
            disabled={loading}
            style={{
              flex: '1',
              padding: '12px 24px',
              fontSize: '16px',
              fontWeight: '500',
              backgroundColor: '#94a3b8',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
