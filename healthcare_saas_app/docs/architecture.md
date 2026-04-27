# System Architecture

## Overview

The application follows a serverless, cloud-native architecture on AWS. The frontend is a React SPA served from S3 via CloudFront. The backend is a FastAPI app running inside AWS Lambda, exposed through API Gateway HTTP API. A single PostgreSQL RDS instance stores all data.

---

## Production Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │              AWS CloudFront CDN              │
                        │  d_______________.cloudfront.net             │
                        │                                              │
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
                                                          │   Python 3.12, 512 MB   │
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
                                                          │   RDS PostgreSQL          │
                                                          │   db.t4g.micro            │
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

All datetimes in the system are stored and compared in **UTC**. This is critical because AWS Lambda's system clock runs in UTC, so any code that uses `datetime.now()` without an explicit timezone produces UTC on Lambda but local time on a developer's machine — causing silent comparison bugs.

### Rules

| Layer | Rule |
|---|---|
| Backend (Python) | Always use `datetime.now(timezone.utc).replace(tzinfo=None)` for "now". Never use `datetime.now()` or `datetime.utcnow()`. |
| Backend (parsing) | Parse incoming ISO strings with `datetime.fromisoformat(s.replace('Z', '+00:00'))`, then convert to UTC-naive via `.astimezone(timezone.utc).replace(tzinfo=None)`. |
| Database | Stores UTC-naive datetimes. No timezone column — UTC is the implicit contract. |
| Frontend (sending) | Slot times are sent as UTC ISO strings using `new Date(...).toISOString()` (e.g. `2026-04-28T19:00:00.000Z`). |
| Frontend (receiving) | Stored slot times returned from the API are UTC-naive strings. Append `Z` before passing to `new Date()` so the browser converts to local time correctly: `new Date(slotTime + 'Z')`. |

### Why naive UTC (not timezone-aware)?

SQLAlchemy's `DateTime` column (without `timezone=True`) stores and returns naive datetimes. Keeping everything as UTC-naive avoids SQLAlchemy/asyncpg timezone coercion surprises while still being unambiguous — as long as the UTC convention is consistently applied.

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
