# Prompt: React Components and UI System

## Prompt

Build a reusable component system for healthcare workflows. No external icon library — use text labels and Unicode symbols. No CSS framework dependency — use plain CSS or CSS modules.

---

### Shared / Common Components

#### `LabeledField.tsx`
Form input wrapper that renders a label, the input, and a validation error message.

```tsx
interface LabeledFieldProps {
  label: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}
```

#### `StatusMessage.tsx`
Success or error banner shown after an action.

```tsx
interface StatusMessageProps {
  type: 'success' | 'error' | 'info';
  message: string;
  onDismiss?: () => void;
}
```

#### `ProtectedRoute.tsx`
Role-aware route guard (see architecture spec).

---

### Layout Components

#### `AppHeader.tsx`
Top navigation bar. Shows:
- App name / logo
- Active section title
- User display name + role badge
- Logout button

```tsx
interface AppHeaderProps {
  userName: string;
  role: string;
  onLogout: () => void;
}
```

#### `AppLayout.tsx`
Page wrapper. Renders `AppHeader` + breadcrumb trail + `<Outlet />` for child routes.

```tsx
interface AppLayoutProps {
  userName: string;
  role: string;
  onLogout: () => void;
}
```

---

### Domain-Specific Components

#### Appointment Components
- **`AppointmentCard`** — shows appointment date, doctor/patient name, status badge, and action buttons (confirm / cancel)
- **`AppointmentStatusBadge`** — colored badge for SCHEDULED / CONFIRMED / COMPLETED / CANCELLED
- **`BookAppointmentForm`** — doctor selector, date picker, time slot selector, notes field

#### Availability Components
- **`AvailabilityCalendar`** — week view showing slot status (AVAILABLE / BOOKED / BLOCKED) for a doctor
- **`SlotStatusBadge`** — colored badge for slot status

#### Patient Components
- **`MedicalRecordCard`** — symptoms, diagnosis, lab results, appointment date
- **`PrescriptionCard`** — medication details, pharmacy name, linked medical record
- **`DocumentListItem`** — document name, type, upload date, download link

#### Admin Components
- **`UserRow`** — table row for user list: name, email, role, status, actions (delete / restore)
- **`AdminMetricsPanel`** — counts for users, appointments, and appointments by status

---

### Form Validation Patterns

All forms use controlled inputs with inline validation:

```tsx
const [errors, setErrors] = useState<Record<string, string>>({});

const validate = () => {
  const newErrors: Record<string, string> = {};
  if (!email) newErrors.email = "Email is required";
  if (!isValidEmail(email)) newErrors.email = "Invalid email format";
  if (password.length < 8) newErrors.password = "Password must be at least 8 characters";
  setErrors(newErrors);
  return Object.keys(newErrors).length === 0;
};
```

Never rely on `required` attribute alone — always validate in the submit handler.

---

### Loading and Error States

Every data-fetching page must handle three states:

```tsx
if (isLoading) return <div>Loading...</div>;
if (error) return <StatusMessage type="error" message="Failed to load data. Please try again." />;
// data is available — render normally
```

---

### Accessibility Baseline

- All form inputs have an associated `<label>` via `htmlFor` / `id` pairing.
- Buttons have descriptive text or `aria-label`.
- Color alone is never the only way to convey state (status badges also have text).
- Keyboard navigation works for all interactive elements.

---

### No External Icon Libraries

Do not use `lucide-react`, `react-icons`, or any other icon package. Use:
- Unicode symbols (✓, ✕, +, →, ...)
- Short text labels ("Edit", "Delete", "View")
- CSS-styled indicators (colored dots for status)

This avoids build errors and keeps the bundle small.

---

### Deliverables

- `frontend/src/components/common/` — LabeledField, StatusMessage, ProtectedRoute
- `frontend/src/components/layout/` — AppHeader, AppLayout
- `frontend/src/components/pages/` — all 15 page components (see routing spec)
- `frontend/src/utils/index.ts` — `isValidEmail()`, `formatDate()`, `formatDateTime()`
- `frontend/src/constants/index.ts` — countries list, API timeout values

### Acceptance Criteria

- All page components render without runtime errors.
- Forms show inline validation errors on submit with missing or invalid fields.
- Every page handles the loading and error states from React Query.
- No import from `lucide-react` or any icon package.
- `npx tsc --noEmit` passes with no errors.
