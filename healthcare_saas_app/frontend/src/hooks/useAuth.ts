/**
 * Authentication Hook
 * Manages authentication state, login, logout, and user session data
 * Provides centralized authentication logic for the application
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { requireRole } from "../app/access";
import { getMainMenuFromPath } from "../config/menu";
import { delay, parseErrorMessage } from "../utils";
import { DEFAULT_COUNTRY, STATUS_MESSAGE_DURATION, INITIAL_STATUS_DURATION } from "../constants";
import type { SessionState, Role, LoginFormState, PatientRegistrationState, RegisterPayload } from "../types/app";

const initialSession: SessionState = { accessToken: "", role: "GUEST", tenantId: "" };

export function useAuth() {
  const [session, setSession] = useState<SessionState>(initialSession);
  const [status, setStatus] = useState("Ready.");
  const [loginForm, setLoginForm] = useState<LoginFormState>({ email: "", password: "" });
  const [patientRegistration, setPatientRegistration] = useState<PatientRegistrationState>({
    name: "",
    phone: "",
    insurance: "",
    policy: "",
    dateOfBirth: "",
    gender: "",
    addressLine1: "",
    addressLine2: "",
    city: "",
    state: "",
    postalCode: "",
    country: DEFAULT_COUNTRY
  });
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null);
  const navigate = useNavigate();

  // Handle navigation when session changes
  useEffect(() => {
    console.log('DEBUG: useAuth useEffect triggered:', {
      pendingNavigation,
      sessionRole: session.role,
      sessionRoleType: typeof session.role,
      isGuest: session.role === "GUEST",
      condition: pendingNavigation && session.role !== "GUEST"
    });
    
    if (pendingNavigation && session.role !== "GUEST") {
      console.log('DEBUG: Session updated, navigating to:', pendingNavigation);
      
      // Small delay to ensure state update has propagated
      setTimeout(() => {
        navigate(pendingNavigation);
        setPendingNavigation(null);
      }, 50);
    }
  }, [session, pendingNavigation, navigate]);

  // Auto-clear status message after duration
  useEffect(() => {
    if (status && status !== "Ready.") {
      const timer = setTimeout(() => {
        setStatus("");
      }, STATUS_MESSAGE_DURATION);
      
      return () => clearTimeout(timer);
    }
  }, [status]);

  // Clear initial "Ready." message after short delay
  useEffect(() => {
    const timer = setTimeout(() => {
      setStatus("");
    }, INITIAL_STATUS_DURATION);
    
    return () => clearTimeout(timer);
  }, []);

  /**
   * Handles user login for different roles
   */
  async function handleLogin(target: "PATIENT" | "DOCTOR" | "ADMIN") {
    try {
      console.log('DEBUG: Starting login for role:', target);
      const result = await api.login({ 
        email: loginForm.email, 
        password: loginForm.password, 
        remember_me: false 
      });
      
      console.log('DEBUG: Login result:', result);
      console.log('DEBUG: Result role type:', typeof result.role);
      console.log('DEBUG: Result role value:', result.role);
      
      const newSession = {
        accessToken: result.access_token,
        role: result.role,
        tenantId: result.tenant_id,
        userName: result.user_name,
        insuranceProvider: result.insurance_provider,
        insurancePolicyId: result.insurance_policy_id,
      };
      
      console.log('DEBUG: New session object:', newSession);
      
      setSession(newSession);
      
      console.log('DEBUG: Session set, navigating to dashboard...');
      
      // Navigate after a short delay to ensure state update
      setTimeout(() => {
        console.log('DEBUG: Delayed navigation, target role:', target);
        
        // Set pending navigation based on target role
        if (target === "PATIENT") {
          setPendingNavigation("/patients/appointments");
        } else if (target === "DOCTOR") {
          setPendingNavigation("/doctors/appointments");
        } else {
          setPendingNavigation("/admin/system-dashboard");
        }
      }, 100);
    } catch (error) {
      console.error('DEBUG: Login error:', error);
      setStatus(parseErrorMessage(error));
    }
  }

  /**
   * Handles user logout
   */
  function handleLogout() {
    setSession(initialSession);
    setStatus("Logged out successfully.");
    navigate("/");
    
    // Reset form states
    setLoginForm({ email: "", password: "" });
    resetPatientRegistration();
  }

  /**
   * Handles patient registration
   */
  async function registerPatient() {
    try {
      const payload: RegisterPayload = {
        fullName: patientRegistration.name,
        email: loginForm.email,
        phone: patientRegistration.phone,
        password: loginForm.password,
        insuranceProvider: patientRegistration.insurance,
        insurancePolicyNumber: patientRegistration.policy,
        dateOfBirth: patientRegistration.dateOfBirth || null,
        gender: patientRegistration.gender || null,
        addressLine1: patientRegistration.addressLine1 || null,
        addressLine2: patientRegistration.addressLine2 || null,
        city: patientRegistration.city || null,
        state: patientRegistration.state || null,
        postalCode: patientRegistration.postalCode || null,
        country: patientRegistration.country || null,
      };

      const result = await api.registerPatient(payload as unknown as Record<string, unknown>);
      setStatus(result.message);
      navigate("/patients/login");
      resetLoginForm();
      resetPatientRegistration();
    } catch (error) {
      setStatus(parseErrorMessage(error));
    }
  }

  /**
   * Resets login form to initial state
   */
  function resetLoginForm() {
    setLoginForm({ email: "", password: "" });
  }

  /**
   * Resets patient registration form to initial state
   */
  function resetPatientRegistration() {
    setPatientRegistration({
      name: "",
      phone: "",
      insurance: "",
      policy: "",
      dateOfBirth: "",
      gender: "",
      addressLine1: "",
      addressLine2: "",
      city: "",
      state: "",
      postalCode: "",
      country: DEFAULT_COUNTRY
    });
  }

  /**
   * Checks if the current user has the required role
   */
  function checkRole(requiredRoles: Role[]): string | null {
    return requireRole(session.role, requiredRoles);
  }

  return {
    // State
    session,
    status,
    loginForm,
    patientRegistration,
    pendingNavigation,
    
    // Actions
    setSession,
    setStatus,
    setLoginForm,
    setPatientRegistration,
    
    // API functions
    handleLogin,
    handleLogout,
    registerPatient,
    checkRole,
    resetLoginForm,
    resetPatientRegistration,
  };
}
