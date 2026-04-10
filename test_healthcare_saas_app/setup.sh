#!/bin/bash

# Healthcare E2E Test Setup Script
# This script helps set up the independent E2E test environment

echo "🚀 Setting up Healthcare E2E Test Suite..."
echo "=========================================="

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js >= 18.0.0"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2)
REQUIRED_VERSION="18.0.0"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$NODE_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Node.js version $NODE_VERSION is too old. Please install Node.js >= $REQUIRED_VERSION"
    exit 1
fi

echo "✅ Node.js version: $NODE_VERSION"

# Install dependencies
echo "📦 Installing dependencies..."
npm install

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
npx playwright install

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Playwright browsers"
    exit 1
fi

# Check if healthcare application servers are running
echo "🔍 Checking healthcare application servers..."

# Check frontend server
if curl -s http://localhost:5173 > /dev/null; then
    echo "✅ Frontend server is running on http://localhost:5173"
else
    echo "⚠️  Frontend server is not running on http://localhost:5173"
    echo "   Please start the frontend server before running tests"
fi

# Check backend server
if curl -s http://localhost:8000 > /dev/null; then
    echo "✅ Backend server is running on http://localhost:8000"
else
    echo "⚠️  Backend server is not running on http://localhost:8000"
    echo "   Please start the backend server before running tests"
fi

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Make sure healthcare application servers are running"
echo "2. Run smoke tests: npm run test:smoke"
echo "3. Run all tests: npm test"
echo "4. View test reports: npm run test:report"
echo ""
echo "📚 For more information, see README.md"
