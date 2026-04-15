# Prompt: Middleware Stack, Lambda Configuration, and Rate Limiting

## Prompt

Implement the FastAPI application assembly, middleware stack, Lambda entry point, and resilience controls for this Healthcare SaaS backend.

---

### Application Assembly (`backend/app/main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.middleware.tenant_middleware import TenantContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.api.routes import auth, doctors, patients, appointments, admin, health
from app.core.config import settings

app = FastAPI(title="Healthcare SaaS API", version="1.0.0")

# Middleware order matters — outermost runs first on request, last on response
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers — each endpoint exposed both with and without /api prefix
for router in [auth.router, doctors.router, patients.router,
               appointments.router, admin.router, health.router]:
    app.include_router(router)
    app.include_router(router, prefix="/api")

# Lambda entry point — module-level so it is reused across warm invocations
handler = Mangum(app, lifespan="off")
```

**Why `lifespan="off"`:** FastAPI `lifespan` async context managers are not guaranteed to run correctly inside Lambda because Lambda does not guarantee shutdown. Disable it; initialise any resources at module level instead.

**Why CORS is in FastAPI, not API Gateway:** API Gateway must not be configured to add CORS headers. Doing so produces duplicate `Access-Control-Allow-Origin` headers which browsers reject.

---

### Application Configuration (`backend/app/core/config.py`)

All settings read from environment variables. Fail fast on startup if required values are missing.

```python
@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL")           # required
    jwt_secret: str = os.getenv("JWT_SECRET")               # required
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    db_schema_init_on_startup: bool = _env_flag("DB_SCHEMA_INIT_ON_STARTUP")
    # HOST/PORT used by Uvicorn in local dev only — ignored by Lambda
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    # S3 bucket for patient document uploads
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "")

settings = Settings()
```

**Environment variable reference:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | `postgresql+asyncpg://user:pass@host:5432/db` |
| `JWT_SECRET` | Yes | — | HS256 signing key (≥ 32 chars) |
| `JWT_ALGORITHM` | No | `HS256` | Token algorithm |
| `ACCESS_TOKEN_MINUTES` | No | `30` | Token TTL in minutes |
| `CORS_ORIGINS` | Yes | — | Comma-separated allowed origins |
| `DB_SCHEMA_INIT_ON_STARTUP` | No | `false` | `true` for local dev only |
| `S3_BUCKET_NAME` | Yes (Lambda) | `""` | Patient document bucket |
| `APP_ENV` | No | `dev` | `dev` \| `staging` \| `production` |
| `HOST` | No | `0.0.0.0` | Uvicorn bind host (local dev only) |
| `PORT` | No | `8000` | Uvicorn bind port (local dev only) |

---

### Request Context Propagation

Every request gets a unique `request_id` for log correlation. This is set by `TenantContextMiddleware` and accessible throughout the request lifecycle via `contextvars`.

```python
# Set on every request (including public paths)
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="")
_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")

def get_request_id() -> str: return _request_id.get()
def get_tenant_id() -> str: return _tenant_id.get()
```

---

### Rate Limiting

Protect sensitive endpoints from brute-force and abuse using an in-process token bucket. For Lambda, use a simple per-invocation counter backed by a shared cache (ElastiCache/Redis) or a lightweight in-memory approach for low-traffic deployments.

**Limits by endpoint:**

| Endpoint category | Limit |
|-------------------|-------|
| `POST /auth/login` | 10 requests / minute per IP |
| `POST /auth/forgot-password` | 5 requests / minute per IP |
| `POST /auth/reset-password` | 5 requests / minute per IP |
| All other endpoints | 100 requests / minute per token |

**Rate limit response:**
```json
HTTP 429 Too Many Requests
Retry-After: 60
{"detail": "Too many requests. Please retry after 60 seconds."}
```

**Implementation note for Lambda:** In-memory rate limiting per execution environment is not effective at scale (each Lambda container is independent). For production, use AWS WAF rate limiting rules on the API Gateway or CloudFront distribution — this is cheaper and more reliable than in-process solutions.

---

### Centralized Exception Handling

Register an exception handler that catches unhandled exceptions and returns a safe response:

```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."}
    )
```

Never expose stack traces or internal error details to clients.

---

### Deployment Context: Lambda + Mangum

The `handler = Mangum(app, lifespan="off")` at the bottom of `main.py` is the Lambda entry point. API Gateway invokes it as:

```json
{
  "FunctionName": "healthcare-backend-backend",
  "Handler": "app.main.handler"
}
```

The Lambda execution environment is re-used across warm invocations. Module-level objects (the `engine`, boto3 clients, the `app` instance) are created once per environment.

**Cold start behaviour:** First invocation after a new environment is provisioned takes ~1–2 seconds. Subsequent warm invocations are fast. `pool_pre_ping=True` on the DB engine detects stale connections after long idle periods.

---

### Deliverables

- `backend/app/main.py` — full app factory with middleware stack and `handler = Mangum(...)`
- `backend/app/core/config.py` — `Settings` dataclass reading from env
- `backend/app/middleware/tenant_middleware.py` — JWT extraction, public path bypass
- `backend/app/middleware/security_headers.py` — security response headers
- `backend/.env.example` — all env vars with documentation comments

### Acceptance Criteria

- `from app.main import handler` succeeds without errors.
- `GET /api/health` returns 200 with `{"status":"healthy"}`.
- A request missing the `Authorization` header to a protected path returns 401.
- A request to a public path (e.g. `POST /api/auth/login`) returns the correct response without a token.
- Security headers are present on every response.
- CORS preflight (`OPTIONS`) on `/api/auth/login` returns the correct `Access-Control-Allow-Origin`.
