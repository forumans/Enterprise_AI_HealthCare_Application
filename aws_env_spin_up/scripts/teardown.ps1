<#
.SYNOPSIS
    Snapshots the RDS instance, backs up the schema, and deletes the billable
    AWS resources for the healthcare_saas_app (CloudFormation stack + RDS
    instance) so the account stops incurring cost. CloudFront, both S3
    buckets, and the VPC networking are left in place - they cost nothing
    meaningful while idle.

.DESCRIPTION
    Lives in aws_env_spin_up/ (a sibling project to healthcare_saas_app/, kept
    separate from application source code). Requires the AWS CLI and SAM CLI
    configured for the target account/region, and network access to the RDS
    instance for the pg_dump step (it lives in a private VPC subnet - see
    ../README.md for how to reach it, e.g. via an SSM port-forward session).

.PARAMETER SkipSchemaDump
    Skip the pg_dump schema-only backup step (only do this if
    healthcare_saas_app/backend/migrations/001_initial_schema.sql is already
    known to be current).

.PARAMETER WhatIf
    Print what would be done without deleting anything.
#>
param(
    [switch]$SkipSchemaDump,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$StackName    = "healthcare-backend"
$DbInstanceId = "healthcare-db"
$DbName       = "healthcare_saas"
$DbUser       = "healthcare_user"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$RepoRoot   = Split-Path -Parent $ProjectDir
$BackendDir = Join-Path $RepoRoot "healthcare_saas_app\backend"
$SnapshotId = "healthcare-db-final-$(Get-Date -Format 'yyyy-MM-dd-HHmmss')"

# Real account-specific identifiers (RDS endpoint, subnet IDs) live in this gitignored file, not
# in the script - see aws-config.example.json for the shape. Never commit aws-config.local.json.
$ConfigFile = Join-Path $ScriptDir "aws-config.local.json"
if (-not (Test-Path $ConfigFile)) {
    throw "Missing $ConfigFile. Copy aws-config.example.json to aws-config.local.json and fill in your real AWS values."
}
$Config     = Get-Content $ConfigFile -Raw | ConvertFrom-Json
$Region     = $Config.Region
$DbHost     = $Config.DbHost
$VpcSubnets = $Config.VpcSubnetIds

Write-Host "=== Step 1: Backup ===" -ForegroundColor Cyan

if (-not $SkipSchemaDump) {
    $SchemaFile = Join-Path $BackendDir "migrations\001_initial_schema.sql"
    Write-Host "Dumping live schema to $SchemaFile"
    if (-not $WhatIf) {
        & pg_dump -h $DbHost -U $DbUser -d $DbName --schema-only -f $SchemaFile
        if ($LASTEXITCODE -ne 0) {
            throw "pg_dump failed. If this is a connection timeout, the RDS instance is in a private subnet - see ../README.md for how to reach it (SSM port-forward or bastion) before re-running, or pass -SkipSchemaDump to rely on the RDS snapshot alone."
        }
        Write-Host "Schema dump saved. Commit this file in healthcare_saas_app before proceeding." -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping schema dump (-SkipSchemaDump passed)."
}

Write-Host "Capturing RDS instance config (subnet group, security groups, class) for redeploy..."
$MetaFile = Join-Path $ScriptDir "last-teardown-metadata.json"
if (-not $WhatIf) {
    $Instance = aws rds describe-db-instances --db-instance-identifier $DbInstanceId --region $Region | ConvertFrom-Json
    $Db = $Instance.DBInstances[0]
    $Metadata = @{
        SnapshotId          = $SnapshotId
        DbInstanceClass     = $Db.DBInstanceClass
        DbSubnetGroupName   = $Db.DBSubnetGroup.DBSubnetGroupName
        VpcSecurityGroupIds = @($Db.VpcSecurityGroups | ForEach-Object { $_.VpcSecurityGroupId })
        Engine              = $Db.Engine
        EngineVersion       = $Db.EngineVersion
        DbName              = $DbName
        TornDownAt          = (Get-Date -Format "o")
    }
    $Metadata | ConvertTo-Json | Set-Content -Path $MetaFile
    Write-Host "Saved instance metadata to $MetaFile (redeploy.ps1 reads this automatically)." -ForegroundColor Green
}

Write-Host "Creating final RDS snapshot: $SnapshotId"
if (-not $WhatIf) {
    aws rds create-db-snapshot `
        --db-instance-identifier $DbInstanceId `
        --db-snapshot-identifier $SnapshotId `
        --region $Region | Out-Null

    Write-Host "Waiting for snapshot to become available (this can take several minutes)..."
    aws rds wait db-snapshot-available --db-snapshot-identifier $SnapshotId --region $Region
    Write-Host "Snapshot $SnapshotId is available." -ForegroundColor Green
}

Write-Host "`nChecking for NAT Gateways / unattached Elastic IPs in the VPC (these bill even when idle)..."
$VpcId = (aws ec2 describe-subnets --subnet-ids $VpcSubnets[0] --region $Region --query "Subnets[0].VpcId" --output text)
$NatGateways = aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VpcId" "Name=state,Values=available" --region $Region --query "NatGateways[].NatGatewayId" --output text
$UnattachedEips = aws ec2 describe-addresses --region $Region --query "Addresses[?AssociationId==null].AllocationId" --output text

if ($NatGateways) {
    Write-Host "Found NAT Gateway(s) that likely bill ~$32/mo each: $NatGateways" -ForegroundColor Yellow
    Write-Host "Review whether Lambda needs them (it only talks to RDS/S3 in-VPC) before deleting manually:"
    Write-Host "  aws ec2 delete-nat-gateway --nat-gateway-id <id> --region $Region"
} else {
    Write-Host "No active NAT Gateways found." -ForegroundColor Green
}

if ($UnattachedEips) {
    Write-Host "Found unattached Elastic IP(s) (~`$3.6/mo each): $UnattachedEips" -ForegroundColor Yellow
    Write-Host "  aws ec2 release-address --allocation-id <id> --region $Region"
} else {
    Write-Host "No unattached Elastic IPs found." -ForegroundColor Green
}

Write-Host "`n=== Step 2: Delete billable resources ===" -ForegroundColor Cyan

if ($WhatIf) {
    Write-Host "[PREVIEW MODE] Nothing has been deleted and nothing will be." -ForegroundColor Green
    Write-Host "[PREVIEW MODE] A real run would now ask you to type 'delete' to confirm, then delete:"
    Write-Host "[PREVIEW MODE]   - CloudFormation stack '$StackName'"
    Write-Host "[PREVIEW MODE]   - RDS instance '$DbInstanceId'"
    Write-Host "`nPreview complete. Your live app was not touched at any point." -ForegroundColor Cyan
    exit 0
}

$confirm = Read-Host "Type 'delete' to permanently delete the CloudFormation stack '$StackName' and the RDS instance '$DbInstanceId' (snapshot $SnapshotId will remain)"
if ($confirm -ne "delete") {
    Write-Host "Aborted - nothing was deleted. Re-run when ready." -ForegroundColor Yellow
    exit 0
}

Write-Host "Deleting CloudFormation stack $StackName..."
Push-Location $BackendDir
try {
    sam delete --stack-name $StackName --region $Region --no-prompts
} finally {
    Pop-Location
}

Write-Host "Deleting RDS instance $DbInstanceId (snapshot already taken, skipping final snapshot)..."
aws rds delete-db-instance `
    --db-instance-identifier $DbInstanceId `
    --skip-final-snapshot `
    --region $Region | Out-Null
Write-Host "RDS deletion initiated. It will take a few minutes to complete." -ForegroundColor Green

Write-Host "`nDone. CloudFront, both S3 buckets, and VPC networking were left untouched." -ForegroundColor Cyan
Write-Host "Record this snapshot ID somewhere durable - you'll need it for redeploy.ps1: $SnapshotId" -ForegroundColor Yellow
