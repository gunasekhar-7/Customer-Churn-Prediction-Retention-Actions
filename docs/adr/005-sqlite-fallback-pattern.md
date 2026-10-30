# ADR 005: Database — SQLite Fallback for Local Development

**Status**: Accepted
**Date**: 2026-10-24

## Context

The application uses PostgreSQL in production but developers need to run locally without a full PostgreSQL instance. Options for local development:

1. **Require local PostgreSQL** (Docker or native) — friction for contributors
2. **SQLite file-based** — zero config, but some SQL differences
3. **SQLite in-memory** — fastest, but no persistence across restarts
4. **Mock/fake DB** — high maintenance, diverges from production

## Decision

Use **SQLite file-based** (`sqlite:///./churn_dev.db`) as the default local development database with automatic fallback.

### Implementation

`src/config.py::database_url_or_sqlite`:

```python
@property
def database_url_or_sqlite(self) -> str:
    if self.DATABASE_URL:
        return self.DATABASE_URL
    if self.is_production:
        raise RuntimeError("DATABASE_URL must be set in production")
    return "sqlite:///./churn_dev.db"
```

Engine creation (`src/database.py`) handles both:
- **PostgreSQL**: Connection pooling, pre-ping, recycle
- **SQLite**: `check_same_thread=False`, pooling disabled

### Schema Compatibility

All models use SQLAlchemy ORM with types compatible with both dialects:
- `DateTime(timezone=True)` → PostgreSQL `TIMESTAMPTZ`, SQLite `TEXT` (ISO format)
- `JSON` → PostgreSQL `JSONB`, SQLite `TEXT` (JSON serialized)
- `Index` definitions work on both

### Test Override

Tests can inject a custom engine (including in-memory SQLite) via `set_engine()` for isolation.

## Consequences

**Positive**:
- Zero-config local development (`git clone && pip install -e . && python -m scripts.create_test_artifact`)
- CI can run unit tests with in-memory SQLite (fast, isolated)
- Production requires explicit `DATABASE_URL` (fail-fast if missing)
- Same ORM code path for both dialects

**Negative**:
- SQLite has weaker type enforcement (e.g., allows string in integer column)
- Some PostgreSQL features unavailable locally (advisory locks, `FOR UPDATE SKIP LOCKED`)
- Schema migrations tested only on PostgreSQL in CI
- Concurrent writer limitations in SQLite (not an issue for single-user dev)

## Mitigations

- Integration tests run against real PostgreSQL in CI
- Alembic migrations tested on PostgreSQL
- Type validation at application layer (Pydantic) catches most issues

## References

- `src/config.py`: Configuration with fallback logic
- `src/database.py`: Engine creation with dialect-specific settings
- `tests/integration/test_postgresql_integration.py`: PostgreSQL-specific tests
- `alembic/versions/`: Migrations tested on PostgreSQL