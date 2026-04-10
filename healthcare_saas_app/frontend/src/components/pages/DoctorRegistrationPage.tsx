/**
 * Doctor Registration Page Component
 * Handles doctor registration with validation and API integration
 * Provides a clean, modular interface for healthcare professional registration
 */

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useAuthContext } from "../../contexts/AuthContext";
import { validateEmail, parseErrorMessage } from "../../utils";
import { LabeledField } from "../common/LabeledField";
import { StatusMessage } from "../common/StatusMessage";

interface FieldErrors {
  fullName?: string;
  email?: string;
  phone?: string;
  password?: string;
  specialty?: string;
  licenseNumber?: string;
  dateOfBirth?: string;
}

interface DoctorRegistrationPageProps {
  auth: any;
}

export function DoctorRegistrationPage({ auth }: DoctorRegistrationPageProps) {
  const { status, setStatus } = useAuthContext();
  const navigate = useNavigate();
  
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [statusType, setStatusType] = useState<'success' | 'error'>('success');

  // Clear any existing status messages when navigating to registration page
  useEffect(() => {
    setStatus("");
    setStatusType('success'); // Reset to default
  }, [setStatus]);

  // Function to validate that doctor is at least 18 years old
  function validateDoctorAge(dateOfBirth: string): string | null {
    if (!dateOfBirth) {
      return "Date of birth is required.";
    }
    
    const birthDate = new Date(dateOfBirth);
    const today = new Date();
    
    // Calculate age
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    
    if (age < 18) {
      return `Doctor must be at least 18 years old. Current age: ${age}`;
    }
    
    return null;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitAttempted(true);
    
    const nextErrors: FieldErrors = {};
    if (fullName.trim().length < 3) {
      nextErrors.fullName = "Name must be at least 3 characters.";
    }
    if (!validateEmail(email)) {
      nextErrors.email = "Please provide a valid email address.";
    }
    if (!/^\+?[0-9\-\s]{10,15}$/.test(phone)) {
      nextErrors.phone = "Phone should be 10-15 digits.";
    }
    if (password.length < 5) {
      nextErrors.password = "Password must be at least 5 characters.";
    }
    
    // Validate doctor age (must be at least 18 years old)
    const ageError = validateDoctorAge(dateOfBirth);
    if (ageError) {
      nextErrors.dateOfBirth = ageError;
    }
    
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }
    
    try {
      const payload = {
        fullName: fullName.trim(),
        email: email.trim(),
        phone: phone.trim(),
        password: password,
        specialty: specialty.trim() || undefined,
        licenseNumber: licenseNumber.trim() || undefined,
        dateOfBirth: dateOfBirth || undefined,
      };
      
      console.log("🔍 DEBUG: Doctor registration form payload:", payload);
      console.log("🔍 DEBUG: Phone from form:", payload.phone);
      
      const result = await api.registerDoctor(payload);
      console.log("🔍 DEBUG: Doctor registration result:", result);
      
      setStatus(result.message);
      setStatusType('success'); // Success message
      
      // Navigate to login after successful registration
      setTimeout(() => {
        navigate("/doctors/login");
      }, 2000);
    } catch (error) {
      setStatus(parseErrorMessage(error));
      setStatusType('error'); // Error message
    }
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Doctor Registration</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        Register as a healthcare provider to manage appointments and consultations
      </p>
      
      {status && (
        <StatusMessage 
          message={status} 
          type={statusType}
        />
      )}

      <form onSubmit={handleSubmit} className="form-stack">
        <LabeledField
          id="doctor-full-name"
          label="Full Name"
          helpText="Name must be 3-80 characters."
          value={fullName}
          onChange={setFullName}
          error={submitAttempted ? errors.fullName : undefined}
          autoComplete="off"
        />
        
        <LabeledField
          id="doctor-email"
          label="Email"
          helpText="Use a valid email format, e.g., name@example.com."
          value={email}
          onChange={setEmail}
          type="email"
          placeholder="your.email@example.com"
          error={submitAttempted ? errors.email : undefined}
          autoComplete="off"
        />
        
        <LabeledField
          id="doctor-phone"
          label="Phone"
          helpText="Use 10-15 digits. Country code allowed."
          value={phone}
          onChange={setPhone}
          error={submitAttempted ? errors.phone : undefined}
          autoComplete="off"
        />
        
        <LabeledField
          id="doctor-password"
          label="Password"
          helpText="Minimum 5 characters."
          value={password}
          onChange={setPassword}
          type="password"
          placeholder="Enter your password"
          error={submitAttempted ? errors.password : undefined}
          autoComplete="new-password"
        />
        
        <LabeledField
          id="doctor-specialty"
          label="Specialty"
          helpText="Medical specialty (optional)."
          value={specialty}
          onChange={setSpecialty}
          autoComplete="off"
        />
        
        <LabeledField
          id="doctor-license-number"
          label="License Number"
          helpText="Medical license number (optional)."
          value={licenseNumber}
          onChange={setLicenseNumber}
          autoComplete="off"
        />
        
        <LabeledField
          id="doctor-date-of-birth"
          label="Date of Birth"
          helpText="Doctor must be at least 18 years old"
          value={dateOfBirth}
          onChange={setDateOfBirth}
          type="date"
          error={submitAttempted ? errors.dateOfBirth : undefined}
          autoComplete="off"
        />
        
        <button 
          type="submit" 
          className="button-primary"
          style={{ 
            padding: '12px 24px',
            fontSize: '16px',
            fontWeight: '500',
            backgroundColor: '#42b5f5',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            marginTop: '16px'
          }}
        >
          Register
        </button>
      </form>
      
      <div style={{ textAlign: 'center', marginTop: '20px' }}>
        <span style={{ color: '#b4cce2' }}>Already have an account? </span>
        <button 
          type="button"
          onClick={() => navigate("/doctors/login")}
          style={{
            background: 'none',
            border: 'none',
            color: '#42b5f5',
            textDecoration: 'underline',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          Sign In
        </button>
      </div>
    </section>
  );
}
