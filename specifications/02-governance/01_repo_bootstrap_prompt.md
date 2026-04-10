# Prompt: Repository Bootstrap

## Prompt
Create the initial repository baseline for a Healthcare SaaS system with strict multi-project boundaries:

```text
healthcare_saas_app/
  frontend/
  backend/
  testing/
  infrastructure/
  deployment/
  docs/specifications/
```

### Requirements
1. Initialize each project with independent tooling and lockfiles.
2. Add top-level and per-project README files with run commands.
3. Add `.editorconfig`, `.gitignore`, and formatting/lint defaults.
4. Add root task runner shortcuts for local developer workflows.
5. Keep cross-project dependencies explicit, never implicit.

### Deliverables
- Final directory tree.
- Bootstrap scripts for local setup.
- Version pinning policy for Node/Python/Terraform/tooling.

### Acceptance Criteria
- New contributor can run frontend, backend, and tests locally from docs only.
- Repo starts cleanly with no hidden manual setup.
