# Healthcare E2E Test Setup Script (PowerShell)
# This script helps set up the independent E2E test environment

Write-Host "🚀 Setting up Healthcare E2E Test Suite..." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

# Check if Node.js is installed
try {
    $nodeVersion = node -v
    Write-Host "✅ Node.js version: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js is not installed. Please install Node.js >= 18.0.0" -ForegroundColor Red
    exit 1
}

# Check Node.js version (basic check)
$versionParts = $nodeVersion.Replace('v', '').Split('.')
$majorVersion = [int]$versionParts[0]

if ($majorVersion -lt 18) {
    Write-Host "❌ Node.js version $nodeVersion is too old. Please install Node.js >= 18.0.0" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Install Playwright browsers
Write-Host "🌐 Installing Playwright browsers..." -ForegroundColor Yellow
npx playwright install

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install Playwright browsers" -ForegroundColor Red
    exit 1
}

# Check if healthcare application servers are running
Write-Host "🔍 Checking healthcare application servers..." -ForegroundColor Yellow

# Check frontend server
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 5 -UseBasicParsing
    Write-Host "✅ Frontend server is running on http://localhost:5173" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Frontend server is not running on http://localhost:5173" -ForegroundColor Yellow
    Write-Host "   Please start the frontend server before running tests" -ForegroundColor Yellow
}

# Check backend server
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000" -TimeoutSec 5 -UseBasicParsing
    Write-Host "✅ Backend server is running on http://localhost:8000" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Backend server is not running on http://localhost:8000" -ForegroundColor Yellow
    Write-Host "   Please start the backend server before running tests" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 Setup completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Cyan
Write-Host "1. Make sure healthcare application servers are running" -ForegroundColor White
Write-Host "2. Run smoke tests: npm run test:smoke" -ForegroundColor White
Write-Host "3. Run all tests: npm test" -ForegroundColor White
Write-Host "4. View test reports: npm run test:report" -ForegroundColor White
Write-Host ""
Write-Host "📚 For more information, see README.md" -ForegroundColor Cyan
