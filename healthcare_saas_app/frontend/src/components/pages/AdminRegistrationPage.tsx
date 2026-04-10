/**
 * Admin Registration Page Component
 * Handles admin registration with validation and API integration
 * Used by existing admins to register new admin users
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
}

interface AdminRegistrationPageProps {
  auth: any;
}

export function AdminRegistrationPage({ auth }: AdminRegistrationPageProps) {
  const { status, setStatus } = useAuthContext();
  const navigate = useNavigate();
  
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

  // Clear any existing status messages when navigating to registration page
  useEffect(() => {
    setStatus("");
  }, [setStatus]);

  // Redirect if not authenticated as admin
  useEffect(() => {
    if (!auth.session.accessToken || auth.session.role !== "ADMIN") {
      navigate("/admin/login");
    }
  }, [auth.session.accessToken, auth.session.role, navigate]);

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
    
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }
    
    try {
      const result = await api.registerAdmin({
        fullName: fullName.trim(),
        email: email.trim(),
        password: password,
        phone: phone.trim(),
      }, auth.session.accessToken);
      
      setStatus(result.message);
      
      // Clear form after successful registration
      setFullName("");
      setEmail("");
      setPhone("");
      setPassword("");
      setSubmitAttempted(false);
      
    } catch (error) {
      setStatus(parseErrorMessage(error));
    }
  }

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <h2>Admin Registration</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        Register a new administrator to manage the healthcare system
      </p>
      
      {status && (
        <StatusMessage 
          message={status} 
          type={
            status.toLowerCase().includes('success') || 
            status.toLowerCase().includes('successfully') || 
            status.toLowerCase().includes('completed') ||
            status.toLowerCase().includes('registered') ||
            status.toLowerCase().includes('confirmed') ||
            status.toLowerCase().includes('updated') ||
            status.toLowerCase().includes('created')
              ? 'success' 
              : 'error'
          } 
        />
      )}

      <form onSubmit={handleSubmit} className="form-stack">
        <LabeledField
          id="admin-full-name"
          label="Full Name"
          helpText="Name must be 3-80 characters."
          value={fullName}
          onChange={setFullName}
          error={submitAttempted ? errors.fullName : undefined}
          autoComplete="off"
        />
        
        <LabeledField
          id="admin-email"
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
          id="admin-phone"
          label="Phone"
          helpText="Use 10-15 digits. Country code allowed."
          value={phone}
          onChange={setPhone}
          error={submitAttempted ? errors.phone : undefined}
          autoComplete="off"
        />
        
        <LabeledField
          id="admin-password"
          label="Password"
          helpText="Minimum 5 characters."
          value={password}
          onChange={setPassword}
          type="password"
          placeholder="Enter your password"
          error={submitAttempted ? errors.password : undefined}
          autoComplete="new-password"
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
            Register Admin
          </button>
        </div>
      </form>
    </section>
  );
}
