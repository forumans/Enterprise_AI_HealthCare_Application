# Test Execution Matrix

## Central Orchestration

Working directory:
- `test_healthcare_saas_app`

### All suites
```bash
npm test
```

### Individual suites
```bash
npm run test:unit:backend
npm run test:unit:frontend
npm run test:integration
npm run test:e2e
```

## Recommended Execution Order

1. Backend unit
2. Frontend unit
3. Integration
4. E2E

## Local Pre-Run Checklist

1. Backend service up at `API_BASE_URL`
2. Frontend service up at `FRONTEND_BASE_URL`
3. Admin E2E credentials exported (if running E2E)

## CI Guidance

- Run unit suites on every commit
- Run integration on pull requests
- Run E2E on merge-to-main and nightly schedule
