# Prompt: Frontend State Management and Data Flow

## Prompt
Define and implement state boundaries and data flow for `frontend/`.

### State Libraries

| State type | Tool | Location |
|-----------|------|----------|
| Session / auth state | React Context (`AuthContext`) | `frontend/src/contexts/` |
| Server state (API data) | **TanStack React Query v5** (`useQuery`, `useMutation`) | `frontend/src/hooks/` |
| Local UI state | `useState` / `useReducer` | In component |

Use **TanStack React Query** for all server-side data fetching. Do not use plain `useEffect` + `useState` for API calls. React Query handles caching, background refetching, loading states, and error states consistently.

### Token Storage

The JWT access token must be stored in **React Context** (in-memory), never in `localStorage` or `sessionStorage`. Storing tokens in Web Storage exposes them to XSS. On page refresh the user must re-authenticate.

### Requirements
1. Separate state by scope:
   - session/auth state (React Context — token, role, user identity),
   - server state (TanStack React Query — appointments, profile, medical history, etc.),
   - local UI state (component-local — form values, modal open/close).
2. Normalize key entities where needed (appointments, users, patients).
3. Avoid duplicated data-fetching logic across pages — all API calls go through named hooks in `hooks/`.
4. Keep token and tenant context propagation consistent — token is passed as argument to all API calls, sourced from `useAuth()`.

### Deliverables
- State architecture in `frontend/src/contexts/`, `frontend/src/hooks/`, and `frontend/src/app/`.
- Conventions doc in `frontend/docs/state-management.md`.
- Tests in `testing/frontend/` for auth/session transitions and critical workflows.

### Acceptance Criteria
- Role changes and login/logout transitions are deterministic.
- No stale state leaks across tenant/session changes.
- Error, loading, and empty states are handled consistently.
