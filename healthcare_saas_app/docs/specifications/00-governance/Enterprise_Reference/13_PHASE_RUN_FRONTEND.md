# Phase Run: Frontend

Implement this phase only:
- `docs/specifications/06-frontend/01_frontend_architecture.md`
- `docs/specifications/06-frontend/02_react_components_ui_library.md`
- `docs/specifications/06-frontend/03_state_management_data_flow.md`
- `docs/specifications/06-frontend/04_api_integration_data_fetching.md`

Use these reference docs as strict constraints:
- `docs/specifications/00-governance/Enterprise_Reference/06_ANTI_PATTERNS.md`
- `docs/specifications/00-governance/Enterprise_Reference/08_CI_MINIMUM_GATES.md`
- `docs/specifications/00-governance/Enterprise_Reference/04_PHASE_CHECKPOINT_TEMPLATE.md`
- `docs/specifications/00-governance/Enterprise_Reference/07_CONTRACT_CHANGE_POLICY.md`

Do not implement or modify the reference docs themselves.
Use them only to constrain implementation and reporting behavior.

Execution rules:
1. Implement only frontend scope.
2. Keep API access centralized and role routes protected.
3. Ensure production runtime logging is minimal and debug-gated.
4. Run targeted checks for type safety and critical UI flows.
5. Report start/end time and duration, then checkpoint summary.
