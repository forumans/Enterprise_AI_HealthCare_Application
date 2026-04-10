/**
 * Application-specific type definitions
 * This module contains all TypeScript interfaces and types used throughout the application
 */

import type { 
  AppointmentMetrics,
  AdminUserRow, 
  AppointmentRow, 
  DoctorAppointmentRow, 
  PatientSearchRow, 
  Role, 
  SessionState 
} from "../types";

// Re-export commonly used types from the main types file
export type {
  AppointmentMetrics,
  AdminUserRow,
  AppointmentRow,
  DoctorAppointmentRow,
  PatientSearchRow,
  Role,
  SessionState
};

// Application-specific types
export type MainMenu = "Home" | "Doctors" | "Patients" | "Admin";

export type FieldErrors = Record<string, string>;

export interface RegisterPayload {
  fullName: string;
  email: string;
  phone: string;
  password: string;
  specialty?: string; // Optional for doctor registration
  licenseNumber?: string; // Optional for doctor registration
  insuranceProvider?: string; // Optional for patient registration
  insurancePolicyNumber?: string; // Optional for patient registration
  dateOfBirth?: string; // Optional for patient registration
  gender?: string; // Optional for patient registration
  addressLine1?: string; // Optional for patient registration
  addressLine2?: string; // Optional for patient registration
  city?: string; // Optional for patient registration
  state?: string; // Optional for patient registration
  postalCode?: string; // Optional for patient registration
  country?: string; // Optional for patient registration
}

export interface SubmenuItem {
  to: string;
  label: string;
  requiresAuth?: boolean;
  role?: Role;
  hideWhenAuth?: boolean;
}

export type SubmenuMap = {
  [key in MainMenu]: SubmenuItem[];
};

// Form state interfaces
export interface LoginFormState {
  email: string;
  password: string;
}

export interface PatientRegistrationState {
  name: string;
  phone: string;
  insurance: string;
  policy: string;
  dateOfBirth: string;
  gender: string;
  addressLine1: string;
  addressLine2: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
}

export interface AppointmentBookingState {
  doctorId: string;
  slot: string;
  reason: string;
  appointmentId: string;
}

export interface ConsultationState {
  symptoms: string;
  diagnosis: string;
  labResults: string;
  medication: string;
  dosage: string;
  instructions: string;
}

// Component prop interfaces
export interface LabeledFieldProps {
  id: string;
  label: string;
  helpText: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  error?: string;
  autoComplete?: string;
  required?: boolean;
  children?: React.ReactNode;
}

export interface ProtectedRouteProps {
  allowed: Role[];
  role: Role;
  children: JSX.Element;
}

export interface StatusMessageProps {
  message: string;
  type?: 'success' | 'error';
}

// Navigation interfaces
export interface NavigationState {
  activeMainMenu: MainMenu;
  openMainMenu: MainMenu | null;
}

// Data loading states
export interface DataState {
  loading: boolean;
  error: string | null;
  success: string | null;
}
