/**
 * Auth Context
 * Provides authentication state management across the application
 * Ensures single instance of auth state to prevent state synchronization issues
 */

import React, { createContext, useState, useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { requireRole } from "../app/access";
import { getMainMenuFromPath } from "../config/menu";
import { delay, parseErrorMessage } from "../utils";
import { DEFAULT_COUNTRY, STATUS_MESSAGE_DURATION, INITIAL_STATUS_DURATION } from "../constants";
import type { SessionState, Role, LoginFormState, PatientRegistrationState, RegisterPayload } from "../types/app";

const initialSession: SessionState = { accessToken: "", role: "GUEST", tenantId: "" };
const debugEnabled = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEBUG_LOGS === "true";

function debugLog(...args: unknown[]) {
  if (debugEnabled) {
    console.log(...args);
  }
}

interface AuthContextType {
  session: SessionState;
  status: string;
  loginForm: { email: string; password: string };
  patientRegistration: any;
  pendingNavigation: string | null;
  setSession: React.Dispatch<React.SetStateAction<SessionState>>;
  setStatus: React.Dispatch<React.SetStateAction<string>>;
  setLoginForm: React.Dispatch<React.SetStateAction<{ email: string; password: string }>>;
  setPatientRegistration: React.Dispatch<React.SetStateAction<any>>;
  handleLogin: (target: "PATIENT" | "DOCTOR" | "ADMIN") => Promise<void>;
  handleLogout: () => void;
  registerPatient: () => Promise<void>;
  checkRole: (requiredRoles: string[]) => string | null;
  resetLoginForm: () => void;
  resetPatientRegistration: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  
  // Auth state
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

  // Auto-clear status message after duration (but not for errors)
  useEffect(() => {
    if (status && status !== "Ready.") {
      // Add a small delay to ensure status is properly set before checking
      const timer = setTimeout(() => {
        // Don't auto-clear error messages (keep them persistent)
        const isError = status.includes("failed") || 
                       status.includes("Error") || 
                       status.includes("Authentication failed") ||
                       status.includes("registered as a") && status.includes("not a") && status.includes("Please use the");
        
        debugLog("Auto-clear status check:", { status, isError });
        
        // Success messages clear after 10 seconds, errors stay persistent
        const clearDelay = isError ? 0 : 10000;
        
        if (clearDelay > 0) {
          const clearTimer = setTimeout(() => {
            setStatus("");
          }, clearDelay);
          
          return () => clearTimeout(clearTimer);
        }
      }, 100); // Small delay to ensure status is properly set
      
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

  // Handle navigation when session changes
  useEffect(() => {
    if (pendingNavigation && session.role !== "GUEST") {
      // Small delay to ensure state update has propagated
      setTimeout(() => {
        navigate(pendingNavigation);
        setPendingNavigation(null);
      }, 50);
    }
  }, [session, pendingNavigation, navigate]);

  // Handle login
  async function handleLogin(target: "PATIENT" | "DOCTOR" | "ADMIN") {
    debugLog("Auth login requested for role:", target);
    
    try {
      const result = await api.login({ 
        email: loginForm.email, 
        password: loginForm.password, 
        remember_me: false 
      });
      
      debugLog("Login API result received.");
      
      // CRITICAL SECURITY: Validate that the returned role matches the target role
      if (result.role !== target) {
        debugLog("Role mismatch detected during login.", {
          expectedRole: target,
          actualRole: result.role,
        });
        
        // SECURITY: Always show generic message to prevent credential discovery
        const errorMessage = "Invalid credentials";
        setStatus(errorMessage);
        return; // Stop login process
      }
      
      const newSession = {
        accessToken: result.access_token,
        role: result.role,
        tenantId: result.tenant_id,
        userName: result.user_name,
        insuranceProvider: result.insurance_provider,
        insurancePolicyId: result.insurance_policy_id,
      };
      
      debugLog("Login succeeded. Updating session state.");
      setSession(newSession);
      
      // Clear any existing error messages on successful login
      setStatus("");
      
      // Navigate after a short delay to ensure state update
      setTimeout(() => {
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
      // Ensure we display a clean error message
      let errorMessage = "Authentication failed";
      if (error instanceof Error) {
        errorMessage = error.message;
        // If it's still in JSON format, extract the detail
        if (errorMessage.startsWith("{")) {
          try {
            const errorData = JSON.parse(errorMessage);
            errorMessage = errorData.detail || errorMessage;
          } catch {
            // Keep original message if parsing fails
          }
        }
      }
      
      debugLog("Login failed. Updating auth status.");
      
      // Use setTimeout to ensure React state update is processed
      setTimeout(() => {
        setStatus(errorMessage);
        debugLog("Auth status updated after failed login.");
      }, 0);
    }
  }

  // Handle logout
  function handleLogout() {
    setSession(initialSession);
    setStatus("Logged out successfully.");
    navigate("/");
    
    // Reset form states
    setLoginForm({ email: "", password: "" });
    resetPatientRegistration();
  }

  // Register patient
  async function registerPatient() {
    // Implementation here
  }

  // Check role
  function checkRole(requiredRoles: Role[]): string | null {
    return requireRole(session.role, requiredRoles);
  }

  // Reset forms
  function resetLoginForm() {
    setLoginForm({ email: "", password: "" });
  }

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

  const value = {
    session,
    status,
    loginForm,
    patientRegistration,
    pendingNavigation,
    setSession,
    setStatus,
    setLoginForm,
    setPatientRegistration,
    handleLogin,
    handleLogout,
    registerPatient,
    checkRole,
    resetLoginForm,
    resetPatientRegistration,
  };
  
  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuthContext must be used within an AuthProvider");
  }
  return context;
}
