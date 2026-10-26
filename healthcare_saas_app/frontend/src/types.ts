export type Role = "GUEST" | "PATIENT" | "DOCTOR" | "ADMIN" | "SUPPORT_STAFF";

export interface SessionState {
  accessToken: string;
  role: Role;
  tenantId: string;
  userName?: string;
  insuranceProvider?: string;
  insurancePolicyId?: string;
  insurancePolicyNumber?: string;
  /** The clinic's IANA time zone; every time is shown in it */
  clinicTimezone?: string;
}

export interface LoginResponse {
  access_token: string;
  role: Role;
  tenant_id: string;
  user_name?: string;
  insurance_provider?: string;
  insurance_policy_id?: string;
  insurance_policy_number?: string;
  clinic_timezone?: string;
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

/** A patient search hit for support staff (GET /support/patients) - contact details only. */
export interface SupportPatientRow {
  id: string;
  name: string;
  phone: string;
  email: string;
  date_of_birth: string;
  gender: string;
  insurance_provider: string;
  city: string;
  state: string;
}

/** A user found on the admin Reset Password / Email screen (GET /admin/users/search). */
export interface AdminUserSearchRow {
  user_id: string;
  role: string;
  name: string;
  email: string;
  phone: string;
  /** Patients only; "" for other roles. */
  address: string;
  date_of_birth: string;
  /** Doctors only. */
  specialty: string;
  /** False once an admin deactivates the account (it can't log in). */
  is_active: boolean;
  /** True for the admin doing the search (who can't deactivate themselves). */
  is_self: boolean;
}

/** A doctor search hit for support staff (GET /support/doctors). */
export interface SupportDoctorRow {
  id: string;
  name: string;
  phone: string;
  email: string;
  specialty: string;
  license_number: string;
  /** False while the doctor's login is deactivated (e.g. awaiting approval): listed, but can't be booked. */
  is_active?: boolean;
}

/** An appointment as listed for support staff (GET /support/appointments). */
export interface SupportAppointmentRow {
  id: string;
  appointment_time: string;
  status: string;
  reason: string;
  patient_id: string;
  patient_name: string;
  doctor_id: string;
  doctor_name: string;
}

/** One hourly slot of GET /doctor/availability/{id}/all. Block fields are sent to doctors and staff only. */
export interface AvailabilitySlot {
  slot_time: string;
  status: "AVAILABLE" | "BOOKED" | "BLOCKED";
  block_id?: string | null;
  block_reason?: string | null;
  /** Booked, but the doctor has since blocked the hour: support staff should reschedule it. */
  needs_reschedule?: boolean;
}

export type BlockReasonCategory = "VACATION" | "CONFERENCE" | "SICK" | "PERSONAL" | "ADMINISTRATIVE" | "OTHER";

/** What a range block/unblock would do (preview), or did (apply). Times are UTC. */
export interface RangePreview {
  mode: "block" | "unblock";
  start: string;
  end: string;
  slots_to_create: number;
  created_blocked: number;
  to_block: number;
  already_blocked: number;
  to_flag: number;
  already_flagged: number;
  to_open: number;
  already_open: number;
  to_unflag: number;
  days_to_fill: number;
  appointments: Array<{ appointment_id: string; appointment_time: string; patient_name: string; status: string; needs_reschedule: boolean }>;
  /** Sent back to apply: the server refuses (409) if the schedule changed since this preview. */
  fingerprint: string;
}

/** A doctor's range block (GET /doctor/availability/{id}/blocks). */
export interface ScheduleBlockRow {
  id: string;
  start: string;
  end: string;
  reason_category: BlockReasonCategory;
  reason_label: string;
  reason_note: string | null;
  created_at: string;
  released_at: string | null;
  state: "ACTIVE" | "PARTIALLY_RELEASED" | "RELEASED";
  blocked_hours: number;
  needs_reschedule: number;
  opened_hours: number;
}

/** An appointment in the support staff "Needs Reschedule" queue (GET /support/reschedule-queue). */
export interface RescheduleQueueRow {
  id: string;
  appointment_time: string;
  status: string;
  /** Within the next 24 hours. */
  urgent: boolean;
  doctor_id: string;
  doctor_name: string;
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  patient_email: string;
  reason_category: BlockReasonCategory | null;
  reason_label: string;
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
