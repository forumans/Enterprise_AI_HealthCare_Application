# System Architecture

## Overview

The application follows a serverless, cloud-native architecture on AWS. The frontend is a React SPA served from S3 via CloudFront. The backend is a FastAPI app running inside AWS Lambda, exposed through API Gateway HTTP API. A single PostgreSQL RDS instance stores all data.

---

## Production Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │              AWS CloudFront CDN             │
                        │  d_______________.cloudfront.net            │
                        │                                             │
                        │  Default behavior  →  S3 (frontend assets)  │
                        │  /api/* behavior   →  API Gateway + Lambda  │
                        └─────────────────────────────────────────────┘
                                    │                    │
                    ┌───────────────┘                    └────────────────┐
                    ▼                                                     ▼
        ┌───────────────────┐                             ┌──────────────────────────┐
        │   S3 Bucket       │                             │  API Gateway HTTP API    │
        │  (React SPA)      │                             │  (any method, any path)  │
        │  index.html       │                             └──────────────────────────┘
        │  /assets/*.js     │                                          │
        │  /assets/*.css    │                                          ▼
        └───────────────────┘                             ┌──────────────────────────┐
                                                          │   AWS Lambda Function    │
                                                          │   Python 3.12, 512 MB    │
                                                          │                          │
                                                          │   Mangum (ASGI adapter)  │
                                                          │        ↕                 │
                                                          │   FastAPI App            │
                                                          │   ├─ Middleware stack    │
                                                          │   ├─ Route handlers      │
                                                          │   └─ SQLAlchemy async    │
                                                          └──────────────────────────┘
                                                                       │
                                                                       │ (VPC / port 5432)
                                                                       ▼
                                                          ┌──────────────────────────┐
                                                          │   RDS PostgreSQL         │
                                                          │   db.t4g.micro           │
                                                          │   Private VPC subnets    │
                                                          └──────────────────────────┘
                                                                       
                                                          ┌──────────────────────────┐
                                                          │   S3 Documents Bucket    │
                                                          │   (patient file uploads) │
                                                          └──────────────────────────┘
```

---

## Component Responsibilities

### CloudFront
- Serves the React frontend globally with edge caching
- Routes `/api/*` requests to API Gateway (no caching on API paths)
- Handles HTTPS termination
- Uses `AllViewerExceptHostHeader` origin request policy for API paths so the correct `Host` header is forwarded to API Gateway

### S3 (Frontend)
- Stores the compiled React app (`index.html`, JS bundles, CSS)
- Private bucket — accessed only through CloudFront via OAC (Origin Access Control)
- Custom error responses redirect all 403/404s to `index.html` (SPA routing)

### API Gateway HTTP API
- Lightweight, low-cost gateway (~$1 per 1M requests vs ~$3.50 for REST API)
- Single catch-all route (`ANY /{proxy+}`) forwards every request to Lambda
- CORS is **not** configured here — FastAPI's `CORSMiddleware` handles it entirely

### Lambda Function
- Runs the full FastAPI application on every invocation
- Uses [Mangum](https://mangum.faas.dev/) to translate API Gateway events to ASGI
- Placed inside the VPC so it can reach RDS on the private network
- Connection pool fixed at `pool_size=1, max_overflow=0` — each Lambda instance holds exactly one DB connection, preventing connection exhaustion when Lambda scales horizontally
- Entry point: `app.main.handler`

### RDS PostgreSQL
- Single `db.t4g.micro` instance (sufficient for current load)
- Private subnets only — not publicly accessible
- Lambda's security group is allowed inbound on port 5432

### S3 (Documents)
- Stores patient-uploaded documents
- Objects stored under key pattern: `documents/<tenant_id>/<patient_id>/<timestamp>_<filename>`
- Lambda IAM role has `s3:PutObject` and `s3:GetObject` on this bucket
- Download links are presigned URLs (1-hour expiry) generated at request time

---

## Local Development Architecture

```
Browser (http://127.0.0.1:5173)
        │
        │  HTTP requests with Bearer token
        ▼
Vite Dev Server (React)
        │
        │  fetch() to http://127.0.0.1:8000
        ▼
Uvicorn (FastAPI)
        │
        │  Middleware stack:
        │  1. SecurityHeadersMiddleware
        │  2. TenantContextMiddleware (JWT)
        │  3. AuditContextMiddleware
        │  4. CORSMiddleware
        ▼
PostgreSQL (localhost:5432)
```

In local development there is no Lambda, no API Gateway, and no CloudFront. Uvicorn serves the FastAPI app directly. File uploads go to the local filesystem (`backend/uploads/`) — in production they go to S3.

---

## Request Flow (Production)

### Frontend Asset Request
1. Browser requests `https://<cloudfront-domain>/`
2. CloudFront checks edge cache — serves from cache or fetches from S3
3. S3 returns `index.html` (or JS/CSS asset)
4. React app boots in the browser

### API Request (e.g. Patient books appointment)
1. React calls `POST /api/appointments` with `Authorization: Bearer <token>`
2. CloudFront matches `/api/*` behavior, forwards to API Gateway (strips `Host` header)
3. API Gateway invokes Lambda (cold start on first request, warm on subsequent)
4. Lambda runs Mangum → FastAPI processes the request:
   - `SecurityHeadersMiddleware` adds security headers
   - `TenantContextMiddleware` decodes JWT, validates claims, sets `request.state`
   - `AuditContextMiddleware` captures actor and method for audit logging
   - `CORSMiddleware` adds CORS headers
   - Route handler runs business logic, queries PostgreSQL via asyncpg
   - Audit log written to `audit_logs` table
5. Response travels back: Lambda → API Gateway → CloudFront → Browser

---

## Middleware Stack

Middleware executes in reverse registration order (last registered = first to process the request):

| Order | Middleware | Responsibility |
|---|---|---|
| 1st | `CORSMiddleware` | Add CORS headers to every response |
| 2nd | `AuditContextMiddleware` | Capture actor metadata for write operations |
| 3rd | `TenantContextMiddleware` | Decode JWT, set tenant/user/role context |
| 4th | `SecurityHeadersMiddleware` | Add security headers (last applied to response) |

---

## Multi-Tenancy

Every database table (except `tenants`) has a `tenant_id` column. All queries are filtered by the `tenant_id` extracted from the JWT. This means:

- A user from Tenant A can never read or modify data belonging to Tenant B
- Isolation is enforced at the middleware layer, not just at the application layer
- The default tenant is created automatically on the first user registration

---

## Datetime and Timezone Convention

All instants are stored and exchanged in **UTC**; all *calendar* logic (office hours, "today", weeks) happens in the **clinic's own time zone**. Every clinic (tenant) has an IANA zone in `tenants.timezone` (migration 008), so clinics anywhere in the world share one deployment. AWS Lambda's clock runs in UTC and a developer's machine doesn't, so code never relies on the process's local zone.

### Rules

| Layer | Rule |
|---|---|
| Database | Every timestamp column is `timestamptz` (migration 003) holding UTC. `tenants.timezone` holds the clinic's zone. |
| Backend "now" | `timeutils.utc_now()` (aware UTC). Never `datetime.now()` or `datetime.utcnow()`; never bind a naive datetime. |
| Backend parsing | `timeutils.parse_client_datetime()` turns any ISO string (with or without offset; naive means UTC) into aware UTC. |
| Backend clinic calendar | `clinic_today(tz)`, `clinic_day_bounds(day, tz)`, `clinic_week_bounds(day, tz)`, `default_slot_times(tz)` all take the zone explicitly. Routes pass `identity.clinic_tz`, which `get_current_identity` loads with the account check (no extra query). |
| API responses | ISO-8601 with offset (`+00:00`). Login also returns `clinic_timezone`. |
| Frontend | Shows every time and lays out every grid in the clinic's zone (`useClinicTimeZone()`), never the browser's. Calendar days are `{year, month, day}` values; grid cells are clinic wall-clock keys (`clinicSlotKey` / `slotKeyToDate`), and instants go to the API as `toISOString()`. Helpers live in `src/utils/index.ts` and use only `Intl`. Every calendar shows the zone under its heading with `<ClinicTimeNote />`. |

Frontend tests run with `TZ=Asia/Tokyo` (`vitest.config.ts`), a zone unlike any test clinic's, so code that slips back to the browser's zone fails.

---

## Security Layers

| Layer | Mechanism |
|---|---|
| Transport | HTTPS enforced by CloudFront |
| Authentication | JWT HS256 tokens, 30-minute expiry |
| Authorisation | RBAC via `require_roles()` dependency on each route |
| Multi-tenancy | `tenant_id` filtering on all queries |
| Password storage | PBKDF2-SHA256, 120,000 iterations, random 16-byte salt |
| Security headers | `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Cache-Control: no-store` |
| Input validation | Pydantic schemas on all request bodies |
| Audit trail | All write operations logged to `audit_logs` table |
