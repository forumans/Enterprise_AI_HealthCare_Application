# Prompt: Frontend Architecture

## Prompt
Implement the frontend as an independent `frontend/` project using React + TypeScript + Vite.

### Architecture Rules
1. Keep strict separation from `backend/`; communicate only via API contracts.
2. Organize by feature domains and shared UI primitives.
3. Support role-based navigation and route protection (`ADMIN`, `DOCTOR`, `PATIENT`).
4. Use environment-driven configuration (`VITE_API_BASE_URL`, feature flags).

### Required Structure
```text
frontend/src/
  app/
  api/
  components/
  contexts/
  hooks/
  pages/
  styles/
  types/
```

### Deliverables
- Route architecture with protected layouts by role.
- Session/auth context with secure defaults.
- Error/loading boundary strategy.
- Frontend architecture doc in `frontend/docs/frontend-architecture.md`.

### Acceptance Criteria
- App can run independently with mocked or real backend URL.
- Unauthorized route access is blocked and redirected.
- Production build output is static-host ready for S3/CloudFront.
