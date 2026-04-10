# CI Minimum Gates

These checks are the minimum required before merge and release.

## Global
- Formatting/lint checks pass.
- Secrets scan passes.
- Dependency vulnerability scan passes at configured threshold.

## Backend
- Unit tests pass.
- Critical integration tests pass.
- Migrations validate (`upgrade` path).
- Static typing/lint checks pass.

## Frontend
- Type checks pass.
- Unit tests pass.
- Build passes.
- No production-unsafe debug logging in runtime paths.

## Testing Project
- Integration smoke suite passes.
- E2E smoke suite passes for critical workflows.
- Security regression suite passes for RBAC/tenant isolation.

## Deployment
- Pipeline syntax/validation passes.
- Artifact version traceable to commit SHA.
- Rollback instructions present for release.
