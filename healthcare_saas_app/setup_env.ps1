# Environment Setup Script
# This script prompts for database selection and loads appropriate .env file

Write-Host "Environment Setup Script" -ForegroundColor Green
Write-Host "======================" -ForegroundColor Green

# Prompt user for database selection
do {
    $choice = Read-Host "Which database to connect (DEV/TEST)?"
    $choiceUpper = $choice.ToUpper().Trim()
    
    if ($choiceUpper -eq "DEV" -or $choiceUpper -eq "TEST") {
        break
    } else {
        Write-Host "Error: Invalid input. Please enter 'DEV' or 'TEST'." -ForegroundColor Red
    }
} while ($true)

# Determine which file to load
if ($choiceUpper -eq "DEV") {
    $envFile = ".env"
    $databaseMode = "Development"
} else {
    $envFile = ".env.test"
    $databaseMode = "Testing"
}

Write-Host "`nSelected database mode: $databaseMode" -ForegroundColor Yellow
Write-Host "Loading environment variables from $envFile..." -ForegroundColor Yellow

# Check if file exists
if (-not (Test-Path $envFile)) {
    Write-Host "Error: $envFile file not found in current directory!" -ForegroundColor Red
    exit 1
}

# Clear existing environment variables that might be overwritten
Write-Host "Clearing previous environment variables..." -ForegroundColor Cyan

# Load and set environment variables from selected file
$loadedCount = 0
Get-Content $envFile | ForEach-Object {
    if ($_ -match "^([^=]+)=(.*)$") {
        $name = $matches[1]
        $value = $matches[2]
        
        # Set/overwrite the environment variable
        Set-Item -Path "env:$name" -Value $value -Force
        Write-Host "Set $name = $value" -ForegroundColor Cyan
        $loadedCount++
    }
}

if ($loadedCount -gt 0) {
    Write-Host "`nEnvironment variables loaded successfully!" -ForegroundColor Green
    Write-Host "Loaded $loadedCount variables from $envFile" -ForegroundColor Green
    
    # Show key database information
    if ($env:DATABASE_URL) {
        Write-Host "Current DATABASE_URL: $env:DATABASE_URL" -ForegroundColor Yellow
    }
    if ($env:CORS_ORIGINS) {
        Write-Host "Current CORS_ORIGINS: $env:CORS_ORIGINS" -ForegroundColor Yellow
    }
} else {
    Write-Host "Warning: No valid environment variables found in $envFile" -ForegroundColor Yellow
}

Write-Host "`nEnvironment setup complete!" -ForegroundColor Green
