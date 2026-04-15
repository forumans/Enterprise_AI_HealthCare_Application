# Prompt: Frontend Architecture and Routing

## Prompt

Implement the frontend as a React 18 + TypeScript + Vite SPA. It communicates with the FastAPI backend via a typed API client and uses React Router DOM v6 for client-side routing.

---

### Directory Structure

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
│   └── pages/                    # One component per route
│       ├── LoginPage.tsx
│       ├── PatientRegistrationPage.tsx
│       ├── DoctorRegistrationPage.tsx
│       ├── AdminRegistrationPage.tsx
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
│       └── AdminAppointmentsPage.tsx
├── hooks/
│   ├── useAuth.ts                # Login, logout, token and identity storage
│   ├── useAppointments.ts        # Appointment CRUD operations
│   ├── useUserData.ts            # User profile data fetching
│   └── useNavigation.ts          # Active view / navigation state
├── types/
│   └── app.ts                    # Shared TypeScript interfaces
├── constants/
│   └── index.ts                  # Countries list, timeout values
├── config/
│   └── menu.ts                   # Sidebar/navigation menu config
└── utils/
    └── index.ts                  # Email validation, date formatting
```

---

### Route Table

| Path | Component | Roles |
|------|-----------|-------|
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

### Protected Route

`ProtectedRoute` wraps any route that requires authentication. It reads from the `useAuth` hook and redirects to `/` if no token is present.

```tsx
// components/common/ProtectedRoute.tsx
const ProtectedRoute = ({ allowedRoles }: { allowedRoles: string[] }) => {
  const { token, role } = useAuth();
  if (!token) return <Navigate to="/" replace />;
  if (!allowedRoles.includes(role)) return <Navigate to="/" replace />;
  return <Outlet />;
};
```

---

### Auth State

The JWT token is stored in **React Context** (in-memory), never `localStorage`. On page refresh the user is redirected to login.

```tsx
// App.tsx — auth context setup
const [token, setToken] = useState<string | null>(null);
const [role, setRole] = useState<string | null>(null);
const [userName, setUserName] = useState<string>("");
const [tenantId, setTenantId] = useState<string>("");
```

---

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Backend base URL (local dev only — not needed in production) |
| `VITE_APP_NAME` | `Healthcare SaaS Platform` | App display name |
| `VITE_ENABLE_DEBUG` | `false` | Enables verbose API logging |

In production, the frontend is served via CloudFront which proxies `/api/*` to the Lambda backend. The `VITE_API_BASE_URL` is not needed — all API calls use relative paths (`/api/...`).

---

### Build Output

```bash
npm run build  # outputs to dist/
```

- `dist/index.html` — SPA entry point (CloudFront serves this for all non-asset paths via 403/404 error rule)
- `dist/assets/*.js` — hashed JS bundles
- `dist/assets/*.css` — hashed CSS bundles

---

### vite.config.ts

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,  // disable in production
  },
})
```

---

### Deliverables

- Complete `frontend/src/` directory matching the structure above
- All page components with at minimum a loading/error state and data display
- `ProtectedRoute` that blocks unauthenticated and wrong-role access
- `App.tsx` with all routes wired up
- `vite.config.ts` and `package.json` with correct dependencies

### Acceptance Criteria

- `npm run dev` starts the app at `http://127.0.0.1:5173`.
- `npm run build` produces a valid `dist/` directory.
- `npx tsc --noEmit` passes with no type errors.
- Unauthenticated users are redirected to `/` from any protected route.
- A PATIENT token cannot navigate to `/admin/*` or `/doctor/*` routes.
- Production build makes no requests to `localhost` — all API calls use `/api/` prefix.
