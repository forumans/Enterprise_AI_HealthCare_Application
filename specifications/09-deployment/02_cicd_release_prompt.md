# Prompt: CI/CD and Release Engineering

## Prompt
Implement CI/CD in `deployment/` with reliable pipelines for `frontend/`, `backend/`, and `testing/`.

### Requirements
1. Separate backend and frontend workflows with clear path filters.
2. Enforce quality gates:
   - lint/type checks,
   - unit tests,
   - integration smoke tests.
3. Build and publish backend container to ECR.
4. Build and publish frontend static artifacts to S3 + CloudFront invalidation.
5. Run migrations safely before backend rollout.

### Deliverables
- GitHub Actions workflows under `deployment/github-actions/` (or `.github/workflows` with documentation).
- Release runbook in `deployment/runbooks/release.md`.
- Rollback runbook in `deployment/runbooks/rollback.md`.
- Versioning and changelog policy.

### Acceptance Criteria
- Pipeline failures are fast and informative.
- Production deploys require explicit branch/environment controls.
- Release artifact versions are traceable to commit SHA.
