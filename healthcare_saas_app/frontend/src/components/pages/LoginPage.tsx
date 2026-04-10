/**
 * LoginPage Component
 * Handles login functionality for all user roles (Patient, Doctor, Admin)
 * Provides role-specific login forms and navigation
 */

import React from "react";
import { Link } from "react-router-dom";
import { LabeledField } from "../common/LabeledField";
import { StatusMessage } from "../common/StatusMessage";
import { useAuthContext } from "../../contexts/AuthContext";
import { validateEmail } from "../../utils";
import type { Role } from "../../types/app";

interface LoginPageProps {
  role: "PATIENT" | "DOCTOR" | "ADMIN";
}

export function LoginPage({ role }: LoginPageProps) {
  const { loginForm, setLoginForm, handleLogin, status, setStatus } = useAuthContext();
  const [submitAttempted, setSubmitAttempted] = React.useState(false);

  // Clear any existing status messages when navigating to login page
  React.useEffect(() => {
    setStatus("");
  }, [setStatus]);

  const getRoleSpecificContent = () => {
    switch (role) {
      case "PATIENT":
        return {
          title: "Patient Login",
          subtitle: "Access your medical records and appointments",
          registerLink: "/patients/register",
          registerText: "Don't have an account? Register"
        };
      case "DOCTOR":
        return {
          title: "Doctor Login", 
          subtitle: "Manage your appointments and patient consultations",
          registerLink: "/doctors/register",
          registerText: "New doctor? Register here"
        };
      case "ADMIN":
        return {
          title: "Admin Login",
          subtitle: "System administration and management",
          registerLink: "/admin/register-admin",
          registerText: "First time setup? Register admin"
        };
    }
  };

  const content = getRoleSpecificContent();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('🔍 DEBUG: Form submitted for role:', role);
    console.log('🔍 DEBUG: Email:', loginForm.email);
    console.log('🔍 DEBUG: Password length:', loginForm.password.length);
    
    setSubmitAttempted(true);
    
    // Validate email
    if (!validateEmail(loginForm.email)) {
      console.log('🔍 DEBUG: Email validation failed');
      return; // Email validation will be handled by the form
    }
    
    // Validate password (minimum 8 characters required)
    if (loginForm.password.length < 8) {
      console.log('🔍 DEBUG: Password validation failed');
      setStatus("Password must be at least 8 characters.");
      return;
    }
    
    console.log('🔍 DEBUG: Validation passed, calling handleLogin');
    handleLogin(role);
  };

  const emailError = submitAttempted && loginForm.email && !validateEmail(loginForm.email) 
    ? "Please enter a valid email address" 
    : "";

  return (
    <section>
      <h2>{content.title}</h2>
      <p style={{ color: '#b4cce2', marginBottom: '24px' }}>
        {content.subtitle}
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
          id="email"
          label="Email"
          helpText="Enter your registered email address"
          value={loginForm.email}
          onChange={(value) => setLoginForm(prev => ({ ...prev, email: value }))}
          type="email"
          placeholder="your.email@example.com"
          error={emailError}
          autoComplete="email"
        />

        <LabeledField
          id="password"
          label="Password"
          helpText="Enter your password"
          value={loginForm.password}
          onChange={(value) => setLoginForm(prev => ({ ...prev, password: value }))}
          type="password"
          placeholder="Enter your password"
          autoComplete="current-password"
        />

        <button 
          type="submit" 
          className="button-primary"
          disabled={!loginForm.email || !loginForm.password || !!emailError}
        >
          Login as {role.charAt(0) + role.slice(1).toLowerCase()}
        </button>
      </form>

      <div style={{ marginTop: '24px', textAlign: 'center' }}>
        <Link to={content.registerLink} style={{ color: '#42b5f5' }}>
          {content.registerText}
        </Link>
      </div>
    </section>
  );
}
