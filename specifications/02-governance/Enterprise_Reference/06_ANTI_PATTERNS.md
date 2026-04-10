# Anti-Patterns to Avoid

## Planning/Execution
- Running all prompts at once without phase gates.
- Mixing unrelated phases in one long execution.
- Continuing after failing checkpoint verification.

## Architecture
- Collapsing project boundaries (`frontend/backend/testing/infrastructure/deployment`).
- Putting business logic directly in API route handlers.
- Duplicating API logic across frontend pages instead of shared client/hooks.

## Security
- Logging tokens, passwords, or PHI.
- Treating frontend role checks as sufficient authorization.
- Using broad wildcard CORS in production.

## Data
- Using `create_all` as production schema strategy.
- Writing migrations without rollback planning.
- Using real or sensitive data in seeds/tests.

## CI/CD
- Deploying without migration/version checks.
- No path filters (causing unnecessary pipeline churn).
- Missing rollback runbook for backend/frontend releases.
