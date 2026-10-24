<#
.SYNOPSIS
    Deploys new application code to the RUNNING environment: updates the Lambda + API Gateway
    stack via SAM, then rebuilds and redeploys the frontend.

.DESCRIPTION
    Use this when the environment is already up (redeploy.ps1 is for bringing it back after a
    teardown: it restores RDS and recreates the stack). A stack update keeps the same API Gateway
    URL, so CloudFront's /api/* origin and the frontend's VITE_API_BASE_URL stay valid; the script
    checks the latter and stops if it doesn't match.

    DATABASE_URL and JWT_SECRET (NoEcho SAM parameters) are read from the live Lambda's
    configuration and passed straight to sam deploy - never printed or written to disk - so
    existing sessions and the database connection carry over unchanged.

    Apply any pending migrations FIRST with run-migration.ps1: the new backend may need them.

        cd aws_env_spin_up\scripts
        .\deploy-update.ps1             # backend + frontend
        .\deploy-update.ps1 -SkipFrontend
#>
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$StackName  = "healthcare-backend"
$FunctionName = "healthcare-backend-backend"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$BackendDir = Join-Path $RepoRoot "healthcare_saas_app\backend"
$FrontendDir = Join-Path $RepoRoot "healthcare_saas_app\frontend"
$Config = Get-Content (Join-Path $ScriptDir "aws-config.local.json") -Raw | ConvertFrom-Json
$Region = $Config.Region

$StackStatus = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].StackStatus" --output text
if ($StackStatus -notmatch "_COMPLETE$" -or $StackStatus -match "ROLLBACK|DELETE") {
    throw "Stack $StackName is '$StackStatus' - this script only updates a healthy running stack (use redeploy.ps1 after a teardown)."
}
$ApiUrl = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text

if (-not $SkipBackend) {
    Write-Host "=== Backend: sam build + sam deploy (stack update) ===" -ForegroundColor Cyan
    $Live = aws lambda get-function-configuration --function-name $FunctionName --region $Region --query "Environment.Variables" --output json | ConvertFrom-Json
    if (-not $Live.DATABASE_URL -or -not $Live.JWT_SECRET) { throw "Could not read DATABASE_URL/JWT_SECRET from the live Lambda." }

    Push-Location $BackendDir
    try {
        # Build outside OneDrive (it locks .aws-sam files -> [WinError 5]); fresh dir each run.
        $SamBuildDir = Join-Path $env:TEMP ("healthcare-sam-build-" + (Get-Date -Format yyyyMMddHHmmss))
        sam build --build-dir $SamBuildDir
        if ($LASTEXITCODE -ne 0) { throw "sam build failed." }

        sam deploy --template-file (Join-Path $SamBuildDir "template.yaml") --resolve-s3 --s3-prefix $StackName `
            --stack-name $StackName --region $Region --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset `
            --parameter-overrides `
            "AppEnv=production" `
            "DatabaseUrl=$($Live.DATABASE_URL)" `
            "JwtSecret=$($Live.JWT_SECRET)" `
            "CorsOrigins=http://$($Config.CloudFrontDomain),https://$($Config.CloudFrontDomain)" `
            "DocumentsBucketName=$($Config.DocumentsBucketName)" `
            "LambdaSecurityGroupId=$($Config.LambdaSecurityGroupId)" `
            "PrivateSubnetIds=$($Config.VpcSubnetIds -join ',')"
        if ($LASTEXITCODE -ne 0) { throw "sam deploy failed." }
    } finally {
        Remove-Variable Live -ErrorAction SilentlyContinue
        Pop-Location
    }
    $NewApiUrl = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text
    if ($NewApiUrl -ne $ApiUrl) { throw "API URL changed ($ApiUrl -> $NewApiUrl): update CloudFront's /api/* origin and rebuild the frontend (see redeploy.ps1 steps 4-5)." }
    Write-Host "Backend deployed; API URL unchanged." -ForegroundColor Green
}

if (-not $SkipFrontend) {
    Write-Host "`n=== Frontend: build, upload to S3, invalidate CloudFront ===" -ForegroundColor Cyan
    $EnvFile = Join-Path $FrontendDir ".env.production"
    if (-not (Select-String -Path $EnvFile -Pattern ([regex]::Escape("VITE_API_BASE_URL=$ApiUrl/api")) -Quiet)) {
        throw "$EnvFile doesn't point at the live API ($ApiUrl/api). Fix VITE_API_BASE_URL first."
    }
    Push-Location $FrontendDir
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "frontend build failed." }
    } finally {
        Pop-Location
    }
    aws s3 sync (Join-Path $FrontendDir "dist") "s3://$($Config.FrontendBucketName)" --delete --region $Region
    if ($LASTEXITCODE -ne 0) { throw "s3 sync failed." }
    $DistId = aws cloudfront list-distributions --query "DistributionList.Items[?DomainName=='$($Config.CloudFrontDomain)'].Id" --output text
    $InvalidationId = aws cloudfront create-invalidation --distribution-id $DistId --paths "/*" --query "Invalidation.Id" --output text
    Write-Host "Waiting for the CloudFront invalidation to finish..."
    aws cloudfront wait invalidation-completed --distribution-id $DistId --id $InvalidationId
    Write-Host "Frontend deployed." -ForegroundColor Green
}

Write-Host "`n=== Smoke test ===" -ForegroundColor Cyan
$Health = Invoke-RestMethod "https://$($Config.CloudFrontDomain)/api/health" -TimeoutSec 30
Write-Host "health: $($Health | ConvertTo-Json -Compress)"
if ($Health.status -ne "healthy" -or $Health.database -ne "connected") { throw "Health check failed after deploy - check: aws logs tail /aws/lambda/$FunctionName --region $Region" }
Write-Host "Done. Load https://$($Config.CloudFrontDomain)/ and sign in to confirm." -ForegroundColor Green
