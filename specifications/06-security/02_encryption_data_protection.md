# Prompt: Encryption and Data Protection

## Prompt
Implement encryption and data protection controls across `backend`, `infrastructure`, and `deployment`.

### Requirements
1. Enforce TLS in transit for all external and internal traffic where applicable.
2. Ensure encryption at rest for RDS, S3, and backups.
3. Use KMS-managed keys for cloud resources.
4. Protect sensitive fields and avoid PHI leakage in logs/events.
5. Define key rotation and secret rotation policy.

### Deliverables
- `infrastructure/` config for encrypted RDS/S3 and KMS usage.
- `backend/docs/data-protection-policy.md` including PHI handling.
- `deployment/runbooks/secret-rotation.md`.
- Validation checks in `testing/security/` for encryption and logging rules.

### Acceptance Criteria
- All storage classes holding sensitive data are encrypted.
- Runtime config references secret stores, not plaintext credentials.
- Error and access logs avoid PHI exposure.
