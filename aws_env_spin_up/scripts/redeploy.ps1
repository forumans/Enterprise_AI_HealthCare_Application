<#
.SYNOPSIS
    Restores the RDS instance from the latest teardown snapshot, redeploys the
    Lambda + API Gateway stack via SAM, repoints CloudFront's /api/* origin at
    it, and rebuilds/redeploys the frontend (its bundle bakes in the API
    Gateway URL at build time, so it goes stale whenever the URL changes).
    Run this after teardown.ps1 to bring the healthcare_saas_app back up for
    a demo.

.DESCRIPTION
    Lives in aws_env_spin_up/ (a sibling project to healthcare_saas_app/, kept
    separate from application source code). Requires
    aws_env_spin_up/.env.production.backup.json to contain the real
    DATABASE_URL and JWT_SECRET (these are NoEcho SAM params, never stored in
    samconfig.toml - this file is a JSON dump of the live Lambda's environment
    variables, captured by teardown.ps1 before deletion). Requires
    scripts/last-teardown-metadata.json written by teardown.ps1 (subnet
    group, security groups, snapshot id, db name).

    Fully automated end to end - no manual console steps required. (Earlier
    versions of this script left the CloudFront origin update and the
    frontend rebuild/redeploy as manual steps; both turned out to be easy to
    forget - the frontend one especially, since skipping it produces a
    frontend that loads fine but fails every API call with "Failed to fetch"
    because its bundled API URL points at a deleted endpoint.)

.PARAMETER SnapshotId
    RDS snapshot to restore from. Defaults to the snapshot recorded in
    scripts/last-teardown-metadata.json.

.PARAMETER NewDbInstanceId
    Identifier for the restored RDS instance. Defaults to "healthcare-db".
#>
param(
    [string]$SnapshotId,
    [string]$NewDbInstanceId = "healthcare-db"
)

$ErrorActionPreference = "Stop"

$Region     = "us-east-1"
$StackName  = "healthcare-backend"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$RepoRoot   = Split-Path -Parent $ProjectDir
$BackendDir = Join-Path $RepoRoot "healthcare_saas_app\backend"
$MetaFile   = Join-Path $ScriptDir "last-teardown-metadata.json"
$SecretsFile = Join-Path $ProjectDir ".env.production.backup.json"

if (-not (Test-Path $MetaFile)) {
    throw "Missing $MetaFile. Run teardown.ps1 first, or create this file manually with DbSubnetGroupName/VpcSecurityGroupIds/SnapshotId/DbName (see ../README.md)."
}
$Metadata = Get-Content $MetaFile -Raw | ConvertFrom-Json

if (-not $SnapshotId) {
    $SnapshotId = $Metadata.SnapshotId
}
if (-not $SnapshotId) {
    throw "No snapshot ID available. Pass -SnapshotId explicitly or run: aws rds describe-db-snapshots --region $Region --query `"DBSnapshots[?starts_with(DBSnapshotIdentifier,'healthcare-db-final')].DBSnapshotIdentifier`""
}

if (-not (Test-Path $SecretsFile)) {
    throw "Missing $SecretsFile. Redeploy needs DATABASE_URL and JWT_SECRET (NoEcho SAM params not stored anywhere else). Restore it from your password manager first, as a JSON file with those keys."
}

$DbName = if ($Metadata.DbName) { $Metadata.DbName } else { "healthcare_saas" }

Write-Host "=== Step 1: Restore RDS from snapshot $SnapshotId ===" -ForegroundColor Cyan

aws rds restore-db-instance-from-db-snapshot `
    --db-instance-identifier $NewDbInstanceId `
    --db-snapshot-identifier $SnapshotId `
    --db-instance-class $Metadata.DbInstanceClass `
    --db-subnet-group-name $Metadata.DbSubnetGroupName `
    --vpc-security-group-ids $Metadata.VpcSecurityGroupIds `
    --no-publicly-accessible `
    --region $Region | Out-Null

Write-Host "Waiting for RDS instance to become available (typically 10-15 minutes)..."
aws rds wait db-instance-available --db-instance-identifier $NewDbInstanceId --region $Region

$NewEndpoint = (aws rds describe-db-instances --db-instance-identifier $NewDbInstanceId --region $Region --query "DBInstances[0].Endpoint.Address" --output text)
Write-Host "RDS restored. New endpoint: $NewEndpoint" -ForegroundColor Green
Write-Host "(This differs from the old endpoint - that's expected after a restore.)" -ForegroundColor Yellow

Write-Host "`n=== Step 2: Apply migrations (if this is a schema-only restore) ===" -ForegroundColor Cyan
Write-Host "If the snapshot already contains data + schema (the normal case), skip this. Otherwise run in order:"
Write-Host "  psql -h $NewEndpoint -U healthcare_user -d $DbName -f healthcare_saas_app/backend/migrations/001_initial_schema.sql"
Write-Host "  psql -h $NewEndpoint -U healthcare_user -d $DbName -f healthcare_saas_app/backend/migrations/002_fix_sync_function.sql"

Write-Host "`n=== Step 3: Deploy Lambda + API Gateway via SAM ===" -ForegroundColor Cyan

# Read DATABASE_URL / JWT_SECRET out of the JSON secrets backup, but rewrite the host to the new RDS endpoint.
$Secrets = Get-Content $SecretsFile -Raw | ConvertFrom-Json
if (-not $Secrets.DATABASE_URL -or -not $Secrets.JWT_SECRET) {
    throw "$SecretsFile is missing DATABASE_URL or JWT_SECRET."
}
$DatabaseUrl = $Secrets.DATABASE_URL -replace '@[^:/]+:5432', "@${NewEndpoint}:5432"
$JwtSecret   = $Secrets.JWT_SECRET

# Non-secret params stay in sync with samconfig.toml - update both places if these ever change.
$CorsOrigins           = "http://d38vpnbis6nxp0.cloudfront.net,https://d38vpnbis6nxp0.cloudfront.net"
$DocumentsBucketName   = "healthcare-documents-697949337234"
$LambdaSecurityGroupId = "sg-02a345de12bfe50b4"
$PrivateSubnetIds      = "subnet-04dbe0922a7249d51,subnet-02167dbc45e42d274"

Push-Location $BackendDir
try {
    sam build
    if ($LASTEXITCODE -ne 0) { throw "sam build failed." }

    sam deploy --stack-name $StackName --region $Region --capabilities CAPABILITY_IAM --no-confirm-changeset `
        --parameter-overrides `
        "AppEnv=production" `
        "DatabaseUrl=$DatabaseUrl" `
        "JwtSecret=$JwtSecret" `
        "CorsOrigins=$CorsOrigins" `
        "DocumentsBucketName=$DocumentsBucketName" `
        "LambdaSecurityGroupId=$LambdaSecurityGroupId" `
        "PrivateSubnetIds=$PrivateSubnetIds"
    if ($LASTEXITCODE -ne 0) { throw "sam deploy failed." }
} finally {
    Pop-Location
}

$ApiUrl = (aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
$ApiDomain = $ApiUrl -replace '^https://', ''
Write-Host "New ApiUrl: $ApiUrl" -ForegroundColor Green

Write-Host "`n=== Step 4: Update CloudFront /api/* origin ===" -ForegroundColor Cyan
$CloudFrontDomain = "d38vpnbis6nxp0.cloudfront.net"
$ApiOriginId       = "healthcare-backend-alb-402156686.us-east-1.elb.amazonaws.com"
$DistId = (aws cloudfront list-distributions --query "DistributionList.Items[?DomainName=='$CloudFrontDomain'].Id" --output text)

$CfConfigRaw = aws cloudfront get-distribution-config --id $DistId | ConvertFrom-Json
$ETag = $CfConfigRaw.ETag
$CfConfig = $CfConfigRaw.DistributionConfig
$Origin = $CfConfig.Origins.Items | Where-Object { $_.Id -eq $ApiOriginId }
if (-not $Origin) { throw "Could not find CloudFront origin '$ApiOriginId' - update it manually via the console instead." }
$Origin.DomainName = $ApiDomain

$CfConfigFile = Join-Path $env:TEMP "cf-config-update.json"
$CfConfig | ConvertTo-Json -Depth 20 | Set-Content -Path $CfConfigFile
aws cloudfront update-distribution --id $DistId --distribution-config "file://$CfConfigFile" --if-match $ETag | Out-Null
Remove-Item $CfConfigFile -Force
Write-Host "Waiting for CloudFront to finish propagating the new origin (3-5 min)..."
aws cloudfront wait distribution-deployed --id $DistId
Write-Host "CloudFront origin updated." -ForegroundColor Green

Write-Host "`n=== Step 5: Rebuild and redeploy the frontend ===" -ForegroundColor Cyan
Write-Host "(Vite bakes VITE_API_BASE_URL into the JS bundle at build time - since the API Gateway URL just changed, the frontend must be rebuilt and re-uploaded, or the old bundle will call a dead endpoint.)"
$FrontendDir = Join-Path $RepoRoot "healthcare_saas_app\frontend"
$FrontendEnvFile = Join-Path $FrontendDir ".env.production"
$FrontendBucket = "healthcare-frontend-20260320"

(Get-Content $FrontendEnvFile) -replace 'VITE_API_BASE_URL=.*', "VITE_API_BASE_URL=$ApiUrl/api" | Set-Content $FrontendEnvFile

Push-Location $FrontendDir
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed." }
} finally {
    Pop-Location
}

aws s3 sync (Join-Path $FrontendDir "dist") "s3://$FrontendBucket" --delete --region $Region
$InvalidationId = (aws cloudfront create-invalidation --distribution-id $DistId --paths "/*" --query 'Invalidation.Id' --output text)
Write-Host "Waiting for CloudFront invalidation to complete..."
aws cloudfront wait invalidation-completed --distribution-id $DistId --id $InvalidationId
Write-Host "Frontend rebuilt and redeployed." -ForegroundColor Green

Write-Host "`n=== Done ===" -ForegroundColor Cyan
Write-Host "Smoke-test: curl https://$CloudFrontDomain/api/health"
Write-Host "Then load https://$CloudFrontDomain/ in a browser and confirm login works."
