/**
 * Admin Patient Registration Page Component
 * Handles admin registration of new patients with validation and API integration
 * Used by admins to register new patient accounts
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
  dateOfBirth?: string;
  gender?: string;
  addressLine1?: string;
  city?: string;
  state?: string;
  postalCode?: string;
  insuranceProvider?: string;
  insurancePolicyNumber?: string;
}

interface AdminRegisterPatientPageProps {
  auth: any;
}

export function AdminRegisterPatientPage({ auth }: AdminRegisterPatientPageProps) {
  const navigate = useNavigate();
  
  const [status, setStatus] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [addressLine1, setAddressLine1] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [insuranceProvider, setInsuranceProvider] = useState("");
  const [insurancePolicyNumber, setInsurancePolicyNumber] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

  // Redirect if not authenticated as admin
  useEffect(() => {
    if (!auth.session.accessToken || auth.session.role !== "ADMIN") {
      navigate("/admin/login");
    }
  }, [auth.session.accessToken, auth.session.role, navigate]);

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
      setErrors(prev => ({
        ...prev,
        dateOfBirth: error || undefined
      }));
    }
  };

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitAttempted(true);
    
    console.log("Patient registration form submitted");
    
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
    if (!gender) {
      nextErrors.gender = "Gender is required.";
    }
    
    // Validate date of birth using the validation function
    const dateOfBirthError = validateDateOfBirth(dateOfBirth);
    if (dateOfBirthError) {
      nextErrors.dateOfBirth = dateOfBirthError;
    }
    
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      console.log("Form validation failed:", nextErrors);
      return;
    }
    
    console.log("Form validation passed, calling API...");
    
    try {
      const payload = {
        fullName: fullName.trim(),
        email: email.trim(),
        password: password,
        phone: phone.trim(),
        dateOfBirth: dateOfBirth || undefined,
        gender: gender || undefined,
        addressLine1: addressLine1.trim(),
        city: city.trim(),
        state: state.trim(),
        postalCode: postalCode.trim(),
        insuranceProvider: insuranceProvider.trim(),
        insurancePolicyNumber: insurancePolicyNumber.trim(),
      };
      
      console.log("API payload:", payload);
      console.log("Auth token:", auth.session.accessToken ? "Present" : "Missing");
      
      const result = await api.registerPatientAdmin(payload, auth.session.accessToken);
      
      console.log("Patient registration successful!");
      console.log("Full API response:", result);
      console.log("Response type:", typeof result);
      console.log("Response keys:", result ? Object.keys(result) : "null/undefined");
      console.log("result.message:", result?.message);
      console.log("result.message type:", typeof result?.message);
      
      // Check if result has message property
      if (result && result.message) {
        console.log("Setting status to:", result.message);
        setStatus(result.message);
      } else if (result && typeof result === 'string') {
        console.log("Result is a string, setting status to:", result);
        setStatus(result);
      } else {
        console.log("No message found in response, using default success message");
        setStatus("Patient registration successful!");
      }
      
      // Clear status message after 10 seconds
      setTimeout(() => {
        console.log("Clearing status message after 10 seconds");
        setStatus("");
      }, 10000); // 10 seconds
      
      // Clear form after successful registration with delay
      setTimeout(() => {
        console.log("Clearing form after delay");
        setFullName("");
        setEmail("");
        setPhone("");
        setPassword("");
        setDateOfBirth("");
        setGender("");
        setAddressLine1("");
        setCity("");
        setState("");
        setPostalCode("");
        setInsuranceProvider("");
        setInsurancePolicyNumber("");
        setSubmitAttempted(false);
      }, 3000); // 3 second delay before clearing form
      
    } catch (error) {
      console.log("Patient registration error:", error);
      const errorMessage = parseErrorMessage(error);
      console.log("Setting error status to:", errorMessage);
      setStatus(errorMessage);
      
      // Clear error message after 10 seconds
      setTimeout(() => {
        console.log("Clearing error message after 10 seconds");
        setStatus("");
      }, 10000); // 10 seconds
    }
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Register Patient</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        Register a new patient to manage their healthcare information and appointments
      </p>
      
      {status && (
        <>
          {console.log("Rendering status message:", status)}
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
        </>
      )}

      <form onSubmit={handleSubmit} className="form-stack">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <LabeledField
            id="patient-full-name"
            label="Full Name"
            helpText="Name must be 3-80 characters."
            value={fullName}
            onChange={setFullName}
            error={submitAttempted ? errors.fullName : undefined}
            autoComplete="off"
          />
          
          <LabeledField
            id="patient-email"
            label="Email"
            helpText="Use a valid email format, e.g., name@example.com."
            value={email}
            onChange={setEmail}
            type="email"
            placeholder="your.email@example.com"
            error={submitAttempted ? errors.email : undefined}
            autoComplete="off"
          />
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <LabeledField
            id="patient-phone"
            label="Phone"
            helpText="Use 10-15 digits. Country code allowed."
            value={phone}
            onChange={setPhone}
            error={submitAttempted ? errors.phone : undefined}
            autoComplete="off"
          />
          
          <LabeledField
            id="patient-password"
            label="Password"
            helpText="Minimum 5 characters."
            value={password}
            onChange={setPassword}
            type="password"
            placeholder="Enter password"
            error={submitAttempted ? errors.password : undefined}
            autoComplete="new-password"
          />
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <LabeledField
            id="patient-date-of-birth"
            label="Date of Birth"
            helpText="Select date from calendar"
            value={dateOfBirth}
            onChange={handleDateOfBirthChange}
            type="date"
            error={errors.dateOfBirth}
            autoComplete="off"
          />
          
          <LabeledField
            id="patient-gender"
            label="Gender"
            helpText="Select gender"
            value={gender}
            onChange={setGender}
            error={submitAttempted ? errors.gender : undefined}
            autoComplete="off"
          >
            <select 
              value={gender} 
              onChange={(e) => setGender(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">Select Gender</option>
              <option value="Male">Male</option>
              <option value="Female">Female</option>
              <option value="Other">Other</option>
            </select>
          </LabeledField>
        </div>
        
        <LabeledField
          id="patient-address-line1"
          label="Address Line 1"
          helpText="Street address"
          value={addressLine1}
          onChange={setAddressLine1}
          error={submitAttempted ? errors.addressLine1 : undefined}
          autoComplete="off"
        />
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
          <LabeledField
            id="patient-city"
            label="City"
            helpText="City name"
            value={city}
            onChange={setCity}
            error={submitAttempted ? errors.city : undefined}
            autoComplete="off"
          />
          
          <LabeledField
            id="patient-state"
            label="State"
            helpText="State or province"
            value={state}
            onChange={setState}
            error={submitAttempted ? errors.state : undefined}
            autoComplete="off"
          />
          
          <LabeledField
            id="patient-postal-code"
            label="Postal Code"
            helpText="ZIP or postal code"
            value={postalCode}
            onChange={setPostalCode}
            error={submitAttempted ? errors.postalCode : undefined}
            autoComplete="off"
          />
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <LabeledField
            id="patient-insurance-provider"
            label="Insurance Provider"
            helpText="Insurance company name (optional)"
            value={insuranceProvider}
            onChange={setInsuranceProvider}
            error={submitAttempted ? errors.insuranceProvider : undefined}
            autoComplete="off"
          />
          
          <LabeledField
            id="patient-insurance-policy-number"
            label="Insurance Policy Number"
            helpText="Policy number (optional)"
            value={insurancePolicyNumber}
            onChange={setInsurancePolicyNumber}
            error={submitAttempted ? errors.insurancePolicyNumber : undefined}
            autoComplete="off"
          />
        </div>
        
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
            Register Patient
          </button>
        </div>
      </form>
    </section>
  );
}
