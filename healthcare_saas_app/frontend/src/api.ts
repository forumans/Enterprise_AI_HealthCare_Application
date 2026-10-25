import type {
  AppointmentMetrics,
  AdminUserRow,
  AdminUserSearchRow,
  AppointmentRow,
  DoctorAppointmentRow,
  LoginResponse,
  PatientSearchRow,
  SupportAppointmentRow,
  SupportDoctorRow,
  SupportPatientRow,
} from "./types";

const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";
const debugEnabled = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEBUG_LOGS === "true";

function debugLog(...args: unknown[]) {
  if (debugEnabled) {
    console.log(...args);
  }
}

function debugError(...args: unknown[]) {
  if (debugEnabled) {
    console.error(...args);
  }
}

/**
 * Fired on `window` when a request that carried a login token gets 401: the server no longer
 * accepts the session (expired, or the account was deactivated/deleted/changed). AuthContext
 * listens for it and signs the user out.
 */
export const SESSION_ENDED_EVENT = "hc:session-ended";

export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  // Path only for debug logs: query strings carry search terms (names, emails, phone numbers)
  const logPath = url.split("?")[0];
  try {
    // Debug: Log the request details
    if (options?.headers && 'Authorization' in options.headers) {
      const authHeader = options.headers.Authorization as string;
      debugLog("Making authenticated request to:", `${baseUrl}${logPath}`);
      debugLog("Auth header present:", authHeader ? "Yes" : "No");
      debugLog("Auth header starts with Bearer:", authHeader.startsWith("Bearer ") ? "Yes" : "No");
    } else {
      debugLog("Making unauthenticated request to:", `${baseUrl}${logPath}`);
    }
    
    const response = await fetch(`${baseUrl}${url}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    debugLog(`Response status: ${response.status} ${response.statusText}`);

    if (!response.ok) {
      const errorText = await response.text();
      // The body may contain personal data, so only the status is logged
      debugError(`Request to ${logPath} failed with status ${response.status}`);

      const sentToken = Boolean(options?.headers && (options.headers as Record<string, string>).Authorization);
      if (response.status === 401 && sentToken) {
        window.dispatchEvent(new CustomEvent(SESSION_ENDED_EVENT));
      }
      
      // Try to parse JSON error to get the detail field
      try {
        const errorJson = JSON.parse(errorText);
        if (errorJson.detail) {
          throw new Error(errorJson.detail);
        }
      } catch {
        // If it's not JSON or doesn't have detail, throw the original error
        throw new Error(errorText || `HTTP ${response.status}: ${response.statusText}`);
      }
    }

    if (response.status === 204) {
      return undefined as T;
    }
    
    const data = await response.json() as T;
    return data;
  } catch (error) {
    if (error instanceof Error) {
      debugError(`Fetch error for ${logPath}:`, error);
      debugError("Error type:", error.constructor.name);
      debugError("Error message:", error.message);
    } else {
      debugError(`Fetch error for ${logPath}:`, error);
    }
    
    // Check if it's a network error
    if (error instanceof TypeError && error.message.includes('fetch')) {
      debugError("Network error detected - checking CORS and server status");
      throw new Error('Failed to fetch - please check your internet connection and ensure the server is running');
    }
    
    // Check if it's a CORS error
    if (error instanceof Error && error.message.includes('CORS')) {
      debugError("CORS error detected");
      throw new Error('CORS error - the server may not allow requests from this origin');
    }
    
    throw error;
  }
}

export function withAuth(token: string): Record<string, string> {
  if (!token) {
    debugError("No token provided to withAuth.");
  }
  return { Authorization: `Bearer ${token}` };
}

export const api = {
  registerPatient: (payload: Record<string, unknown>) =>
    request<{ message: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: { email: string; password: string; remember_me: boolean }) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, newPassword: string) =>
    request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  listWeeklyAppointments: (token: string, fromDate?: string) =>
    request<AppointmentRow[]>(`/appointments/week${fromDate ? `?from_date=${fromDate}` : ""}`, {
      method: "GET",
      headers: withAuth(token),
    }),

  /** The caller's appointments; includeCancelled also lists cancelled ones (status CANCELLED). */
  listAllAppointments: (token: string, includeCancelled = false) =>
    request<AppointmentRow[]>(`/appointments/all${includeCancelled ? "?include_cancelled=true" : ""}`, {
      method: "GET",
      headers: withAuth(token),
    }),

  getCurrentPatient: (token: string) =>
    request<{ id: string; name: string; email: string; phone: string; date_of_birth?: string; insurance_provider?: string; insurance_policy_number?: string; address?: string; emergency_contact?: string; emergency_phone?: string }>("/patient/me", {
      method: "GET",
      headers: withAuth(token),
    }),

  bookAppointment: (token: string, payload: { doctor_id: string; slot: string; reason: string; patient_id?: string }) =>
    request<{ id: string; status: string }>("/appointments", {
      method: "POST",
      headers: withAuth(token),
      body: JSON.stringify(payload),
    }),

  cancelAppointment: (token: string, appointmentId: string) =>
    request<{ message: string }>(`/appointments/${appointmentId}`, {
      method: "DELETE",
      headers: withAuth(token),
    }),

  /** The doctor's appointments in the clinic week containing fromDate, including cancelled ones. */
  doctorAllAppointments: (token: string, fromDate?: string) =>
    request<DoctorAppointmentRow[]>(`/doctor/appointments/all?include_cancelled=true${fromDate ? `&from_date=${fromDate}` : ""}`, {
      method: "GET",
      headers: withAuth(token),
    }),

  getDoctorMe: (token: string) =>
    request<any>("/doctors/me", {
      method: "GET",
      headers: withAuth(token),
    }),

  searchPatients: (token: string, q: string) =>
    request<PatientSearchRow[]>(`/patients/search?q=${encodeURIComponent(q)}`, {
      method: "GET",
      headers: withAuth(token),
    }),

  patientPrescriptionsFull: (token?: string, patientId?: string) => {
    debugLog('API: Making patientPrescriptionsFull call to /patient/prescriptions-full');
    debugLog('API: Token available:', !!token);
    debugLog('API: PatientId provided:', !!patientId);
    
    const url = patientId ? `/patient/prescriptions-full?patient_id=${patientId}` : '/patient/prescriptions-full';
    
    return request<Array<{
      appointment_time: string;
      doctor_name: string;
      appointment_status: string;
      appointment_note: string;
      symptoms: string;
      diagnosis: string;
      lab_results: string;
      medication_details: string;
      pharmacy_name: string;
      appointment_created_at: string;
    }>>(url, {
      method: "GET",
      headers: withAuth(token || ''),
    }).catch(error => {
      debugError('API: patientPrescriptionsFull error:', error);
      throw error;
    });
  },

  listAdminUsers: (token: string, page: number, pageSize: number) =>
    request<AdminUserRow[]>(`/admin/users?page=${page}&page_size=${pageSize}`, {
      method: "GET",
      headers: withAuth(token),
    }),

  listAdminAppointments: (token: string, page: number, pageSize: number) =>
    request<AppointmentRow[]>(`/admin/appointments?page=${page}&page_size=${pageSize}`, {
      method: "GET",
      headers: withAuth(token),
    }),

  reports: (token: string) =>
    request<Record<string, string | number>>("/admin/reports", {
      method: "GET",
      headers: withAuth(token),
    }),

  adminCreateUser: (
    token: string,
    payload: {
      role: "DOCTOR" | "PATIENT" | "ADMIN" | "SUPPORT_STAFF";
      full_name?: string;
      email: string;
      phone?: string;
      password: string;
      specialty?: string;
      license_number?: string;
      insurance_provider?: string;
      insurance_policy_number?: string;
      date_of_birth?: string;
      gender?: string;
      address_line1?: string;
      address_line2?: string;
      city?: string;
      state?: string;
      postal_code?: string;
      country?: string;
    },
  ) =>
    request<{ id: string }>("/admin/users", {
      method: "POST",
      headers: withAuth(token),
      body: JSON.stringify(payload),
    }),

  listDoctors: (token?: string) =>
    request<Array<{ id: string; name: string; specialty: string | null }>>("/doctors", {
      method: "GET",
      ...(token && { headers: withAuth(token) }),
    }),

  registerDoctor: (payload: { fullName: string; email: string; password: string; specialty?: string; licenseNumber?: string; phone?: string; dateOfBirth?: string }) => {
      const requestBody = {
        full_name: payload.fullName,
        email: payload.email,
        password: payload.password,
        specialty: payload.specialty,
        license_number: payload.licenseNumber,
        phone: payload.phone,
        date_of_birth: payload.dateOfBirth,
      };
      
      
      return request<{ message: string }>("/doctors/register", {
        method: "POST",
        body: JSON.stringify(requestBody),
      });
    },

  /** Public: whether the deployment still needs its first administrator. */
  getAdminSetupStatus: () =>
    request<{ setup_required: boolean }>("/admin/setup-status", { method: "GET" }),

  /** Public first-time setup: creates the first administrator (refused once any admin exists). */
  bootstrapAdmin: (payload: { full_name: string; email: string; password: string; timezone?: string }) =>
    request<{ message: string }>("/admin/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  registerAdmin: (payload: { fullName: string; email: string; password: string; phone?: string }, token?: string) =>
    request<{ message: string }>("/admin/users", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify({
        role: "ADMIN",
        full_name: payload.fullName,
        email: payload.email,
        password: payload.password,
        phone: payload.phone || "",
      }),
    }),

  registerPatientAdmin: (payload: { 
    fullName: string; 
    email: string; 
    password: string; 
    phone?: string;
    dateOfBirth?: string;
    gender?: string;
    addressLine1?: string;
    city?: string;
    state?: string;
    postalCode?: string;
    insuranceProvider?: string;
    insurancePolicyNumber?: string;
  }, token?: string) =>
    request<{ message: string }>("/admin/users", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify({
        role: "PATIENT",
        full_name: payload.fullName,
        email: payload.email,
        password: payload.password,
        phone: payload.phone || "",
        date_of_birth: payload.dateOfBirth || null,
        gender: payload.gender || null,
        address_line1: payload.addressLine1 || "",
        city: payload.city || "",
        state: payload.state || "",
        postal_code: payload.postalCode || "",
        insurance_provider: payload.insuranceProvider || "",
        insurance_policy_number: payload.insurancePolicyNumber || "",
      }),
    }),

  registerDoctorAdmin: (payload: { 
    fullName: string; 
    email: string; 
    password: string; 
    phone?: string;
    dateOfBirth?: string;
    specialty?: string;
    licenseNumber?: string;
    gender?: string;
    addressLine1?: string;
    city?: string;
    state?: string;
    postalCode?: string;
  }, token?: string) => {
      const requestBody = {
        role: "DOCTOR",
        full_name: payload.fullName,
        email: payload.email,
        password: payload.password,
        phone: payload.phone || "",
        date_of_birth: payload.dateOfBirth || null,
        specialty: payload.specialty || "",
        license_number: payload.licenseNumber || "",
        gender: payload.gender || null,
        address_line1: payload.addressLine1 || "",
        city: payload.city || "",
        state: payload.state || "",
        postal_code: payload.postalCode || "",
      };
      
            
      return request<{ message: string }>("/admin/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify(requestBody),
      });
    },

  listAllDoctorAvailability: (doctorId: string, token?: string) =>
    request<Array<{ slot_time: string; status: "AVAILABLE" | "BOOKED" | "BLOCKED" }>>(`/doctor/availability/${doctorId}/all?days=${30}`, {
      method: "GET",
      ...(token && { headers: withAuth(token) }),
    }),

  getCurrentTenant: (token: string) =>
    request<{ id: string; name: string; domain?: string; timezone: string }>("/tenants/current", {
      method: "GET",
      headers: withAuth(token),
    }),

  /** Admin: change the clinic's IANA time zone; open/blocked slots keep their local hours. */
  updateCurrentTenant: (token: string, payload: { timezone: string }) =>
    request<{ id: string; name: string; domain?: string; timezone: string; slots_moved: number }>("/tenants/current", {
      method: "PATCH",
      headers: withAuth(token),
      body: JSON.stringify(payload),
    }),

  confirmAppointment: (appointmentId: string, token?: string) =>
    request<{ message: string }>(`/appointments/${appointmentId}/confirm`, {
      method: "POST",
      ...(token && { headers: withAuth(token) }),
    }),

  updateAppointmentReason: (token: string, appointmentId: string, reason: string) =>
    request<{ id: string; reason: string; status: string }>(`/appointments/${appointmentId}`, {
      method: "PATCH",
      headers: withAuth(token),
      body: JSON.stringify({ reason }),
    }),

  getSupportProfile: (token: string) =>
    request<{ id: string; full_name: string; phone: string; email: string }>("/support/profile", {
      method: "GET",
      headers: withAuth(token),
    }),

  updateSupportProfile: (token: string, payload: { full_name: string; phone: string }) =>
    request<{ message: string; full_name: string; phone: string; email: string }>("/support/profile", {
      method: "PUT",
      headers: withAuth(token),
      body: JSON.stringify(payload),
    }),

  supportSearchDoctors: (token: string, q: string) =>
    request<SupportDoctorRow[]>(`/support/doctors?q=${encodeURIComponent(q)}`, {
      method: "GET",
      headers: withAuth(token),
    }),

  supportSearchPatients: (token: string, q: string) =>
    request<SupportPatientRow[]>(`/support/patients?q=${encodeURIComponent(q)}`, {
      method: "GET",
      headers: withAuth(token),
    }),

  supportListAppointments: (token: string, filter: { patientId?: string; doctorId?: string }) =>
    request<SupportAppointmentRow[]>(
      `/support/appointments?${filter.patientId ? `patient_id=${encodeURIComponent(filter.patientId)}` : `doctor_id=${encodeURIComponent(filter.doctorId ?? "")}`}`,
      { method: "GET", headers: withAuth(token) }
    ),

  rescheduleAppointment: (token: string, appointmentId: string, slot: string) =>
    request<{ id: string; appointment_time: string; status: string }>(`/appointments/${appointmentId}/reschedule`, {
      method: "POST",
      headers: withAuth(token),
      body: JSON.stringify({ slot }),
    }),

  getTodayAppointments: (token?: string) =>
    request<Array<{ id: string; doctor_id: string; time: string; patient_name: string; reason: string; status: string }>>('/doctor/appointments/today', {
      method: "GET",
      ...(token && { headers: withAuth(token) }),
    }),

  getAppointmentDetails: (appointmentId: string, token?: string) =>
    request<{ id: string; time: string; patient_id: string; patient_name: string; status: string; notes?: string }>(`/doctor/appointments/${appointmentId}`, {
      method: "GET",
      ...(token && { headers: withAuth(token) }),
    }),

  createMedicalRecord: (record: {
    appointment_id: string;
    patient_id: string;
    diagnosis: string;
    notes: string;
    lab_results?: string;
  }, token?: string) =>
    request<{ id: string; message: string }>('/medical-records', {
      method: "POST",
      headers: withAuth(token || ''),
      body: JSON.stringify(record),
    }),

  getMedicalRecordByAppointment: (appointmentId: string, token?: string) =>
    request<{ id: string; appointment_id: string; symptoms: string; diagnosis: string; lab_results: string | null }>(`/medical-records/${appointmentId}`, {
      method: "GET",
      headers: withAuth(token || ''),
    }),

  createPrescription: (prescription: {
    medical_record_id: string;
    medication_details: string;
    pharmacy_id?: string;
  }, token?: string) =>
    request<{ message: string }>('/prescriptions', {
      method: "POST",
      headers: withAuth(token || ''),
      body: JSON.stringify(prescription),
    }),

  completeAppointment: (appointmentId: string, token?: string) =>
    request<{ message: string }>(`/appointments/${appointmentId}/status`, {
      method: "PATCH",
      headers: {
        ...(token && { ...withAuth(token) }),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status: "COMPLETED" }),
    }),

  upsertDoctorAvailability: (doctorId: string, slotTime: string, isAvailable: boolean, token: string, blockReason?: string) => {
    const payload = {
      slot: slotTime,
      is_available: isAvailable,
      block_reason: blockReason,
      doctor_id: doctorId,
    };
    return request<{ message: string }>(`/doctor/availability`, {
      method: "POST",
      headers: withAuth(token),
      body: JSON.stringify(payload),
    });
  },

  deleteDoctorAvailability: (doctorId: string, slotTime: string, token: string) =>
    request<{ message: string }>(`/doctor/availability/${doctorId}`, {
      method: "DELETE",
      headers: withAuth(token),
      body: JSON.stringify({
        slot_time: slotTime,
      }),
    }),

  getDoctorProfile: (token: string) =>
    request<any>(`/doctor/profile`, {
      method: "GET",
      headers: withAuth(token),
    }),

  updateDoctorProfile: (token: string, payload: any) => {
      
      return request<{ message: string }>(`/doctor/profile`, {
        method: "PUT",
        headers: withAuth(token),
        body: JSON.stringify(payload),
      });
    },

  getPatientProfile: (token: string) =>
    request<any>(`/patient/patient/profile`, {
      method: "GET",
      headers: withAuth(token),
    }),

  updatePatientProfile: (token: string, payload: any) =>
    request<{ message: string }>(`/patient/patient/profile`, {
      method: "PUT",
      headers: withAuth(token),
      body: JSON.stringify(payload),
    }),

  getPharmacies: (token?: string) =>
    request<Array<{
      id: string;
      name: string;
      address: string;
      phone: string;
    }>>('/prescriptions/pharmacies', {
      method: "GET",
      headers: withAuth(token || ''),
    }).catch(error => {
      debugError('API: getPharmacies error:', error);
      throw error;
    }),

  adminSearchUsers: (token: string, role: string, q: string) =>
    request<AdminUserSearchRow[]>(`/admin/users/search?role=${encodeURIComponent(role)}&q=${encodeURIComponent(q)}`, {
      method: 'GET',
      headers: withAuth(token),
    }),

  adminResetPasswordById: (token: string, userId: string, newPassword: string) =>
    request<{ message: string; user_id: string; user_email: string; user_role: string }>(`/admin/users/${userId}/reset-password`, {
      method: 'POST',
      headers: withAuth(token),
      body: JSON.stringify({ new_password: newPassword }),
    }),

  adminSetUserActive: (token: string, userId: string, active: boolean) =>
    request<{ message: string; user_id: string; user_email: string; user_role: string; is_active: boolean }>(
      `/admin/users/${userId}/${active ? 'activate' : 'deactivate'}`,
      { method: 'POST', headers: withAuth(token) }
    ),

  adminChangeEmailById: (token: string, userId: string, newEmail: string) =>
    request<{ message: string; user_id: string; old_email: string; new_email: string; user_role: string }>(`/admin/users/${userId}/change-email`, {
      method: 'POST',
      headers: withAuth(token),
      body: JSON.stringify({ new_email: newEmail }),
    }),

  getResetPasswordRoles: (token: string) =>
    request<Array<{ value: string; label: string }>>('/admin/roles', {
      method: 'GET',
      headers: withAuth(token),
    }),

  // Admin Dashboard APIs
  getUsers: (token: string) =>
    request<any[]>('/admin/users', {
      method: 'GET',
      headers: withAuth(token),
    }),

  getAdminReports: (token: string) =>
    request<any>('/admin/reports', {
      method: 'GET',
      headers: withAuth(token),
    }),

  getAdminAppointmentMetrics: (token: string) =>
    request<AppointmentMetrics>('/admin/appointment-metrics', {
      method: 'GET',
      headers: withAuth(token),
    }),
};
