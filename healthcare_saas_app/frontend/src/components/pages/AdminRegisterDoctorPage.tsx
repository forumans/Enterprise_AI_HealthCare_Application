/**
 * Admin Doctor Registration Page Component
 * Handles admin registration of new doctors with validation and API integration
 * Used by admins to register new doctor accounts
 */

import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { validateEmail, parseErrorMessage } from "../../utils";
import { LabeledField } from "../common/LabeledField";

interface FieldErrors {
  fullName?: string;
  email?: string;
  phone?: string;
  password?: string;
  specialty?: string;
  licenseNumber?: string;
  dateOfBirth?: string;
}

interface AdminRegisterDoctorPageProps {
  auth: any;
}

export function AdminRegisterDoctorPage({ auth }: AdminRegisterDoctorPageProps) {
  const navigate = useNavigate();
  
  const [status, setStatus] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

  // Redirect if not authenticated as admin
  useEffect(() => {
    if (!auth.session.accessToken || auth.session.role !== "ADMIN") {
      navigate("/admin/login");
    }
  }, [auth.session.accessToken, auth.session.role, navigate]);

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

  // Function to validate date of birth
  function validateDateOfBirth(dateOfBirth: string): string | null {
    if (!dateOfBirth) {
      return "Date of birth is required.";
    }
    
    const birthDate = new Date(dateOfBirth);
    const today = new Date();
    
    // Check if date is in the future
    if (birthDate > today) {
      return "Date of birth cannot be in the future.";
    }
    
    // Check if date is too old (more than 120 years)
    const maxAge = 120;
    const maxDate = new Date();
    maxDate.setFullYear(today.getFullYear() - maxAge);
    
    if (birthDate < maxDate) {
      return "Please enter a valid date of birth.";
    }
    
    return null;
  }

  // Real-time validation for date of birth
  const handleDateOfBirthChange = (value: string) => {
    setDateOfBirth(value);
    
    if (submitAttempted || value) {
      const error = validateDateOfBirth(value);
      const ageError = validateDoctorAge(value);
      setErrors(prev => ({
        ...prev,
        dateOfBirth: error || ageError || undefined
      }));
    }
  };

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitAttempted(true);
    
    const nextErrors: FieldErrors = {};
    
    // Validate all fields without early returns
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
    
    // Validate date of birth using the validation function
    const dateOfBirthError = validateDateOfBirth(dateOfBirth);
    const ageError = validateDoctorAge(dateOfBirth);
    if (dateOfBirthError || ageError) {
      nextErrors.dateOfBirth = dateOfBirthError || ageError;
    }
    
    // Set all errors at once
    setErrors(nextErrors);
    
    // Only proceed if no errors
    if (Object.keys(nextErrors).length > 0) {
      return;
    }
    
    try {
      const payload = {
        fullName: fullName.trim(),
        email: email.trim(),
        password: password,
        phone: phone.trim(),
        specialty: specialty.trim() || undefined,
        licenseNumber: licenseNumber.trim() || undefined,
        dateOfBirth: dateOfBirth || undefined,
      };
      
      const result = await api.registerDoctorAdmin(payload, auth.session.accessToken);
      
      // Check if result has message property
      if (result && result.message) {
        setStatus(result.message);
      } else if (result && typeof result === 'string') {
        setStatus(result);
      } else {
        setStatus("Doctor registration successful!");
      }
      
      // Clear status message after 10 seconds
      setTimeout(() => {
        setStatus("");
      }, 10000);
      
      // Clear form after successful registration with delay
      setTimeout(() => {
        setFullName("");
        setEmail("");
        setPhone("");
        setPassword("");
        setSpecialty("");
        setLicenseNumber("");
        setDateOfBirth("");
        setSubmitAttempted(false);
      }, 3000);
      
    } catch (error) {
      const errorMessage = parseErrorMessage(error);
      setStatus(errorMessage);
      
      // Clear error message after 10 seconds
      setTimeout(() => {
        setStatus("");
      }, 10000);
    }
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Register Doctor</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        Register a new doctor to manage appointments and provide healthcare services
      </p>
      
      {status && (
        <div 
          className="status" 
          style={{ 
            marginBottom: '20px', 
            padding: '12px', 
            borderRadius: '4px', 
            border: '1px solid',
            backgroundColor: status.toLowerCase().includes('success') || status.toLowerCase().includes('successful') 
              ? 'rgba(34, 197, 94, 0.1)' 
              : 'rgba(239, 68, 68, 0.1)',
            color: status.toLowerCase().includes('success') || status.toLowerCase().includes('successful') 
              ? '#22c55e' 
              : '#ef4444',
            borderColor: status.toLowerCase().includes('success') || status.toLowerCase().includes('successful') 
              ? 'rgba(34, 197, 94, 0.3)' 
              : 'rgba(239, 68, 68, 0.3)'
          }}
        >
          {status}
        </div>
      )}

      <form onSubmit={handleSubmit} className="form-stack">
        <LabeledField
          id="doctor-full-name"
          label="Full Name"
          helpText="Name must be 3-80 characters."
          value={fullName}
          onChange={setFullName}
          error={errors.fullName}
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
          error={errors.email}
          autoComplete="off"
        />
        
        <LabeledField
          id="doctor-phone"
          label="Phone"
          helpText="Use 10-15 digits. Country code allowed."
          value={phone}
          onChange={setPhone}
          error={errors.phone}
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
          error={errors.password}
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
          onChange={handleDateOfBirthChange}
          type="date"
          error={errors.dateOfBirth}
          autoComplete="off"
        />
        
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={() => navigate("/admin/system-dashboard")}
            style={{
              background: 'transparent',
              color: '#b4cce2',
              border: '1px solid #b4cce2',
              borderRadius: '4px',
              padding: '12px 24px',
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          
          <button
            type="submit"
            style={{
              background: '#42b5f5',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              padding: '12px 24px',
              fontSize: '14px',
              cursor: 'pointer',
              fontWeight: '500'
            }}
          >
            Register Doctor
          </button>
        </div>
      </form>
    </section>
  );
}
