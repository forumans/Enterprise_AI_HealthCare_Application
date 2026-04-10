# Deployment Prompt Set

This directory intentionally keeps only the core deployment prompts used by code-generation agents.

## Canonical Files
- `01_deployment_architecture_prompt.md`
- `02_cicd_release_prompt.md`

## Why This Is Minimal
- Architecture and CI/CD prompts are the source of truth.
- Guide/checklist/change-plan outputs should be generated from these prompts when needed.
- This avoids duplicate prompt intent and conflicting generated outcomes.
