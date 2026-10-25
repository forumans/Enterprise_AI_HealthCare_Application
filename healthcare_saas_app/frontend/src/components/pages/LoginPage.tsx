/**
 * LoginPage Component
 * Handles login functionality for all user roles (Patient, Doctor, Admin)
 * Provides role-specific login forms and navigation
 */

import React from "react";
import { Link, useLocation } from "react-router-dom";
import { LabeledField } from "../common/LabeledField";
import { StatusMessage } from "../common/StatusMessage";
import { useAuthContext } from "../../contexts/AuthContext";
import { validateEmail } from "../../utils";
import { api } from "../../api";
import type { LoginRole } from "../../contexts/AuthContext";

interface LoginPageProps {
  role: LoginRole;
}

export function LoginPage({ role }: LoginPageProps) {
  const { loginForm, setLoginForm, handleLogin, status, setStatus } = useAuthContext();
  // Set when the user was signed out because the server ended their session
  const notice = (useLocation().state as { notice?: string } | null)?.notice ?? "";
  const [submitAttempted, setSubmitAttempted] = React.useState(false);
  // Admin login offers first-time setup only while the deployment has no administrator yet
  const [adminSetupRequired, setAdminSetupRequired] = React.useState(false);

  React.useEffect(() => {
    if (role !== "ADMIN") return;
    api.getAdminSetupStatus()
      .then(result => setAdminSetupRequired(result.setup_required))
      .catch(() => setAdminSetupRequired(false));
  }, [role]);

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
        return adminSetupRequired
          ? {
              title: "Admin Login",
              subtitle: "System administration and management",
              registerLink: "/admin/setup",
              registerText: "First time setup? Create the first administrator"
            }
          : {
              title: "Admin Login",
              subtitle: "System administration and management",
              registerLink: null,
              registerText: "Administrator accounts are created by an existing administrator"
            };
      case "SUPPORT_STAFF":
        return {
          title: "Support Staff Login",
          subtitle: "Manage appointments and availability on behalf of patients and doctors",
          registerLink: null,
          registerText: "Support staff accounts are created by an administrator"
        };
    }
  };

  const content = getRoleSpecificContent();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    setSubmitAttempted(true);
    
    // Validate email
    if (!validateEmail(loginForm.email)) {
      return; // Email validation will be handled by the form
    }
    
    // No password-length check here: the server decides (an older account may have a shorter password)
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

      {notice && !status && (
        <div role="status" style={{
          padding: '12px 14px',
          margin: '0 0 16px 0',
          borderRadius: '6px',
          borderLeft: '4px solid #f0a020',
          backgroundColor: 'rgba(240, 160, 32, 0.12)',
          color: '#ffd28a'
        }}>
          {notice}
        </div>
      )}
      
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
          Login as {role === "SUPPORT_STAFF" ? "Support Staff" : role.charAt(0) + role.slice(1).toLowerCase()}
        </button>
      </form>

      <div style={{ marginTop: '16px', textAlign: 'center' }}>
        <Link to="/forgot-password" style={{ color: '#42b5f5' }}>Forgot password?</Link>
      </div>

      <div style={{ marginTop: '12px', textAlign: 'center' }}>
        {content.registerLink ? (
          <Link to={content.registerLink} style={{ color: '#42b5f5' }}>
            {content.registerText}
          </Link>
        ) : (
          <span style={{ color: '#b4cce2' }}>{content.registerText}</span>
        )}
      </div>
    </section>
  );
}
