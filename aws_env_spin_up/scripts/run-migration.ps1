<#
.SYNOPSIS
    Applies SQL migration files to the private RDS database through a temporary in-VPC Lambda,
    then deletes the Lambda and its role.

.DESCRIPTION
    RDS is in a private subnet with no bastion, so migrations run from a short-lived Lambda placed
    in the app's subnets/security group. Migrations that change types or tables need the table
    OWNER (the RDS master user, "postgres"), not the app's database user, so the master password
    is asked for at a hidden prompt: it is sent only in the Lambda invocation payload (over TLS),
    never printed, and the temporary payload file is deleted right after the call.

    Run it yourself in an interactive PowerShell window (the password prompt needs a keyboard):
        cd aws_env_spin_up\scripts
        .\run-migration.ps1 -MigrationFiles ..\..\healthcare_saas_app\backend\migrations\005_add_support_staff_role.sql

    Each file runs as one simple-protocol script, so its own BEGIN/COMMIT decides the transaction.
    Afterwards the script grants the app user SELECT/INSERT/UPDATE/DELETE on any public table it
    can't read yet (tables created by the master user) and reports the user_role values.

    -Preflight builds and runs the same Lambda but only connects as the app's own database user
    (read from the live Lambda's DATABASE_URL) and reads schema facts - no password prompt and no
    changes. Use it to check packaging, VPC networking and DB reachability before a real run.

    Needs scripts/aws-config.local.json (Region, VpcSubnetIds, LambdaSecurityGroupId) and Python
    with pip on PATH (to package the PostgreSQL driver for Lambda).
#>
param(
    [string[]]$MigrationFiles = @(),
    [switch]$Preflight,
    # Read-only: save a JSON snapshot of the RDS public schema (schema_snapshot.sql) to this file
    [string]$SchemaSnapshot,
    [string]$DbInstanceId = "healthcare-db",
    [string]$MasterUser = "postgres"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Config = Get-Content (Join-Path $ScriptDir "aws-config.local.json") -Raw | ConvertFrom-Json
$Region = $Config.Region
$FunctionName = "healthcare-migration-runner-temp"
$RoleName = "healthcare-migration-runner-temp-role"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)  # PS 5.1's "utf8" adds a BOM that Lambda rejects

if ($SchemaSnapshot) {
    $Preflight = $true  # same read-only app-user connection
    # [IO.File] resolves relative paths against the process's start folder, not the PowerShell location
    # (cd), so a bare "rds.json" used to land in the user's home folder: make it absolute here
    $SchemaSnapshot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($SchemaSnapshot)
}
if (-not $Preflight -and $MigrationFiles.Count -eq 0) { throw "Pass -MigrationFiles <file.sql> [...] (or -Preflight / -SchemaSnapshot <out.json>)." }
foreach ($file in $MigrationFiles) {
    if (-not (Test-Path $file)) { throw "Migration file not found: $file" }
}

$Db = aws rds describe-db-instances --db-instance-identifier $DbInstanceId --region $Region --query "DBInstances[0].[Endpoint.Address,DBName]" --output text
$DbHost, $DbName = $Db -split "\s+"
$AppDbUrl = aws lambda get-function-configuration --function-name healthcare-backend-backend --region $Region --query "Environment.Variables.DATABASE_URL" --output text
$AppDbUser = ([regex]::Match($AppDbUrl, '//([^:@/]+)[:@]')).Groups[1].Value
if (-not $AppDbUser) { throw "Could not read the app's database user from the Lambda configuration." }
Write-Host "Database: $DbName on $DbInstanceId (app user: $AppDbUser)" -ForegroundColor Cyan

$Work = Join-Path $env:TEMP ("migration-runner-" + (Get-Date -Format yyyyMMddHHmmss))
$Package = Join-Path $Work "package"
New-Item -ItemType Directory -Force $Package | Out-Null

$Handler = @'
import psycopg
from urllib.parse import unquote, urlsplit

SCHEMA_FACTS = """
SELECT
  (SELECT array_agg(enumlabel::text ORDER BY enumsortorder) FROM pg_enum e
     JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = 'user_role'),
  to_regclass('public.support_staff') IS NOT NULL,
  current_user
"""

# Whether the connected (app) user can read and write each public table; by OID so it never errors
APP_ACCESS = """
SELECT c.relname,
       has_table_privilege(c.oid, 'SELECT') AND has_table_privilege(c.oid, 'INSERT')
         AND has_table_privilege(c.oid, 'UPDATE') AND has_table_privilege(c.oid, 'DELETE')
FROM pg_class c
WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p')
"""


def handler(event, context):
    if event.get("preflight"):
        url = urlsplit(event["app_db_url"].replace("postgresql+asyncpg://", "postgresql://"))
        conn = psycopg.connect(host=event["host"], dbname=url.path.lstrip("/"), user=unquote(url.username),
                               password=unquote(url.password), sslmode="require", connect_timeout=15)
        try:
            roles, has_staff_table, who = conn.execute(SCHEMA_FACTS).fetchone()
            no_access = sorted(name for name, ok in conn.execute(APP_ACCESS).fetchall() if not ok)
            snapshot = conn.execute(event["snapshot_sql"]).fetchone()[0] if event.get("snapshot_sql") else None
            return {"preflight": True, "connected_as": who, "user_role_values": roles,
                    "support_staff_table": has_staff_table, "tables_without_full_access": no_access,
                    "schema_snapshot": snapshot}
        finally:
            conn.close()

    results = []
    conn = psycopg.connect(host=event["host"], dbname=event["db"], user=event["user"], password=event["password"],
                           sslmode="require", connect_timeout=15, autocommit=True)
    try:
        for migration in event["migrations"]:
            if not isinstance(migration.get("sql"), str):
                results.append({"file": str(migration.get("name")), "ok": False, "error": f"payload bug: sql is {type(migration.get('sql')).__name__}, not text"})
                return {"results": results}
            try:
                conn.execute(migration["sql"])  # no parameters -> simple protocol, multi-statement script
                results.append({"file": migration["name"], "ok": True})
            except Exception as exc:  # report and stop at the first failing file
                results.append({"file": migration["name"], "ok": False, "error": f"{type(exc).__name__}: {exc}"})
                return {"results": results}

        app_user = event["app_user"]
        granted = []
        # Check by OID, not by building 'public.<name>': the planner may evaluate the privilege
        # check before the schema filter, and a name like public.pg_statistic doesn't resolve.
        for (table,) in conn.execute(
            "SELECT c.relname FROM pg_class c "
            "WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p') "
            "AND NOT has_table_privilege(%s, c.oid, 'SELECT')",
            (app_user,),
        ).fetchall():
            conn.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON public."{table}" TO "{app_user}"')
            granted.append(table)
        roles, has_staff_table, _ = conn.execute(SCHEMA_FACTS).fetchone()
        return {"results": results, "granted_to_app_user": granted, "user_role_values": roles, "support_staff_table": has_staff_table}
    finally:
        conn.close()
'@
[IO.File]::WriteAllText((Join-Path $Package "handler.py"), $Handler, $Utf8NoBom)

Write-Host "Packaging the PostgreSQL driver for Lambda (python3.12, x86_64)..."
python -m pip install --quiet --disable-pip-version-check --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: --target $Package "psycopg[binary]==3.2.3"
if ($LASTEXITCODE -ne 0) { throw "pip could not download psycopg for Lambda." }
$Zip = Join-Path $Work "runner.zip"
Compress-Archive -Path (Join-Path $Package "*") -DestinationPath $Zip

$Trust = Join-Path $Work "trust.json"
[IO.File]::WriteAllText($Trust, '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}', $Utf8NoBom)
$PayloadFile = Join-Path $Work "payload.json"
$OutFile = Join-Path $Work "out.json"

try {
    Write-Host "Creating the temporary role and Lambda in the VPC (about a minute)..."
    $RoleArn = aws iam create-role --role-name $RoleName --assume-role-policy-document "file://$Trust" --query Role.Arn --output text
    aws iam attach-role-policy --role-name $RoleName --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
    Start-Sleep -Seconds 12  # new IAM roles take a few seconds before Lambda can assume them
    aws lambda create-function --function-name $FunctionName --runtime python3.12 --architectures x86_64 `
        --handler handler.handler --role $RoleArn --zip-file "fileb://$Zip" --timeout 300 --memory-size 256 `
        --vpc-config "SubnetIds=$($Config.VpcSubnetIds -join ','),SecurityGroupIds=$($Config.LambdaSecurityGroupId)" `
        --region $Region | Out-Null
    aws lambda wait function-active-v2 --function-name $FunctionName --region $Region

    if ($Preflight) {
        $Payload = @{ preflight = $true; host = $DbHost; app_db_url = $AppDbUrl }
        if ($SchemaSnapshot) { $Payload.snapshot_sql = [IO.File]::ReadAllText((Join-Path $ScriptDir "schema_snapshot.sql")) }
    } else {
        $Secure = Read-Host -AsSecureString "Password for RDS master user '$MasterUser' (hidden)"
        $Plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure))
        $Migrations = New-Object System.Collections.ArrayList
        # ReadAllText, not Get-Content: in PS 5.1 Get-Content's string carries PSPath/PSDrive note
        # properties, and ConvertTo-Json then serializes it as an object instead of plain text.
        foreach ($file in $MigrationFiles) {
            $Sql = [IO.File]::ReadAllText((Resolve-Path $file).Path)
            [void]$Migrations.Add(@{ name = [string](Split-Path $file -Leaf); sql = [string]$Sql })
        }
        $Payload = @{ host = $DbHost; db = $DbName; user = $MasterUser; password = $Plain; app_user = $AppDbUser; migrations = $Migrations }
        Remove-Variable Plain, Secure
    }
    [IO.File]::WriteAllText($PayloadFile, ($Payload | ConvertTo-Json -Depth 5 -Compress), $Utf8NoBom)
    Remove-Variable Payload, AppDbUrl

    Write-Host ($(if ($Preflight) { "Running the preflight check..." } else { "Running migrations..." }))
    aws lambda invoke --function-name $FunctionName --payload "fileb://$PayloadFile" --region $Region $OutFile | Out-Null
    Remove-Item $PayloadFile -Force  # it held a password

    $Out = Get-Content $OutFile -Raw | ConvertFrom-Json
    if ($Out.errorMessage) { throw "Runner failed: $($Out.errorType): $($Out.errorMessage)" }
    if ($Preflight) {
        Write-Host "Preflight OK: connected as $($Out.connected_as); user_role = $($Out.user_role_values -join ', '); support_staff table exists = $($Out.support_staff_table)" -ForegroundColor Green
        if ($SchemaSnapshot) {
            [IO.File]::WriteAllText($SchemaSnapshot, $Out.schema_snapshot, $Utf8NoBom)
            Write-Host "Schema snapshot saved to $SchemaSnapshot"
        }
        $NoAccess = @($Out.tables_without_full_access)
        Write-Host ("Tables $($Out.connected_as) can't fully read/write: " + $(if ($NoAccess.Count) { $NoAccess -join ', ' } else { "none" }))
    } else {
        foreach ($r in $Out.results) {
            if ($r.ok) { Write-Host "  OK      $($r.file)" -ForegroundColor Green } else { Write-Host "  FAILED  $($r.file): $($r.error)" -ForegroundColor Red }
        }
        Write-Host "user_role values: $($Out.user_role_values -join ', '); support_staff table exists = $($Out.support_staff_table)"
        if ($Out.granted_to_app_user) { Write-Host "Granted $AppDbUser access to: $($Out.granted_to_app_user -join ', ')" }
        if ($Out.results | Where-Object { -not $_.ok }) { throw "A migration failed (nothing after it was run)." }
        Write-Host "Migrations applied." -ForegroundColor Green
    }
} finally {
    $ErrorActionPreference = "Continue"  # always attempt every cleanup step
    if (Test-Path $PayloadFile) { Remove-Item $PayloadFile -Force }
    Write-Host "Removing the temporary Lambda and role..."
    aws lambda delete-function --function-name $FunctionName --region $Region 2>$null | Out-Null
    aws iam detach-role-policy --role-name $RoleName --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole 2>$null | Out-Null
    aws iam delete-role --role-name $RoleName 2>$null | Out-Null
    Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Cleanup done."
}
