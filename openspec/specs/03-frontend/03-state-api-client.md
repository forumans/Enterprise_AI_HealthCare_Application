# Prompt: State Management, API Client, and Data Fetching

## Prompt

Implement state management and data fetching for the frontend using TanStack React Query v5 for server state and React Context for session/auth state.

---

### State Boundaries

| State type | Tool | Location | Persists on refresh? |
|-----------|------|----------|---------------------|
| Session / auth | React Context (`useState`) | `App.tsx` | No — intentional (XSS protection) |
| Server state (API data) | TanStack React Query | `hooks/` | Via cache (in-memory only) |
| Local UI state | `useState` / `useReducer` | In component | No |

---

### Token Storage Rule

The JWT access token is stored in **React Context** (in-memory), never `localStorage` or `sessionStorage`. Storing tokens in Web Storage exposes them to XSS attacks. On page refresh, the user sees the login screen — this is the correct behaviour.

---

### `useAuth` Hook

Manages login state, token, and user identity.

```typescript
// frontend/src/hooks/useAuth.ts
interface AuthState {
  token: string | null;
  role: string | null;
  userName: string;
  userId: string;
  tenantId: string;
}

const useAuth = () => {
  // Returns:
  return {
    token,       // JWT access token (null if not logged in)
    role,        // "PATIENT" | "DOCTOR" | "ADMIN" | null
    userName,    // Display name
    userId,
    tenantId,
    login,       // (response: LoginResponse) => void
    logout,      // () => void — clears context, redirects to /
  };
};
```

`login()` validates that the API-returned role matches the expected role before storing the token. If there is a mismatch (e.g. a PATIENT tries to log in as a DOCTOR), the session is NOT established.

---

### API Client (`frontend/src/api.ts`)

Centralized HTTP client. **All** backend calls go through here — no `fetch()` calls in components.

```typescript
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

function withAuth(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}
```

**Available methods:**

```typescript
export const api = {
  // Auth
  register: (payload) => request("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: ({ email, password }) => request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  forgotPassword: (email) => request("/api/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (payload) => request("/api/auth/reset-password", { method: "POST", body: JSON.stringify(payload) }),

  // Doctors
  getDoctors: () => request("/api/doctors"),
  getDoctorAvailability: (doctorId, date) => request(`/api/doctor/availability/${doctorId}/ndays?date=${date}`),
  getDoctorAppointments: (token) => request("/api/doctor/appointments/all", { headers: withAuth(token) }),
  getTodayAppointments: (token) => request("/api/doctor/appointments/today", { headers: withAuth(token) }),
  getDoctorProfile: (token) => request("/api/doctors/me", { headers: withAuth(token) }),
  updateDoctorProfile: (payload, token) => request("/api/doctor/profile", { method: "PUT", body: JSON.stringify(payload), headers: withAuth(token) }),

  // Appointments
  bookAppointment: (payload, token) => request("/api/appointments", { method: "POST", body: JSON.stringify(payload), headers: withAuth(token) }),
  getPatientAppointments: (token) => request("/api/patient/appointments/upcoming", { headers: withAuth(token) }),
  cancelAppointment: (id, token) => request(`/api/appointments/${id}`, { method: "DELETE", headers: withAuth(token) }),
  updateAppointmentStatus: (id, status, token) => request(`/api/appointments/${id}/status`, { method: "PUT", body: JSON.stringify({ status }), headers: withAuth(token) }),
  confirmAppointment: (id, token) => request(`/api/appointments/${id}/confirm`, { method: "POST", headers: withAuth(token) }),

  // Patient
  getPatientProfile: (token) => request("/api/patient/me", { headers: withAuth(token) }),
  getMedicalHistory: (token) => request("/api/patient/medical-history", { headers: withAuth(token) }),
  getPrescriptions: (token) => request("/api/patient/prescriptions", { headers: withAuth(token) }),
  getPatientDocuments: (token) => request("/api/patient/documents", { headers: withAuth(token) }),
  uploadDocument: (file, token) => { /* multipart/form-data upload */ },

  // Admin
  getAdminUsers: (token) => request("/api/admin/users", { headers: withAuth(token) }),
  deleteUser: (userId, token) => request(`/api/admin/users/${userId}`, { method: "DELETE", headers: withAuth(token) }),
  restoreUser: (userId, token) => request(`/api/admin/users/${userId}/restore`, { method: "POST", headers: withAuth(token) }),
  resetUserPassword: (payload, token) => request("/api/admin/reset-password", { method: "POST", body: JSON.stringify(payload), headers: withAuth(token) }),
  getAdminAppointments: (token) => request("/api/admin/appointments", { headers: withAuth(token) }),
  getAdminReports: (token) => request("/api/admin/reports", { headers: withAuth(token) }),
};
```

---

### React Query Setup

Wrap the app in `QueryClientProvider`:

```tsx
// main.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1000 * 60,  // 1 minute
      refetchOnWindowFocus: false,
    },
  },
});

root.render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);
```

---

### Custom Hooks (Data Fetching)

All data fetching uses `useQuery` or `useMutation` from React Query — never plain `useEffect` + `useState`.

```typescript
// hooks/useAppointments.ts
export const usePatientAppointments = (token: string) =>
  useQuery({
    queryKey: ["patient-appointments"],
    queryFn: () => api.getPatientAppointments(token),
    enabled: !!token,
  });

export const useBookAppointment = (token: string) =>
  useMutation({
    mutationFn: (payload) => api.bookAppointment(payload, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient-appointments"] });
    },
  });

// hooks/useUserData.ts
export const usePatientProfile = (token: string) =>
  useQuery({
    queryKey: ["patient-profile"],
    queryFn: () => api.getPatientProfile(token),
    enabled: !!token,
  });
```

---

### Debug Logging

Gate all API debug logs behind `VITE_ENABLE_DEBUG`:

```typescript
if (import.meta.env.VITE_ENABLE_DEBUG === "true") {
  console.debug("[API]", url, options);
}
```

Never log tokens, user IDs, or PHI.

---

### TypeScript Interfaces (`frontend/src/types/app.ts`)

Define interfaces for all API response shapes:

```typescript
interface LoginResponse { access_token: string; role: string; tenant_id: string; user_name: string; user_id: string; }
interface Doctor { id: string; full_name: string; specialty: string; }
interface Appointment { id: string; appointment_time: string; status: string; doctor_name?: string; patient_name?: string; notes?: string; }
interface MedicalRecord { id: string; symptoms: string; diagnosis: string; lab_results?: string; created_at: string; }
interface Prescription { id: string; medication_details: string; pharmacy_name?: string; created_at: string; }
interface PatientDocument { id: string; document_name: string; document_type: string; download_url: string; created_at: string; }
interface AdminUser { id: string; email: string; full_name: string; role: string; is_active: boolean; deleted_at?: string; }
```

---

### Deliverables

- `frontend/src/api.ts` — typed API client with all methods
- `frontend/src/hooks/useAuth.ts` — login, logout, token in context
- `frontend/src/hooks/useAppointments.ts` — appointment queries and mutations
- `frontend/src/hooks/useUserData.ts` — profile fetching
- `frontend/src/hooks/useNavigation.ts` — active view tracking for breadcrumbs/menu
- `frontend/src/types/app.ts` — all TypeScript interfaces
- `frontend/src/main.tsx` — QueryClientProvider setup

### Acceptance Criteria

- No component uses `useEffect` + `fetch` for data fetching — all via React Query hooks.
- Token is never stored in `localStorage`, `sessionStorage`, or any browser storage API.
- Query cache invalidates after mutations (e.g. booking an appointment refreshes the appointment list).
- Debug logs only appear when `VITE_ENABLE_DEBUG=true`.
- All API method return types are typed (no `any`).
- `npx tsc --noEmit` passes.
