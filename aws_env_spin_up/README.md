# aws_env_spin_up

Tooling for stopping AWS costs on the `healthcare_saas_app` when it's not being demoed, and spinning it back up on demand. Kept as a separate project (sibling to `healthcare_saas_app/`) so infra/ops tooling doesn't mix with application source code.

This app runs on a mix of IaC-managed resources (Lambda + API Gateway via SAM) and manually-provisioned ones (VPC, RDS, S3 buckets, CloudFront — see `../healthcare_saas_app/docs/deployment.md`). The only resource that bills you simply for existing, whether or not anyone uses the app, is the **RDS instance** (`db.t4g.micro`, ~$12-15/mo). Everything else (Lambda, API Gateway, CloudFront, S3) is pay-per-request/pay-per-GB and costs effectively $0 while idle.

So "stop paying entirely" means: snapshot and delete RDS, verify there's no forgotten NAT Gateway/Elastic IP, and delete the CloudFormation stack for tidiness. CloudFront, both S3 buckets, and the VPC/subnets/security groups are left alone — deleting them buys no savings and makes redeploy slower and riskier.

## Current status

**Running since 2026-10-22** (redeployed for a client demo). On 2026-10-24 the latest code was deployed in place with `deploy-update.ps1` and migration 005 (Support Staff role) applied with `run-migration.ps1`. RDS bills again while it runs (~$0.40-0.50/day) - run `teardown.ps1` when the demo is over. The previous teardown (2026-07-17, snapshot `healthcare-db-final-2026-07-17-153336`) is what `redeploy.ps1` restored from.

**To bring it back up for the next demo**, run `redeploy.ps1` — see below. It's now fully automated (RDS restore, SAM deploy, CloudFront origin update, frontend rebuild/redeploy) based on the fix from the 2026-07-10 incident.

Note: the actual live database name is `healthcare_saas`, not `healthcare_db` as `../healthcare_saas_app/docs/deployment.md` and the `.env.example` file assume — the scripts here use the correct value.

### Operational notes (learned the hard way, now fixed in the scripts)

- **The first redeploy on 2026-07-10 left login broken** with "Failed to fetch" even though the health check passed. Root cause: Vite bakes `VITE_API_BASE_URL` into the frontend's JS bundle at build time, and that redeploy only recreated the backend — the still-deployed frontend bundle kept calling the *old, now-deleted* API Gateway URL directly (bypassing CloudFront entirely). **`redeploy.ps1` now rebuilds and redeploys the frontend automatically** (updates `.env.production`, `npm run build`, `aws s3 sync`, CloudFront invalidation) as its last step, so this can't happen again silently. If you ever see "Failed to fetch" specifically on API calls (not on page load) after a redeploy, this bundle-staleness is the first thing to check: download the live JS bundle and grep it for `execute-api` to see what URL it actually points at.
- **`redeploy.ps1` now also updates the CloudFront `/api/*` origin itself** (via `get-distribution-config`/`update-distribution` with the ETag) instead of leaving it as a manual console step — the account already has `CloudFrontFullAccess`, so this is safe to automate.
- **`sam build` can fail with `[WinError 5] Access is denied`** building directly into `healthcare_saas_app/backend/.aws-sam` — a known OneDrive-sync locking issue since the repo lives under a OneDrive folder. **`redeploy.ps1` now builds into a fresh timestamped dir under `%TEMP%`** (a reused build dir hit the same `PermissionError` when sam tried to delete it) and passes `--resolve-s3`/`--s3-prefix` to `sam deploy` explicitly, since `samconfig.toml` isn't picked up once `--template-file` points outside the backend dir.
- **Unpinned Python deps can break the Lambda on redeploy.** On the 2026-10-22 redeploy, `sqlalchemy>=2.0.0` resolved to SQLAlchemy 2.1, which no longer installs `greenlet` by default — every request failed with `Runtime.ImportModuleError` (health check returned `{"message":"Internal Server Error"}`) until `requirements.txt` was changed to `sqlalchemy[asyncio]>=2.0.0`. If the health check 500s after a redeploy, check `aws logs tail /aws/lambda/healthcare-backend-backend` first.
- **Don't pipe `redeploy.ps1` through `*>&1`/`Tee-Object` in Windows PowerShell 5.1** — that wraps native-command stderr (sam's normal progress output) in error records, and the script's `$ErrorActionPreference = "Stop"` aborts on them.
- **`sam` isn't on the Bash/Git-Bash PATH** but is available in PowerShell (`C:\Program Files\Amazon\AWSSAMCLI\bin`) — run these scripts from PowerShell, not Git Bash, on this machine.

## Layout

```
aws_env_spin_up/
├── README.md                              (this file)
├── .env.production.backup.json            (gitignored — real prod secrets, captured from the live Lambda before teardown)
├── .gitignore
└── scripts/
    ├── teardown.ps1
    ├── redeploy.ps1
    ├── deploy-update.ps1                  (deploy new code to the running environment)
    ├── run-migration.ps1                  (apply SQL migrations via a temporary in-VPC Lambda)
    ├── iam-policy-teardown-redeploy.json  (IAM policy granting the extra permissions these scripts need)
    ├── aws-config.example.json            (tracked — placeholder shape for the real config below)
    ├── aws-config.local.json              (gitignored — real account ID/bucket names/subnet & security-group IDs/CloudFront domain; copy from the example above and fill in)
    └── last-teardown-metadata.json        (gitignored — subnet group / security groups / snapshot id / db name captured by the last teardown; regenerated each run)
```

This repo is public — none of the gitignored files above should ever be committed. If you're setting this up fresh, copy `scripts/aws-config.example.json` to `scripts/aws-config.local.json` and fill in your real values before running either script.

## Prerequisites (one-time)

- AWS CLI configured for the account/region (`aws sts get-caller-identity` succeeds), SAM CLI installed, `psql`/`pg_dump` available.
- **IAM permissions**: **already granted** (done 2026-07-06) as an inline policy on the deploying IAM user (`healthcare_github_action_deploy`), not a managed policy. `scripts/iam-policy-teardown-redeploy.json` is the policy document that was applied, covering the RDS snapshot/delete/restore and NAT Gateway/EIP actions that deploying alone (per `../healthcare_saas_app/docs/deployment.md`) doesn't grant.

  Note for future reference: this had to be an **inline** policy (`aws iam put-user-policy`), not a managed one (`aws iam attach-user-policy`), because the user was already at AWS's default cap of 10 attached managed policies. Inline policies count against a separate quota and don't touch that limit. `AmazonEC2ContainerRegistryFullAccess` looks like a leftover from the pre-Lambda ECS Fargate architecture mentioned in `template.yaml`'s comments — worth reviewing whether it's still needed if you ever need managed-policy headroom again.

  **Updated 2026-08-31**: the user's inline policies (`HealthcareAppTeardownRedeploy` + `LambdaVpcDeployAccess`) also hit their own combined 2048-byte quota, so a one-off Cost Explorer investigation couldn't add a third inline policy. `AmazonECS_FullAccess` (the other pre-Lambda leftover) was detached and `AWSBillingReadOnlyAccess` attached in its place to stay under the 10-managed-policy cap — kept permanently per the user's choice, not reverted. Current attached managed policies: `AmazonAPIGatewayAdministrator`, `AmazonEC2ContainerRegistryFullAccess`, `CloudFrontFullAccess`, `IAMFullAccess`, `SecretsManagerReadWrite`, `AmazonS3FullAccess`, `CloudWatchFullAccessV2`, `AWSCloudFormationFullAccess`, `AWSLambda_FullAccess`, `AWSBillingReadOnlyAccess`.

  To verify the permission is still in place: `aws iam get-user-policy --user-name healthcare_github_action_deploy --policy-name HealthcareAppTeardownRedeploy` should return the policy, and `aws rds describe-db-instances --db-instance-identifier healthcare-db --region us-east-1` should succeed without an `AccessDenied` error (only meaningful while the instance still exists).
- **`scripts/aws-config.local.json`** with the real account-specific identifiers (RDS endpoint host, VPC subnet IDs, Lambda security group ID, S3 bucket names, CloudFront domain and API origin ID) — copy `scripts/aws-config.example.json` and fill in real values. Neither script will run without it. Kept out of git since this repo is public; the current real values can be re-derived from the live AWS resources if this file is ever lost (`aws rds describe-db-instances`, `aws s3 ls`, `aws cloudfront list-distributions`, etc.).
- **`.env.production.backup.json`** with the real `DATABASE_URL` and `JWT_SECRET` — these are `NoEcho` SAM parameters, never saved to `samconfig.toml`. This repo's own `healthcare_saas_app/backend/.env` is set up for **local development only** (points at `localhost`, uses a placeholder `JWT_SECRET`) — it is NOT the production configuration and `redeploy.ps1` does not read it. Since the app doesn't use Secrets Manager (`AWS_SECRETS_MANAGER_ENABLED=false`), the real values can always be re-pulled from a running Lambda via `aws lambda get-function-configuration --function-name healthcare-backend-backend --region us-east-1 --query 'Environment.Variables'` — but once the Lambda is deleted, this backup file is the only remaining copy. Back it up to a password manager; if it's ever lost with no other copy, redeploy is only possible by regenerating `JWT_SECRET` (which invalidates all existing sessions).
- **RDS is in a private VPC subnet, not publicly accessible** (confirmed in `../healthcare_saas_app/docs/deployment.md`, and confirmed empirically — `pg_dump` from a normal dev machine times out). You need one of:
  - An SSM Session Manager port-forward through a bastion/existing EC2 instance in the VPC, or
  - A temporary bastion host, or
  - Running the dump from something already inside the VPC.

  If none of these are available, use `-SkipSchemaDump` on `teardown.ps1` and rely solely on the RDS snapshot for schema recovery (this is what happened on the 2026-07-06 teardown — no bastion was available, so the schema-only dump was skipped and the RDS snapshot is the sole backup of both schema and data).

## Tearing down (stop paying)

```powershell
cd aws_env_spin_up/scripts
.\teardown.ps1
```

This will, in order:
1. `pg_dump --schema-only` the live database to `../healthcare_saas_app/backend/migrations/001_initial_schema.sql` (fills a gap — this file didn't exist before; only two incremental migrations did). Skipped automatically if the RDS instance isn't reachable, or explicitly via `-SkipSchemaDump`.
2. Capture the RDS instance's subnet group, security groups, instance class, and db name to `scripts/last-teardown-metadata.json` (needed to restore an identical instance later — contains no passwords, but does contain real infra identifiers, so it's gitignored, not committed).
3. Take a final RDS snapshot named `healthcare-db-final-<timestamp>` and wait for it to finish.
4. Check for a NAT Gateway or unattached Elastic IP in the VPC (undocumented anywhere — Lambda only needs RDS/S3 access, which doesn't require internet egress, so a NAT Gateway here would likely be a forgotten ~$32/mo cost). Prints commands to delete if found; does not delete automatically. (Checked on 2026-07-06: none found.)
5. Prompt for a typed confirmation, then delete the CloudFormation stack (`sam delete`) and the RDS instance (`aws rds delete-db-instance --skip-final-snapshot`, safe since step 3 already snapshotted).

**Try it safely first**: run `.\teardown.ps1 -WhatIf`. In this mode the script makes no changes at all — it skips the schema dump, skips creating a snapshot, and exits before ever asking you to confirm a deletion. It only runs a couple of read-only "list my resources" AWS calls (to check for a forgotten NAT Gateway) which cannot change anything. It prints `[PREVIEW MODE]` next to every step it would otherwise perform. Your live app is never touched by this preview.

**After this completes**, the CloudFront URL still resolves but `/api/*` calls will error (backend is gone) — that's expected. The frontend static assets and CloudFront distribution stay up at effectively no cost.

## Updating a running environment

When the environment is already up, deploy new code in place instead of tearing down and redeploying:

```powershell
cd aws_env_spin_up/scripts
.\run-migration.ps1 -Preflight                    # optional: check packaging/VPC/DB access, read-only
.\run-migration.ps1 -MigrationFiles <file.sql>    # only if the release adds migrations - run these FIRST
.\deploy-update.ps1                               # sam build/deploy (stack update) + frontend build, S3 sync, invalidation
```

- **`run-migration.ps1`** runs SQL files from a temporary Lambda inside the VPC (RDS is private and there is no bastion), then deletes the Lambda and its IAM role. Migrations that alter types or tables must run as the table owner - the RDS master user `postgres` - so it asks for the master password at a hidden prompt (run it yourself in an interactive PowerShell window). The password goes only into the Lambda invocation payload; the payload file is deleted right after. Afterwards it grants the app user (`healthcare_user`) DML on any public table it can't read - **RDS has no default privileges for the app user, so tables created by `postgres` need this grant** (the local dev database does have them). `-Preflight` connects as the app user instead, makes no changes and reports the `user_role` values, whether `support_staff` exists, and any tables the app user can't fully read/write.
- **`deploy-update.ps1`** reuses the live Lambda's `DATABASE_URL`/`JWT_SECRET` (never printed), so sessions and the DB connection carry over, refuses to run on an unhealthy stack, checks the API URL didn't change (a stack update keeps it), and smoke-tests `/api/health` at the end. `-SkipBackend` / `-SkipFrontend` deploy just one half.
- **`run-migration.ps1 -SchemaSnapshot <file>`** (read-only) saves the RDS schema as JSON; **`python compare_schema.py <file>`** diffs it against the local database (columns, enum values, indexes, constraints, triggers, functions, schemas, app-user access). Use it after running a migration on one side to confirm both match.
- Run both from PowerShell, and don't pipe them through `2>&1`/`*>&1` (see the operational notes above).

## Redeploying for a demo

```powershell
cd aws_env_spin_up/scripts
.\redeploy.ps1
```

This is now fully automated end to end — no manual console steps. It will:
1. Restore RDS from the snapshot recorded in `last-teardown-metadata.json` (or pass `-SnapshotId` explicitly), into the same subnet group and security groups. Takes ~10-15 minutes.
2. Print `psql` commands to apply migrations if you restored a schema-only snapshot rather than one with live data — otherwise skip (the normal case, since RDS snapshots include both).
3. Run `sam build` (into a temp dir outside OneDrive) `&& sam deploy` (from `../healthcare_saas_app/backend`) using the non-secret parameters from `samconfig.toml` (CORS origins, S3 bucket, security group, subnets) plus `DATABASE_URL`/`JWT_SECRET` read from `.env.production.backup.json`, with the DB host rewritten to the new RDS endpoint.
4. Update CloudFront's `/api/*` origin to the new API Gateway domain (the endpoint ID changes every time the stack is recreated) and wait for the distribution to finish propagating (~3-5 min).
5. Rebuild the frontend with the new API URL baked in, sync it to the S3 frontend bucket, and invalidate the CloudFront cache.

### Verify

```bash
curl https://<your-cloudfront-domain>/api/health   # domain is in scripts/aws-config.local.json
# expect: {"status":"healthy","database":"connected"}
```

Then load the frontend URL in a browser and confirm login works.

## Cost reference

| Resource | Cost while running | Cost while torn down |
|---|---|---|
| RDS `db.t4g.micro` | ~$12-15/mo | $0 (deleted; snapshot storage ~$0.095/GB-mo) |
| NAT Gateway (if present) | ~$32/mo + data | $0 (none found in this account) |
| Lambda + API Gateway | ~$0 at low volume (pay-per-use) | $0 (stack deleted) |
| CloudFront + both S3 buckets | ~$0 at low volume | unchanged — left running |
