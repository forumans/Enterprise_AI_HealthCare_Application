# Feature 01 — Home Page

**Roles:** everyone (guest and signed in) · **Route:** `/` · **Depends on:** F06 · **Traces to:** `AUTH-HOME-01…04`

## 1. Purpose

Public landing page that introduces the platform, offers the patient and doctor sign-in entry points, and shows
a "medical breakthroughs" news grid.

## 2. UI

Rendered inside `AppLayout` **without** a breadcrumb.

| Order | Element | Content / behavior |
|-------|---------|--------------------|
| 1 | `h1` | "Smart Healthcare Management Platform" |
| 2 | Lead paragraph (class `lead-text`) | "Manage doctors, patients, appointments, prescriptions, and billing from a single unified platform." |
| 3 | Button row (class `hero-actions`) | "Support Staff Login" → `/support/login` (hidden when the signed-in role is SUPPORT_STAFF); "Patient Login" → `/patients/login` (hidden when the signed-in role is PATIENT); "Doctor Login" → `/doctors/login` (always) |
| 4 | `h2` | "Latest Medical Breakthroughs" |
| 5 | Card grid (class `card-grid`) | 5 news cards; while loading, 5 empty skeleton cards (class `skeleton-card`) |

News card content: icon "🔬"; `h3` headline; muted line "📰 <source>"; summary paragraph; link "Read more →"
that opens `https://www.google.com/search?q=<encodeURIComponent(headline + ' ' + source)>` in a new tab with
`noopener,noreferrer` (anchor has `target="_blank" rel="noopener noreferrer"`; the click handler prevents
default and calls `window.open(url, '_blank', 'noopener,noreferrer')`).

## 3. Data source

`useMedicalNewsAgent()` — a TanStack Query (`queryKey ["medical-news-agent"]`, `staleTime` 15 min) whose fetcher
is pluggable. The reference fetcher waits 650 ms and returns these static cards (no backend call):

| id | headline | source | summary |
|----|----------|--------|---------|
| news-1 | AI model flags early-stage sepsis in ER triage workflows | HealthTech Daily | Multi-center trial reports a measurable reduction in delayed interventions when AI alerts are embedded at triage. |
| news-2 | Remote cardiac monitoring expands into rural community clinics | Clinical Wire | Low-cost wearables paired with care coordination teams reduced hospital readmissions by 11%. |
| news-3 | FHIR-based data exchange standardizes medication histories | Interop Journal | Regional providers reported faster medication reconciliation and fewer duplicate prescriptions. |
| news-4 | New guideline promotes proactive preventive screening reminders | Public Health Review | Automated reminder systems improved annual screening adherence in primary care cohorts. |
| news-5 | Digital therapeutic pilot shows improved diabetes outcomes | Med Outcomes | Patients using app-guided daily coaching recorded stronger HbA1c improvements over 6 months. |

## 4. Acceptance criteria

- **F01-HOME-AC-01** Given a guest, When opening `/`, Then "Support Staff Login", "Patient Login" and "Doctor Login" are shown in that order, with no breadcrumb.
- **F01-HOME-AC-02** Given a signed-in patient, When opening `/`, Then "Patient Login" is hidden.
- **F01-HOME-AC-04** Given signed-in support staff, When opening `/`, Then "Support Staff Login" is hidden.
- **F01-HOME-AC-03** Given the news is loading, Then 5 skeleton cards are shown; after load, 5 cards with
  "Read more →" links that open a new tab with `noopener`.

## 5. Reference implementation

`frontend/src/App.tsx` (`HomePage`), `frontend/src/hooks/useMedicalNewsAgent.ts`.
