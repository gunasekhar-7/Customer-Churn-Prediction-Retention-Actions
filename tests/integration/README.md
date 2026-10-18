# PostgreSQL Integration Tests

This directory contains integration tests that verify PostgreSQL-specific behavior for the Customer Churn Prediction Platform.

## Prerequisites

- PostgreSQL 15+ instance
- Python 3.11+
- Dependencies from `requirements-integration.txt`

## Running Locally

### Option 1: Using Docker (Recommended)

```bash
# Start PostgreSQL
docker run -d \
  --name churn-test-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=churn_test \
  -p 5432:5432 \
  postgres:15-alpine

# Run tests
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/churn_test
export TEST_POSTGRES_AVAILABLE=true
pytest tests/integration/ -v
```

### Option 2: Using Local PostgreSQL

```bash
# Ensure PostgreSQL is running and accessible
export DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/churn_test
export TEST_POSTGRES_AVAILABLE=true
pytest tests/integration/ -v
```

### Option 3: Using testcontainers (Automatic)

```bash
# Install testcontainers
pip install -r requirements-integration.txt

# Run tests (testcontainers will start PostgreSQL automatically)
pytest tests/integration/ -v
```

## Running in CI

The GitHub Actions workflow (`.github/workflows/ci.yml`) automatically runs integration tests using a PostgreSQL service container on every push and pull request.

## Test Coverage

The integration tests verify:

### Part A: PostgreSQL Migrations
- Migrations upgrade existing schema correctly
- Schema matches ORM's intended schema
- Timezone migration results in `TIMESTAMP WITH TIME ZONE` columns
- Existing prediction data preserved during migrations
- Migration execution failures handled safely
- Migrations can run repeatedly
- Downgrade/recovery procedures work correctly

### Part B: Timestamp Semantics
- Timestamp creation and retrieval are UTC-consistent
- Naive datetimes treated as UTC by ORM
- Serialization/deserialization preserves timezone info
- Timestamp comparison and ordering works correctly
- Timezone offsets handled correctly
- Historical naive timestamp assumptions documented

### Part C: Database Pooling and Failures
- Connection reuse from pool
- Session cleanup on exceptions
- Recovery after failed transactions
- Pool exhaustion behavior
- Recovery when database temporarily unavailable

### Part D: Data Minimization and Retention
- Sensitive fields excluded from persistence
- Business fields remain available
- Expired records cleaned per retention period
- Boundary records follow documented rules
- Batch cleanup and dry-run behavior
- Repeated cleanup doesn't corrupt data
- Failures don't silently report success
- Minimization metadata and audit statistics accurate

## Test Organization

| Test Class | Purpose |
|------------|---------|
| `TestPostgreSQLMigrations` | Migration behavior verification |
| `TestTimestampSemantics` | Timezone and timestamp handling |
| `TestConnectionPooling` | Pool behavior and failure recovery |
| `TestDataMinimizationAndRetention` | Data protection and cleanup |

## Skipping Integration Tests

Tests are automatically skipped if PostgreSQL is not available:

```bash
# Without DATABASE_URL, tests are skipped with clear message
pytest tests/integration/ -v
# Output: SKIPPED [42] PostgreSQL not available - set DATABASE_URL env var to run integration tests
```

## Troubleshooting

### Connection Refused
```bash
# Check if PostgreSQL is running
docker ps | grep postgres
# or
systemctl status postgresql
```

### Migration Failures
```bash
# Check alembic version
alembic current
# View migration history
alembic history
```

### Permission Issues
```bash
# Ensure test database user has CREATE/DROP permissions
GRANT ALL PRIVILEGES ON DATABASE churn_test TO test_user;
```