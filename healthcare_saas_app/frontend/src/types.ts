export type Role = "GUEST" | "PATIENT" | "DOCTOR" | "ADMIN";

export interface SessionState {
  accessToken: string;
  role: Role;
  tenantId: string;
  userName?: string;
  insuranceProvider?: string;
  insurancePolicyId?: string;
  insurancePolicyNumber?: string;
}

export interface LoginResponse {
  access_token: string;
  role: Role;
  tenant_id: string;
  user_name?: string;
  insurance_provider?: string;
  insurance_policy_id?: string;
  insurance_policy_number?: string;
}

export interface AppointmentRow {
  id: string;
  appointment_time?: string;
  starts_at?: string;
  doctor_name?: string;
  notes?: string;
  status?: string;
  note?: string;
  [key: string]: any;
}

export interface DoctorAppointmentRow {
  id: string;
  patient_name?: string;
  appointment_time?: string;
  starts_at?: string;
  notes?: string;
  status?: string;
  note?: string;
  [key: string]: any;
}

export interface AdminUserRow {
  id: string;
  role: Role;
  name?: string;
  email?: string;
  full_name?: string;
  phone?: string;
  [key: string]: any;
}

export interface AppointmentMetrics {
  total_appointments_to_date: number;
  total_appointments_year_to_date: number;
  total_appointments_this_month: number;
  total_appointments_this_week: number;
  total_appointments_today: number;
}

export interface PatientSearchRow {
  id: string;
  name: string;
  phone: string;
  dob: string;
  gender?: string;
  address?: string;
  prescription_date?: string;
  symptoms?: string;
  diagnosis?: string;
  lab_results?: string;
  medication?: string;
  [key: string]: any;
}
