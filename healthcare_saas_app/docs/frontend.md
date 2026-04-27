# Frontend Guide

The frontend is a React 18 SPA built with TypeScript and Vite. It communicates with the FastAPI backend via a typed API client and uses React Router for client-side routing.

---

## Tech Stack

| Library | Version | Purpose |
|---|---|---|
| React | 18.3.1 | UI framework |
| TypeScript | 5.x | Type safety |
| Vite | 7.3.1 | Build tool and dev server |
| React Router DOM | 6.30.1 | Client-side routing |
| TanStack React Query | 5.90.5 | Server state management |
| Vitest | 4.0.18 | Unit tests |
| Playwright | Latest | End-to-end tests |

---

## Directory Structure

```
frontend/src/
├── api.ts                        # API client — all backend calls go through here
├── App.tsx                       # Root component: routing, auth state, navigation
├── main.tsx                      # React entry point
├── app/
│   ├── types.ts                  # View enum for navigation state
│   ├── access.ts                 # Role-to-view access control mapping
│   ├── breadcrumbs.ts            # Breadcrumb data structure
│   └── routeBreadcrumbs.ts       # Per-route breadcrumb definitions
├── components/
│   ├── common/
│   │   ├── LabeledField.tsx      # Form field with label + validation message
│   │   ├── ProtectedRoute.tsx    # Redirects unauthenticated users
│   │   └── StatusMessage.tsx     # Success / error banner
│   ├── layout/
│   │   ├── AppHeader.tsx         # Top navigation bar with user menu
│   │   └── AppLayout.tsx         # Page wrapper with header + breadcrumbs
│   └── pages/                    # One component per page/view
│       ├── LoginPage.tsx
│       ├── PatientRegistrationPage.tsx
│       ├── DoctorRegistrationPage.tsx
│       ├── PatientAppointmentsPage.tsx
│       ├── PatientMedicalHistoryPage.tsx
│       ├── PatientPrescriptionsPage.tsx
│       ├── PatientDocumentsPage.tsx
│       ├── PatientProfilePage.tsx
│       ├── DoctorAppointmentsPage.tsx
│       ├── DoctorAvailabilityPage.tsx
│       ├── DoctorProfilePage.tsx
│       ├── AdminDashboardPage.tsx
│       ├── AdminUsersPage.tsx
│       ├── AdminAppointmentsPage.tsx
│       └── [additional page components]
├── hooks/
│   ├── useAuth.ts                # Login, logout, token storage
│   ├── useAppointments.ts        # Appointment CRUD operations
│   ├── useUserData.ts            # User profile data fetching
│   └── useNavigation.ts          # Active view / navigation state
├── types/
│   └── app.ts                    # Shared TypeScript interfaces
├── constants/
│   └── index.ts                  # Countries list, timeout values
├── config/
│   └── menu.ts                   # Sidebar/navigation menu configuration
└── utils/
    └── index.ts                  # Email validation, date formatting helpers
```

---

## Routing

Routes are defined in `App.tsx` using React Router DOM v6. Role-based protection is applied via `ProtectedRoute`:

| Path | Component | Roles |
|---|---|---|
| `/` | `LoginPage` | Public |
| `/register` | `PatientRegistrationPage` | Public |
| `/doctors/register` | `DoctorRegistrationPage` | Public |
| `/admin/register` | `AdminRegistrationPage` | Public |
| `/patient/appointments` | `PatientAppointmentsPage` | PATIENT |
| `/patient/medical-history` | `PatientMedicalHistoryPage` | PATIENT |
| `/patient/prescriptions` | `PatientPrescriptionsPage` | PATIENT |
| `/patient/documents` | `PatientDocumentsPage` | PATIENT |
| `/patient/profile` | `PatientProfilePage` | PATIENT |
| `/doctor/appointments` | `DoctorAppointmentsPage` | DOCTOR |
| `/doctor/availability` | `DoctorAvailabilityPage` | DOCTOR |
| `/doctor/profile` | `DoctorProfilePage` | DOCTOR |
| `/admin/dashboard` | `AdminDashboardPage` | ADMIN |
| `/admin/users` | `AdminUsersPage` | ADMIN |
| `/admin/appointments` | `AdminAppointmentsPage` | ADMIN |

---

## API Client

**File:** `src/api.ts`

All backend calls go through the `request<T>()` function which handles authentication headers, base URL, and error propagation:

```typescript
// Core request function
async function request<T>(url: string, options?: RequestInit): Promise<T>

// Auth header helper
function withAuth(token: string): Record<string, string>
// Returns: { Authorization: "Bearer <token>" }
```

The base URL is read from `VITE_API_BASE_URL` (set in `.env.local` for development, `VITE_API_BASE_URL=/api` is unnecessary in production since CloudFront handles routing).

### Available API Methods

**Auth**
```typescript
api.register(payload)           // POST /auth/register
api.login({email, password})    // POST /auth/login  → returns { access_token, role, ... }
api.forgotPassword(email)       // POST /auth/forgot-password
api.resetPassword(payload)      // POST /auth/reset-password
```

**Doctors**
```typescript
api.getDoctors()                         // GET /doctors
api.getDoctorAvailability(doctorId, date) // GET /doctor/availability/:id/ndays
api.getDoctorAppointments(token)         // GET /doctor/appointments/all
api.getTodayAppointments(token)          // GET /doctor/appointments/today
api.getDoctorProfile(token)              // GET /doctors/me
api.updateDoctorProfile(payload, token)  // PUT /doctor/profile
```

**Appointments**
```typescript
api.bookAppointment(payload, token)                     // POST /appointments
api.getPatientAppointments(token)                       // GET /patient/appointments/upcoming
api.cancelAppointment(appointmentId, token)             // DELETE /appointments/:id
api.updateAppointmentStatus(appointmentId, status, token) // PUT /appointments/:id/status
api.confirmAppointment(appointmentId, token)            // POST /appointments/:id/confirm
```

**Patient**
```typescript
api.getPatientProfile(token)        // GET /patient/me
api.getMedicalHistory(token)        // GET /patient/medical-history
api.getPrescriptions(token)         // GET /patient/prescriptions
api.getPatientDocuments(token)      // GET /patient/documents
api.uploadDocument(file, token)     // POST /patient/documents
```

**Admin**
```typescript
api.getAdminUsers(token)                    // GET /admin/users
api.deleteUser(userId, token)               // DELETE /admin/users/:id
api.restoreUser(userId, token)              // POST /admin/users/:id/restore
api.resetUserPassword(payload, token)       // POST /admin/reset-password
api.getAdminAppointments(token)             // GET /admin/appointments
api.getAdminReports(token)                  // GET /admin/reports
```

### Datetime Handling

All slot times sent to the API must be **UTC ISO strings**. Use `new Date(...).toISOString()` — never manually construct a naive local-time string — so the backend always receives an unambiguous UTC timestamp.

Slot times returned from the API are UTC-naive strings (no `Z` suffix). Append `Z` before passing to `new Date()` so the browser converts to the user's local time correctly:

```typescript
// Correct — treats stored time as UTC, converts to local for display
const slotTime = new Date(apiSlotString + 'Z');
slotTime.getHours(); // local hour

// Wrong — treats stored UTC time as local time, off by the UTC offset
const slotTime = new Date(apiSlotString);
```

---

## Authentication Flow

1. User submits credentials on `LoginPage`
2. `useAuth` hook calls `api.login()` → receives `{ access_token, role, tenant_id, user_name, ... }`
3. Token stored in React context (not `localStorage` — avoids XSS token theft)
4. Token passed as argument to all subsequent API calls
5. On logout, context is cleared and user redirected to `/`

---

## Custom Hooks

### `useAuth`
Manages login state, token, and user identity.

```typescript
const { token, role, userName, login, logout } = useAuth()
```

### `useAppointments`
Provides appointment data and mutation functions.

```typescript
const { appointments, bookAppointment, cancelAppointment } = useAppointments(token)
```

### `useUserData`
Fetches profile data for the authenticated user.

```typescript
const { profile, isLoading } = useUserData(token, role)
```

### `useNavigation`
Tracks the active view/page for breadcrumbs and menu highlighting.

```typescript
const { activeView, setActiveView } = useNavigation()
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Backend base URL |
| `VITE_API_TIMEOUT` | `30000` | Request timeout in ms |
| `VITE_APP_NAME` | `Healthcare SaaS Platform` | App display name |
| `VITE_ENABLE_DEBUG` | `false` | Enables verbose API logging |
| `VITE_SENTRY_DSN` | — | Sentry error tracking DSN |
| `VITE_GOOGLE_ANALYTICS_ID` | — | GA tracking ID |

All variables are prefixed with `VITE_` to be exposed to the browser by Vite.

---

## Building for Production

```bash
cd healthcare_saas_app/frontend
npm run build
```

Output goes to `dist/`. The build is a standard static site:
- `dist/index.html` — entry point (served for all routes via CloudFront error rules)
- `dist/assets/*.js` — hashed JS bundles
- `dist/assets/*.css` — hashed CSS bundles

Deploy by uploading `dist/` to the S3 frontend bucket (see [Deployment Guide](deployment.md)).

---

## Running Tests

```bash
# Unit tests (Vitest)
npm run test

# Unit tests with coverage
npm run test:coverage

# E2E tests (Playwright — requires backend and frontend running)
npx playwright test --config=playwright.simple.config.ts

# View E2E report
npx playwright show-report
```
