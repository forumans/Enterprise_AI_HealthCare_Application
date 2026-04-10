# Prompt: AWS Fast-Track Bootstrap (Step-by-Step)

## Prompt
Generate a fast-track AWS bootstrap plan for this Healthcare SaaS architecture with separate projects:
- `frontend/`
- `backend/`
- `testing/`
- `infrastructure/`
- `deployment/`

### Goal
Produce a practical first deployment path in approximately 15 minutes for a non-production trial environment.

### Required Steps
1. Validate prerequisites (AWS CLI, Docker, Node, Python, GitHub secrets).
2. Provision or verify:
   - ECR repo,
   - ECS cluster/service/task def,
   - RDS endpoint configuration,
   - S3 bucket + CloudFront distribution,
   - ALB target group and listener routing.
3. Configure secrets and environment variables.
4. Deploy backend then frontend.
5. Run smoke tests from `testing/`.

### Deliverables
- A concise command sequence with placeholders clearly marked.
- A “known pitfalls” list and quick fixes.
- Success criteria checklist (health endpoints, login flow, appointment flow).
- Rollback steps for backend and frontend.

### Acceptance Criteria
- New contributor can follow the checklist without hidden assumptions.
- Commands reference current repository structure.
- Output is safe for staging/demo and clearly labels production-hardening gaps.
