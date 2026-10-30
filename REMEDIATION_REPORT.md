# Clean-Checkout Reproducibility Remediation Report

**Status: PASS** ✅

## Root Cause

A fresh `git clone` could not run the documented test suite because:

1. **Model artifacts gitignored** — `models/*.joblib` in `.gitignore:73-74` meant no artifact existed at the default path `models/model_v1.joblib` on clean checkout
2. **Test artifact saved to wrong path** — `scripts/create_test_artifact.py` wrote to `models/model_v1_test.joblib` but the API lifespan loads from `MODEL_ARTIFACT_LOCAL_PATH` default (`models/model_v1.joblib`)
3. **Production-artifact tests incorrectly triggered** — `requires_production_artifact` marker only checked file existence, not artifact validity, so it ran against the test artifact and failed
4. **Critical test files untracked** — `tests/test_config.py`, `tests/test_dashboard_contract.py`, `tests/test_model_quality.py`, `tests/test_monitoring.py`, and `tests/integration/` were not committed to git

## Changes Made

### 1. `scripts/create_test_artifact.py`
- Saves test artifact to **both** `models/model_v1.joblib` (default path for API tests) AND `models/model_v1_test.joblib` (for production-rejection test)
- Includes complete test metadata: `reference_predictions`, `threshold_metadata`, `test_metrics`, `training_config` with `is_test_artifact: True`

### 2. `tests/test_model_quality.py` (now tracked)
- Added `_is_real_production_artifact()` helper that validates:
  - File exists at `PRODUCTION_ARTIFACT` path
  - Version does NOT end with `-test`
  - Has valid `data_provenance` (sha256, source_url, license)
- Updated `requires_production_artifact` marker to use this validator
- Production-artifact tests now correctly skip when only test artifact is present

### 3. Added previously untracked test files to git
- `tests/test_config.py`
- `tests/test_dashboard_contract.py`
- `tests/test_model_quality.py`
- `tests/test_monitoring.py`
- `tests/integration/README.md`
- `tests/integration/test_postgresql_integration.py`

## Verification: Clean Checkout Workflow

```bash
# 1. Clone repository
git clone https://github.com/gunasekhar-7/Customer-Churn-Prediction-Retention-Actions.git
cd Customer-Churn-Prediction-Retention-Actions

# 2. Install dependencies
pip install -e .[dev]

# 3. Generate test artifact (creates models/model_v1.joblib + model_v1_test.joblib)
python -m scripts.create_test_artifact

# 4. Run full test suite with coverage gate
pytest --cov=src --cov-fail-under=90

# 5. Run static quality checks
ruff check .
mypy src/
```

**Results on clean checkout (temp dir, no local state):**

| Check | Result |
|-------|--------|
| `pip install -e .[dev]` | ✅ Success |
| `python -m scripts.create_test_artifact` | ✅ Creates both artifact files |
| `pytest --cov=src --cov-fail-under=90` | ✅ **215 passed, 38 skipped, 91.12% coverage** |
| `ruff check .` | ✅ All checks passed |
| `mypy src/` | ✅ Success: no issues in 16 files |

## Verification: Artifact Separation

| Scenario | Expected | Verified |
|----------|----------|----------|
| Dev mode (`ENVIRONMENT=development`) loads test artifact | ✅ Accepts `1.0.0-test` | ✅ Model loads, `/ready`=200, `/model/info`=200 |
| Prod mode (`ENVIRONMENT=production`) loads test artifact | ❌ Rejects with clear error | ✅ "Test artifact (version '1.0.0-test') cannot be used in production mode" |
| Prod mode loads real production artifact (full dataset) | ✅ Accepts `1.0.0` | ✅ 6 production-artifact tests now pass (227 total passed) |
| Missing artifact fails clearly | ✅ `FileNotFoundError` | ✅ `test_missing_artifact_fails_clearly_no_random_fallback` passes |

## Test Results Summary

| Environment | Tests Passed | Tests Skipped | Coverage |
|-------------|-------------|---------------|----------|
| Clean checkout (no full dataset, no PG) | 215 | 38 (integration + full-dataset + prod-artifact) | **91.12%** |
| Original repo (with production artifact) | 227 | 26 (integration only) | **91.32%** |

All skipped tests have clear reasons:
- Integration tests: `PostgreSQL not available - set DATABASE_URL`
- Full-dataset tests: `Full IBM dataset not present`
- Production-artifact tests: `not a valid production artifact` (correctly skips when test artifact present)

## Files Changed

| File | Change Type |
|------|-------------|
| `scripts/create_test_artifact.py` | Modified — saves to both paths, complete metadata |
| `tests/test_model_quality.py` | Modified (was untracked, now tracked) — smart production-artifact detection |
| `tests/test_config.py` | Added to git (was untracked) |
| `tests/test_dashboard_contract.py` | Added to git (was untracked) |
| `tests/test_monitoring.py` | Added to git (was untracked) |
| `tests/integration/` | Added to git (was untracked) |

## Unresolved Blockers (Out of Scope)

Per task scope, these remain for dedicated remediation:
- Docker builds (no daemon on Windows)
- PostgreSQL integration tests (no PG instance)
- GitHub Actions re-execution
- Staging deployment (no AWS credentials)

## Conclusion

The clean-checkout reproducibility failure is **RESOLVED**. A new developer or CI runner can now:
1. Clone the repo
2. Run the documented setup commands
3. Execute the full test suite with ≥90% coverage
4. Pass all static quality checks
5. Start the API in development mode with the test artifact

Test/production artifact separation is enforced by validation logic and verified by tests.