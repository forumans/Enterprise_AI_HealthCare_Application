# Prompt: Deployment Architecture

## Prompt
Design and implement production deployment using independent `infrastructure/` and `deployment/` projects.

### Target Platform
- Frontend: S3 + CloudFront
- Backend: ECS Fargate behind ALB
- Database: RDS PostgreSQL
- Secrets: AWS Secrets Manager

### Requirements
1. Keep environment separation (`dev`, `staging`, `prod`).
2. Use migration-first release flow for backend.
3. Provide health checks and rollout verification.
4. Ensure deployment is repeatable and automated.

### Deliverables
- Infra definitions under `infrastructure/` (Terraform preferred).
- Deploy scripts and docs under `deployment/`.
- Environment variable and secret mapping matrix.
- Smoke test checklist for post-deploy validation.

### Acceptance Criteria
- A new environment can be provisioned from code.
- Backend and frontend can be deployed independently.
- Rollback path is documented and tested.
