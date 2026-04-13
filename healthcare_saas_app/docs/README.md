# Enterprise AI Healthcare SaaS — Documentation

A multi-tenant healthcare management platform built with React, FastAPI, PostgreSQL, and AWS serverless infrastructure.

---

## What This Application Does

The platform connects patients, doctors, and administrators in a single portal:

- **Patients** register, book appointments with doctors, view medical history, and access prescriptions
- **Doctors** manage their availability, confirm appointments, record diagnoses and prescriptions
- **Admins** manage users, monitor appointments, view reports, and maintain audit logs

Data is fully isolated per tenant, making the platform safe to deploy as a SaaS service with multiple healthcare organisations sharing the same infrastructure.

---

## Documentation Index

| Document | Description |
|---|---|
| [Architecture](architecture.md) | System design, AWS infrastructure, request flow |
| [API Reference](api-reference.md) | All backend endpoints with methods, paths, auth requirements |
| [Data Models](data-models.md) | Database schema, entities, and relationships |
| [Authentication](authentication.md) | JWT implementation, roles, RBAC, middleware |
| [Local Development](local-development.md) | How to run the full stack locally |
| [Deployment](deployment.md) | AWS SAM deployment guide |
| [Frontend Guide](frontend.md) | Frontend structure, pages, hooks, API client |

---

## Tech Stack at a Glance

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, React Router, TanStack Query |
| Backend | FastAPI (Python), SQLAlchemy 2.0 async, asyncpg |
| Database | PostgreSQL 12+ |
| Auth | JWT (HS256), PBKDF2-SHA256 password hashing |
| Cloud Compute | AWS Lambda (Python 3.12) + Mangum ASGI adapter |
| API Gateway | AWS API Gateway HTTP API |
| CDN / Frontend Hosting | AWS CloudFront + S3 |
| Document Storage | AWS S3 |
| Infrastructure as Code | AWS SAM (`template.yaml`) |

---

## Project Structure

```
Enterprise_AI_HealthCare_Application/
├── healthcare_saas_app/
│   ├── backend/                  # FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py           # App factory + Lambda handler
│   │   │   ├── api/routes/       # All route modules
│   │   │   ├── core/             # Config, DB, auth, storage
│   │   │   ├── middleware/       # JWT, audit, CORS, security headers
│   │   │   ├── models/           # SQLAlchemy ORM models
│   │   │   └── services/         # Business logic
│   │   ├── template.yaml         # AWS SAM deployment template
│   │   ├── requirements.txt      # Python dependencies
│   │   └── Dockerfile            # Container definition (local/ECS)
│   ├── frontend/                 # React frontend
│   │   ├── src/
│   │   │   ├── components/       # UI components
│   │   │   ├── hooks/            # Custom React hooks
│   │   │   ├── api.ts            # API client
│   │   │   └── App.tsx           # Root component and routing
│   │   └── package.json
│   ├── docs/                     # This documentation
│   └── migrations/               # SQL migration scripts
├── specifications/               # Specification-driven design docs
└── test_healthcare_saas_app/     # Integration and E2E tests
```

---

## Quick Start

See [Local Development](local-development.md) for the full setup guide.

```bash
# 1. Clone
git clone https://github.com/forumans/Enterprise_AI_HealthCare_Application.git
cd Enterprise_AI_HealthCare_Application

# 2. Backend
cd healthcare_saas_app/backend
pip install -r requirements.txt
# Configure .env (see local-development.md)
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd healthcare_saas_app/frontend
npm install && npm run dev
```

Backend runs at `http://127.0.0.1:8000` · Frontend at `http://127.0.0.1:5173`

---

## User Roles

| Role | Access Summary |
|---|---|
| `PATIENT` | Book appointments, view own records, upload documents |
| `DOCTOR` | Manage availability, confirm appointments, create medical records and prescriptions |
| `ADMIN` | Full system access — manage users, view reports, audit logs |

All roles require a valid JWT token. See [Authentication](authentication.md) for details.
