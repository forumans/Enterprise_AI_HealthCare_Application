# Prompt: Frontend API Integration and Data Fetching

## Prompt
Implement API client and data-fetching patterns for `frontend/` that integrate cleanly with `backend/`.

### Requirements
1. Centralize HTTP request handling (`frontend/src/api/` or `frontend/src/api.ts`).
2. Inject auth token and tenant context where required.
3. Standardize error mapping from backend responses.
4. Gate debug logs behind environment flags only.
5. Add retry and timeout behavior for transient failures.

### Deliverables
- Typed API client methods for auth, appointments, users, reports, profiles.
- Shared response/error types in `frontend/src/types/`.
- API integration tests in `testing/integration/`.
- Operational guidance in `frontend/docs/api-integration.md`.

### Acceptance Criteria
- No feature page performs ad-hoc `fetch` logic without shared client.
- Production runtime has minimal log noise.
- API failures produce user-safe messages and developer-debuggable traces in non-prod.
