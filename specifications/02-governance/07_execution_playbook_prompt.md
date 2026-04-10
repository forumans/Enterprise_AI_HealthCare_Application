# Prompt: Execution Playbook (Claude Code and Codex)

## Prompt
Create an execution playbook that tells contributors exactly how to run the prompt suite with Claude Code and OpenAI Codex.

### Required Sections
1. Recommended prompt order with rationale.
2. Tool-specific operating guidance:
   - small iterative runs,
   - verification checkpoints,
   - progress reporting cadence.
3. Output expectations per stage.
4. Stop/go criteria before moving to next stage.
5. Recovery steps for partial or interrupted runs.

### Recommended Order
1. `00-governance/*`
2. `01-master/*`
3. `02-database/*`
4. `03-backend/*`
5. `06-frontend/*`
6. `04-security/*`
7. `05-observability/*`
8. `07-testing/*`
9. `08-deployment/*`
10. `09-aws/*`

### Acceptance Criteria
- A new contributor can generate the platform incrementally without guessing sequence.
- Playbook minimizes long-running opaque tasks and encourages checkpointed execution.
