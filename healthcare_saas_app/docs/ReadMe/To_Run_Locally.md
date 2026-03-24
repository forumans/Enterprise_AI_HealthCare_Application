# 🚀 Prequisites & Setup Guide

## 📋 System Requirements
- **Python**: 3.8+ (recommended 3.11+)
- **Node.js**: 16+ (recommended 18+)
- **PostgreSQL**: 12+ (for database)
- **Git**: For cloning the repository
- **PowerShell** (Windows) or Terminal (macOS/Linux)

## 📥 Initial Setup (First Time Only)

### 1) Clone the Repository
```bash
git clone https://github.com/forumans/Gopi_HealthCare_Application.git
cd HealthCare_Application
```

### 2) Create Virtual Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1

# macOS/Linux:
source .venv/bin/activate
```

### 3) Install Python Dependencies
```bash
# Install required Python packages
pip install -r backend/requirements.txt

# Verify installation
pip list
```

### 4) Install Node.js Dependencies
```bash
# Navigate to frontend directory
cd frontend

# Install npm packages
npm install

# Return to root directory
cd ..
```

### 5) Setup Environment Variables
```bash
# Create .env file from template
copy .env.example .env

# OR create manually
# Windows:
echo "# Database Configuration" > .env
echo "DATABASE_URL=postgresql+asyncpg://<your_postgres_username>:<your_postgres_password>@localhost:5432/healthcare_sas" >> .env
echo "" >> .env
echo "# CORS Configuration" >> .env
echo "CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174" >> .env
echo "" >> .env
echo "# JWT Configuration" >> .env
echo "JWT_SECRET=change-me-in-production-use-strong-secret-key-here" >> .env
echo "JWT_ALGORITHM=HS256" >> .env

# macOS/Linux:
cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql+asyncpg://<your_postgres_username>:<your_postgres_password>@localhost:5432/healthcare_sas

# CORS Configuration
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174

# JWT Configuration
JWT_SECRET=change-me-in-production-use-strong-secret-key-here
JWT_ALGORITHM=HS256
EOF
```

### 6) Database Setup
```bash
# Follow the database setup guide
# See: docs/ReadMe/db_setup_local.md

# Quick database test (after setup)
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_connection():
    try:
        engine = create_async_engine('postgresql+asyncpg://<your_postgres_username>:<your_postgres_password>@localhost:5432/healthcare_sas')
        async with engine.begin() as conn:
            result = await conn.execute(text('SELECT version()'))
            version = result.scalar()
            print(f'✅ Database connected successfully: {version}')
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        print('Please check PostgreSQL setup and credentials')

asyncio.run(test_connection())
"
```

## 🚀 Running the Application

### 1) Activate venv (if not active)
.\.venv\Scripts\Activate.ps1

# 2) Configure environment variables
# Option A: Use the setup script (recommended)
.\setup_env.ps1

# Option B: Manual setup
# Edit the .env file in the project root to set your database and other configurations
# The .env file contains:
#   DATABASE_URL=postgresql+asyncpg://your_username:your_password@localhost/healthcare_saas
#   CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174
#   JWT_SECRET=change-me-in-production
#   JWT_ALGORITHM=HS256

# 3) Allow React origin (automatically loaded from .env file)
# $env:CORS_ORIGINS will be set from the .env file when the application starts

# 4) Start FastAPI
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# 4.1) FastAPI docs
http://127.0.0.1:8000/docs

# 4.2) FastAPI Health check
http://127.0.0.1:8000/api/health

# 5) Start React + TypeScript frontend
cd frontend
npm install
npm run dev

# 5.1) Frontend URL
http://127.0.0.1:5173
# Note: Default Vite dev server port is 5173

# 6) Test the connection to database
cd ..
python .\test_healthcare_saas_app\tests\db_connection_test.py

# 7) JWT Settings
$env:JWT_SECRET="change-me-in-production"
$env:JWT_ALGORITHM="HS256"

# 8) SMTP Settings on Hotmail
$env:SMTP_HOST="smtp-mail.outlook.com"
$env:SMTP_PORT="587"
$env:SMTP_USERNAME="your-email@example.com"
$env:SMTP_PASSWORD="your-app-password"
$env:SMTP_FROM="your-email@example.com"

# 9) Run the E2E tests
cd test_healthcare_saas_app
npx playwright test --config=playwright.simple.config.ts

# 9.1) View test reports
npx playwright show-report

# 9.2) Run smoke tests (quick health checks)
npm run test:smoke

# 9.3) Run tests in UI mode (interactive)
npm run test:ui

# 9.4) Run specific test file
npx playwright test --config=playwright.simple.config.ts tests/ui-registration-appointment-final.spec.ts

# 9.5) Test Results
# Expected: All 5 tests should pass with 100% success rate
# - Doctor Registration Form Validations ✅
# - Patient Registration Form Validations ✅  
# - Doctor Registration Complete Flow ✅
# - Patient Registration Complete Flow ✅
# - Patient Appointment Booking Flow ✅

## 🔧 Troubleshooting Guide

### Common Issues and Solutions

#### ❌ **Database Connection Issues**
**Problem**: `sqlalchemy.exc.OperationalError: could not connect to server`
**Solutions**:
1. Verify PostgreSQL is running: `pg_ctl status`
2. Check database exists: `psql -l`
3. Verify user permissions: `psql -U healthcare_user -d healthcare_sas`
4. Update .env file with correct credentials

#### ❌ **CORS Errors**
**Problem**: `Access to fetch at 'http://localhost:5174' has been blocked by CORS policy`
**Solutions**:
1. Check .env file includes port 5174 in CORS_ORIGINS
2. Restart FastAPI server after changing .env
3. Verify frontend is running on correct port (5174)

#### ❌ **Python Module Not Found**
**Problem**: `ModuleNotFoundError: No module named 'fastapi'`
**Solutions**:
1. Activate virtual environment: `.\.venv\Scripts\Activate.ps1`
2. Install dependencies: `pip install -r backend/requirements.txt`
3. Verify Python version: `python --version`

#### ❌ **Node.js Module Not Found**
**Problem**: `Error: Cannot find module 'react'`
**Solutions**:
1. Navigate to frontend directory: `cd frontend`
2. Install dependencies: `npm install`
3. Verify Node.js version: `node --version`

#### ❌ **Port Already in Use**
**Problem**: `Port 8000 is already in use`
**Solutions**:
1. Kill existing process: `netstat -ano | findstr :8000`
2. Use different port: `python -m uvicorn backend.app.main:app --port 8001`
3. Kill process ID: `taskkill /PID <PID> /F`

#### ❌ **Environment Variables Not Loading**
**Problem**: Environment variables not recognized
**Solutions**:
1. Check .env file exists in project root
2. Verify .env file format (no spaces around =)
3. Restart application after changing .env

#### ❌ **Test Failures**
**Problem**: Playwright tests failing
**Solutions**:
1. Install browsers: `npx playwright install`
2. Check test configuration: `npx playwright test --config=playwright.simple.config.ts --dry-run`
3. Verify backend is running before tests

### 📋 Quick Setup Checklist

- [ ] Python 3.8+ installed
- [ ] Node.js 16+ installed
- [ ] PostgreSQL 12+ running
- [ ] Virtual environment created and activated
- [ ] Python dependencies installed
- [ ] Node.js dependencies installed
- [ ] .env file configured
- [ ] Database user created with permissions
- [ ] Database connection verified
- [ ] FastAPI server starts successfully
- [ ] Frontend builds and runs without errors

### 🆘 Getting Help

If you encounter issues not covered here:

1. **Check Logs**: Look at FastAPI console output for error messages
2. **Verify Database**: Use database test script to confirm connectivity
3. **Check Dependencies**: Verify all required packages are installed
4. **Review Configuration**: Double-check .env file settings
5. **Consult Documentation**: Refer to other files in docs/ReadMe/ directory

### 📚 Additional Resources

- **Database Setup**: `docs/ReadMe/db_setup_local.md`
- **Server Architecture**: `docs/ReadMe/Server_Directory_Structure.md`
- **Frontend Structure**: `docs/ReadMe/FrontEnd_Module_Structure.md`
- **Testing Guide**: Enhanced prompts in `docs/prompts/06-testing/` (private)

---

## 🎉 Ready to Develop!

Once setup is complete, you should have:
- ✅ FastAPI backend running on `http://localhost:8000`
- ✅ React frontend running on `http://localhost:5174`
- ✅ Database connection established
- ✅ All tests passing with 100% success rate

**Happy coding!** 🚀
