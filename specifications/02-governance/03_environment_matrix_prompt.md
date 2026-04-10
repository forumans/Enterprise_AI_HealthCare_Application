# Prompt: Environment and Secrets Matrix

## Prompt
Create a complete environment variable and secret matrix for `dev`, `staging`, and `prod`.

### Requirements
1. Define all required env vars for frontend, backend, testing, infrastructure, and deployment.
2. Mark each variable as:
   - required/optional,
   - secret/non-secret,
   - source of truth (file, CI secret, Secrets Manager),
   - owner.
3. Add startup validation for required variables.
4. Ensure no secrets are committed to source control.

### Deliverables
- `deployment/env/environment-matrix.md`
- `.env.example` files per project with safe placeholders.
- Validation checks in backend startup and CI.

### Acceptance Criteria
- Missing required env vars fail fast with clear messages.
- Dev/staging/prod config differences are explicit and documented.
