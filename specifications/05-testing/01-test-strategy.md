# Prompt: Test Strategy

## Prompt

Implement a full test suite covering unit, integration, end-to-end, and security testing for this Healthcare SaaS application.

---

### Test Pyramid

```
        /‾‾‾‾‾‾‾‾‾‾‾‾\
       /  E2E (Playwright) \       ← Few, critical user journeys
      /____________________\
     /  Integration Tests   \      ← API contracts, RBAC, tenant isolation
    /________________________\
   /   Unit Tests             \    ← Business logic, auth, utilities
  /____________________________\
```

---

### Backend Unit Tests (pytest)

**Location:** `backend/tests/`

**Tools:** `pytest`, `pytest-asyncio`, `httpx` (async test client)

**Coverage target:** 70% minimum; 90%+ for auth and RBAC modules.

Key test areas:

```
backend/tests/
├── test_auth.py          # JWT creation/validation, password hashing, middleware
├── test_rbac.py          # require_roles(): correct role, wrong role, cross-tenant
├── test_appointments.py  # book, cancel, confirm, status lifecycle
├── test_patients.py      # profile, medical history, prescriptions
├── test_doctors.py       # profile, availability slots
├── test_admin.py         # user management, reports
├── test_storage.py       # S3 upload/download (mocked boto3)
└── conftest.py           # DB fixtures, auth fixtures, test client
```

**Critical tests:**

```python
# test_rbac.py
async def test_patient_cannot_access_admin_endpoint(client, patient_token):
    response = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {patient_token}"})
    assert response.status_code == 403

async def test_cross_tenant_access_blocked(client, tenant_a_token, tenant_b_patient_id):
    response = await client.get(f"/api/patient/{tenant_b_patient_id}", headers={"Authorization": f"Bearer {tenant_a_token}"})
    assert response.status_code in (403, 404)

# test_auth.py
async def test_login_wrong_password_returns_401(client):
    response = await client.post("/api/auth/login", json={"email": "user@test.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

async def test_expired_token_returns_401(client, expired_token):
    response = await client.get("/api/patient/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
```

---

### Frontend Unit Tests (Vitest)

**Location:** `frontend/src/**/*.test.tsx`

**Tools:** `vitest`, `@testing-library/react`, `msw` (mock service worker for API mocking)

Key test areas:

```
frontend/src/
├── hooks/useAuth.test.ts          # login, logout, token storage (never localStorage)
├── hooks/useAppointments.test.ts  # booking, cancellation, cache invalidation
├── components/common/
│   ├── ProtectedRoute.test.tsx    # redirects unauthenticated, blocks wrong role
│   └── StatusMessage.test.tsx
└── utils/index.test.ts            # email validation, date formatting
```

**Critical tests:**

```typescript
// ProtectedRoute.test.tsx
test("redirects to / when no token", () => {
  render(<ProtectedRoute allowedRoles={["PATIENT"]} />);
  expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
});

// useAuth.test.ts
test("token is never stored in localStorage", () => {
  login(mockLoginResponse);
  expect(localStorage.getItem("token")).toBeNull();
  expect(sessionStorage.getItem("token")).toBeNull();
});
```

---

### Integration Tests

**Location:** `backend/tests/integration/` (pytest with real DB) or `healthcare_saas_app/` level

**Tools:** pytest, PostgreSQL test database (ephemeral, created per test run)

Test the full request-to-database path:

```python
# test_appointment_flow.py
async def test_full_booking_flow(client, patient_token, doctor_id, slot_id):
    # 1. Patient books appointment
    resp = await client.post("/api/appointments", json={"doctor_id": doctor_id, "slot_id": slot_id}, ...)
    assert resp.status_code == 200
    appointment_id = resp.json()["id"]

    # 2. Slot is now BOOKED
    slot = await db.get(DoctorAvailability, slot_id)
    assert slot.status == SlotStatus.BOOKED

    # 3. Doctor confirms
    resp = await client.post(f"/api/appointments/{appointment_id}/confirm", headers=doctor_headers)
    assert resp.status_code == 200

    # 4. Patient cancels
    resp = await client.delete(f"/api/appointments/{appointment_id}", headers=patient_headers)
    assert resp.status_code == 200

    # 5. Slot is back to AVAILABLE
    await db.refresh(slot)
    assert slot.status == SlotStatus.AVAILABLE
```

---

### End-to-End Tests (Playwright)

**Location:** `healthcare_saas_app/playwright.simple.config.ts`

**Requirement:** Both backend (port 8000) and frontend (port 5173) must be running.

Critical journeys:

```typescript
// e2e/patient-booking.spec.ts
test("patient books and cancels appointment", async ({ page }) => {
  await page.goto("/");
  await page.fill("[name=email]", "patient@test.com");
  await page.fill("[name=password]", "Password123");
  await page.click("[type=submit]");
  await page.waitForURL("**/patient/appointments");
  // ... book appointment
  // ... verify it appears in list
  // ... cancel it
});

// e2e/doctor-workflow.spec.ts
test("doctor sets availability and views appointments", async ({ page }) => { ... });

// e2e/admin-user-management.spec.ts
test("admin deletes and restores a user", async ({ page }) => { ... });
```

---

### Security Tests

Included in pytest (backend):

```python
# test_security.py
async def test_sql_injection_in_email(client):
    resp = await client.post("/api/auth/login", json={"email": "' OR 1=1 --", "password": "x"})
    assert resp.status_code in (401, 422)  # never 200

async def test_rate_limit_on_login(client):
    for _ in range(15):
        await client.post("/api/auth/login", json={"email": "x@x.com", "password": "wrong"})
    resp = await client.post("/api/auth/login", json={"email": "x@x.com", "password": "wrong"})
    assert resp.status_code == 429

async def test_no_account_enumeration(client):
    resp1 = await client.post("/api/auth/login", json={"email": "nonexistent@test.com", "password": "wrong"})
    resp2 = await client.post("/api/auth/login", json={"email": "real@test.com", "password": "wrong"})
    assert resp1.json()["detail"] == resp2.json()["detail"]  # same error message
```

---

### CI Gates

Minimum gates before merge:

| Check | Tool | Gate |
|-------|------|------|
| Backend lint | `ruff check` | Must pass |
| Backend type check | `mypy` | Must pass |
| Backend unit tests | `pytest` | Must pass, ≥ 70% coverage |
| Frontend type check | `tsc --noEmit` | Must pass |
| Frontend unit tests | `vitest` | Must pass |
| Frontend build | `npm run build` | Must pass |
| E2E smoke suite | `playwright` | Critical paths must pass |
| Secrets scan | `gitleaks` or equivalent | Must pass |

---

### Deliverables

- `backend/tests/` — all unit and integration test files
- `backend/tests/conftest.py` — database fixtures, auth token fixtures, test client setup
- `frontend/src/**/*.test.tsx` — component and hook tests
- `healthcare_saas_app/playwright.simple.config.ts` — Playwright E2E config
- `healthcare_saas_app/e2e/` or `frontend/tests/e2e/` — E2E test specs

### Acceptance Criteria

- All unit tests pass with `pytest` and `npm run test`.
- Full-booking integration test passes against a real (test) database.
- E2E patient booking journey passes end-to-end.
- RBAC negative tests pass (wrong role → 403).
- Cross-tenant isolation tests pass.
- No secrets appear in test fixtures.
