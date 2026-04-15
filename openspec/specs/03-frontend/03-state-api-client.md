## ADDED Requirements

### Requirement: All API calls centralised in api.ts
Every backend HTTP call SHALL go through `frontend/src/api.ts`. No component or hook SHALL call `fetch()` directly. The client SHALL read the base URL from `VITE_API_BASE_URL` (empty string in production, `http://127.0.0.1:8000` in local dev).

#### Scenario: Component fetches data via hook not fetch
- **GIVEN** a page component that displays patient appointments
- **WHEN** the component's code is inspected
- **THEN** it SHALL call a custom hook (e.g. `usePatientAppointments`) and SHALL NOT contain any direct `fetch()` call

#### Scenario: API error propagates correctly
- **GIVEN** the backend returns a 401 response
- **WHEN** the API client receives the response
- **THEN** it SHALL throw an `Error` with the detail message from the response body, which React Query will surface as a query error

---

### Requirement: All data fetching via React Query hooks
All server state SHALL be managed by TanStack React Query v5. Components SHALL use `useQuery` for reads and `useMutation` for writes. Plain `useEffect` + `useState` + `fetch` SHALL NOT be used for data fetching.

#### Scenario: Appointments fetched with useQuery
- **GIVEN** the PatientAppointmentsPage
- **WHEN** the page mounts with a valid token
- **THEN** `useQuery` SHALL manage the loading, error, and data states for the appointments list

#### Scenario: Booking uses useMutation
- **GIVEN** the book-appointment form
- **WHEN** the patient submits the form
- **THEN** `useMutation` SHALL call `api.bookAppointment` and `onSuccess` SHALL invalidate the `["patient-appointments"]` query cache

---

### Requirement: React Query cache invalidation after mutations
WHEN a mutation succeeds, the system SHALL invalidate the relevant query cache keys so the UI automatically reflects the updated state without requiring a page refresh.

#### Scenario: Cache invalidated after booking
- **GIVEN** a patient books a new appointment
- **WHEN** the `bookAppointment` mutation succeeds
- **THEN** the `["patient-appointments"]` query SHALL be invalidated and the appointments list SHALL refetch automatically

#### Scenario: Cache invalidated after cancellation
- **GIVEN** a patient cancels an appointment
- **WHEN** the `cancelAppointment` mutation succeeds
- **THEN** the appointments list SHALL update to reflect the cancellation without a page reload

---

### Requirement: QueryClientProvider wraps the application
The application root SHALL be wrapped in `QueryClientProvider` with a `QueryClient` configured with `retry: 1`, `staleTime: 60000` (1 minute), and `refetchOnWindowFocus: false`.

#### Scenario: QueryClient available throughout app
- **GIVEN** `main.tsx` wraps `<App>` in `<QueryClientProvider>`
- **WHEN** any hook calls `useQuery` or `useMutation`
- **THEN** it SHALL have access to the shared `QueryClient` instance

---

### Requirement: Debug API logging gated behind VITE_ENABLE_DEBUG
Debug-level API logs SHALL only be emitted WHEN `VITE_ENABLE_DEBUG === "true"`. Tokens, user IDs, and PHI SHALL never appear in console output regardless of the debug flag.

#### Scenario: Debug logs suppressed in production
- **GIVEN** `VITE_ENABLE_DEBUG` is not set or is `"false"`
- **WHEN** any API call is made
- **THEN** no `console.debug` output SHALL appear in the browser console

#### Scenario: Debug logs appear in development
- **GIVEN** `VITE_ENABLE_DEBUG=true` in `.env.local`
- **WHEN** an API call is made
- **THEN** `console.debug` output SHALL include the request URL and method but SHALL NOT include the JWT token value

---

### Requirement: All API methods are fully typed with no `any`
Every function in `api.ts` SHALL have explicit TypeScript return types using the interfaces defined in `frontend/src/types/app.ts`. The `any` type SHALL NOT appear in API method signatures or return types.

#### Scenario: TypeScript compilation passes
- **GIVEN** the complete frontend codebase
- **WHEN** `npx tsc --noEmit` is run
- **THEN** it SHALL complete with zero type errors

---

### Requirement: useAuth hook manages login and logout
The `useAuth` hook SHALL expose `token`, `role`, `userName`, `userId`, `tenantId`, `login(response)`, and `logout()`. `login()` SHALL validate that the API-returned role matches the expected role before storing the token. `logout()` SHALL clear all auth state from context and redirect to `/`.

#### Scenario: Login stores identity in context
- **GIVEN** a successful login API response
- **WHEN** `login(response)` is called
- **THEN** `token`, `role`, `userName`, `userId`, and `tenantId` SHALL be stored in React Context and SHALL be accessible via `useAuth()` in any child component

#### Scenario: Logout clears all state
- **GIVEN** an authenticated session
- **WHEN** `logout()` is called
- **THEN** all auth state SHALL be set to null/empty and the router SHALL navigate to `/`
