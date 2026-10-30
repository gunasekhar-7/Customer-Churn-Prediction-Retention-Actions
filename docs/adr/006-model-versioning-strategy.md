# ADR 006: Model Versioning Strategy

## Status
Accepted

## Context
The Customer Churn Prediction platform needs a strategy for managing multiple model versions in production. The system must support:
1. Multiple model artifacts coexisting in the `models/` directory
2. Clear identification of the current production model
3. API endpoints to query model versions and metadata
4. Client-side version tracking via response headers
5. A clean path for future A/B testing or gradual rollouts

## Decision
We implement a **file-based model versioning system** with the following characteristics:

### 1. Version Discovery
- Model artifacts are stored as `.joblib` files in the `models/` directory
- Version is extracted from the artifact's embedded metadata (`metadata.version`)
- The current production model is the **latest non-test artifact** by semantic version
- Test artifacts (version ending in `-test`) are excluded from production consideration

### 2. API Endpoints
- `GET /model/versions` — Lists all available versions with metadata and marks current
- `GET /model/current` — Returns detailed info for the current production model
- `GET /model/info` — Returns info for the model loaded in the current process
- `GET /model/metrics` — Returns performance metrics from artifact metadata

### 3. Client-Side Version Tracking
- All responses include `X-Model-Version` header with the serving model's version
- Clients can detect model changes without additional API calls
- Enables debugging and audit trails

### 4. Loading Strategy
- At startup, FastAPI lifespan loads the current production model via `get_model_artifact()`
- The artifact is cached in memory per worker process
- Model can be updated by adding a new artifact file and restarting workers

## Alternatives Considered

### Alternative 1: External Model Registry (MLflow, MLflow Tracking Server)
**Pros:** Centralized management, UI, experiment tracking, staging/production transitions
**Cons:** Additional infrastructure, complexity, network dependency, overkill for current scope

### Alternative 2: Database-Backed Versioning
**Pros:** Queryable, transactional, supports metadata queries
**Cons:** Additional schema, migration complexity, coupling to DB availability at startup

### Alternative 3: Single Model with Rolling Updates
**Pros:** Simple, no version management needed
**Cons:** No rollback capability, no audit trail, no gradual rollout support

## Consequences

### Positive
- Zero external dependencies for version management
- Transparent version discovery from filesystem
- Semantic versioning enables clear ordering
- Test artifacts explicitly excluded from production
- Easy rollback: remove or rename the new artifact file
- Extensible for future A/B testing (e.g., route by API key suffix)

### Negative
- Requires process restart to pick up new model (acceptable for current scale)
- Multi-worker deployments need coordinated restarts
- No built-in canary/deployment pipeline (manual today)

## Implementation Details
- `src/model_management.py`: `list_model_versions()`, `get_current_model_version()`
- `src/api.py`: New endpoints + `ModelVersionHeaderMiddleware`
- `src/schema.py`: `ModelVersionInfo`, `ModelVersionsResponse`, `ModelCurrentResponse`
- Alembic migration not required (no DB schema changes)

## References
- [Model Management Module](src/model_management.py)
- [API Endpoints](src/api.py)
- [Semantic Versioning](https://semver.org/)