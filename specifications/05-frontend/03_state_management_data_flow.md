# Prompt: Frontend State Management and Data Flow

## Prompt
Define and implement state boundaries and data flow for `frontend/`.

### Requirements
1. Separate state by scope:
   - session/auth state,
   - server state (API data),
   - local UI state.
2. Normalize key entities where needed (appointments, users, patients).
3. Avoid duplicated data-fetching logic across pages.
4. Keep token and tenant context propagation consistent.

### Deliverables
- State architecture in `frontend/src/contexts/`, `frontend/src/hooks/`, and `frontend/src/app/`.
- Conventions doc in `frontend/docs/state-management.md`.
- Tests in `testing/frontend/` for auth/session transitions and critical workflows.

### Acceptance Criteria
- Role changes and login/logout transitions are deterministic.
- No stale state leaks across tenant/session changes.
- Error, loading, and empty states are handled consistently.
