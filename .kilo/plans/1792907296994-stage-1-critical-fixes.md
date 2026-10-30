# Stage 1 Implementation Plan: Critical Fixes

**Goal:** Eliminate red flags in the codebase — true pseudonymization, correct SHAP explanations, proper idempotency, configurable drift detection.

**Context:** Based on code review findings and portfolio enhancement plan. All changes must maintain 175 passing tests, mypy/ruff clean.

---

## Task 1.1: Fix SHAP KernelExplainer Fallback

**Problem:** `explainability.py:52` uses `model.predict_proba` directly for unknown model types, bypassing the preprocessor.

**Solution:** Apply preprocessor transform before calling predict_proba in the fallback.

**Files:** `src/explainability.py`

**Implementation:**
```python
# In get_shap_explainer, KernelExplainer fallback:
# Current: return shap.KernelExplainer(model.predict_proba, shap.sample(X_background, 100))
# Fixed: Create a wrapper that applies preprocessor first

def _make_predict_proba_wrapper(model, preprocessor):
    def predict_proba_wrapper(X):
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X, columns=preprocessor.feature_names_in_)
        X_transformed = preprocessor.transform(X)
        return model.predict_proba(X_transformed)
    return predict_proba_wrapper

# Then in fallback:
# wrapper = _make_predict_proba_wrapper(model, preprocessor)
# return shap.KernelExplainer(wrapper, shap.sample(X_background, 100))
```

**Validation:** Test with a dummy non-linear model; verify SHAP values match manual calculation.

---

## Task 1.2: Remove Plaintext `customer_id` from PredictionRecord

**Problem:** `customer_id` stored in plaintext alongside `customer_id_hash` — defeats pseudonymization.

**Solution:** 
1. Remove `customer_id` column from `PredictionRecord` model
2. Update `create_prediction_record` to only store hash
3. Create Alembic migration to drop column
4. Update dashboard queries to use lookup table for authorized access

**Files:** 
- `src/models.py` (remove column)
- `src/data_protection.py` (update `create_prediction_record`)
- `src/api.py` (update prediction endpoints)
- New Alembic migration: `alembic/versions/..._remove_customer_id_plaintext.py`

**Migration Strategy:**
```python
# upgrade()
op.drop_column('prediction_records', 'customer_id')
# Note: customer_id_hash already has index and unique constraint via lookup table

# downgrade()
op.add_column('prediction_records', sa.Column('customer_id', sa.String(), nullable=False))
```

**Validation:** 
- All API tests pass
- Dashboard metrics still work (uses lookup table)
- `resolve_customer_id` works for authorized access

---

## Task 1.3: Fix Dashboard `/explain` Retry Logic

**Problem:** `dashboard/api_client.py:26-30` marks `/explain` (POST) as idempotent and retries it. POST should not auto-retry for non-idempotent operations.

**Solution:** Remove `/explain` from `IDEMPOTENT_ENDPOINTS`. It's a read operation but uses POST for body size; retry could cause duplicate explanations.

**Files:** `dashboard/api_client.py`

**Implementation:**
```python
IDEMPOTENT_ENDPOINTS = {
    "/health",
    "/model/info",
    # "/explain",  # REMOVE - POST with body, not safe to retry
}
```

**Alternative:** If explanation generation is truly idempotent (same input → same output), document why and keep. But safer to remove.

**Validation:** Dashboard tests pass; manual verify no duplicate explanations on network hiccup.

---

## Task 1.4: Move Hardcoded DriftConfig to Config

**Problem:** `api.py:270-278` hardcodes `DriftConfig` parameters. Should be configurable via environment variables.

**Solution:** Add drift config fields to `Settings` class, use them in lifespan.

**Files:** 
- `src/config.py` (add fields)
- `src/api.py` (use settings in lifespan)

**Implementation in `config.py`:**
```python
# Drift Detection Configuration
DRIFT_PSI_THRESHOLD: float = Field(default=0.1, description="PSI threshold for drift alert")
DRIFT_PSI_WARNING: float = Field(default=0.05, description="PSI threshold for drift warning")
DRIFT_KS_THRESHOLD: float = Field(default=0.05, description="KS test p-value threshold for drift")
DRIFT_MIN_SAMPLES: int = Field(default=100, description="Minimum samples for drift detection")
DRIFT_WINDOW_SIZE: int = Field(default=1000, description="Rolling window size for drift detection")
DRIFT_EVALUATION_INTERVAL_SEC: int = Field(default=300, description="Drift evaluation interval in seconds")
DRIFT_FEATURE_PSI_THRESHOLD: float = Field(default=0.1, description="Feature-level PSI threshold")
DRIFT_FEATURE_KS_THRESHOLD: float = Field(default=0.05, description="Feature-level KS threshold")
```

**In `api.py` lifespan:**
```python
monitoring_service = MonitoringService(
    config=DriftConfig(
        reference_predictions=ref_predictions,
        psi_threshold=settings.DRIFT_PSI_THRESHOLD,
        psi_warning=settings.DRIFT_PSI_WARNING,
        ks_threshold=settings.DRIFT_KS_THRESHOLD,
        min_samples=settings.DRIFT_MIN_SAMPLES,
        window_size=settings.DRIFT_WINDOW_SIZE,
        evaluation_interval_sec=settings.DRIFT_EVALUATION_INTERVAL_SEC,
        feature_psi_threshold=settings.DRIFT_FEATURE_PSI_THRESHOLD,
        feature_ks_threshold=settings.DRIFT_FEATURE_KS_THRESHOLD,
        on_drift_result=lambda result: DRIFT_PSI.set(result.psi_score or 0.0) if result.psi_score else None
    ),
    ...
)
```

**Validation:** Tests pass; verify env var override works.

---

## Cross-Cutting Concerns

### Testing
- Run full test suite after each task: `pytest --ignore=tests/test_dashboard_contract.py --ignore=tests/integration`
- Ensure mypy/ruff clean: `mypy src/ && ruff check src/`
- Add specific tests for:
  - SHAP fallback with preprocessor
  - Pseudonymization without plaintext storage
  - Drift config from env vars

### Migration Safety
- Task 1.2 requires DB migration. Run `alembic upgrade head` in CI.
- Test downgrade path works.
- Backup: `customer_id` still available in `customer_pseudonym_lookup` for authorized access.

### Rollback Plan
- Each task is independent; can merge separately.
- If Task 1.2 breaks dashboard, revert migration and keep `customer_id` column temporarily.

---

## Execution Order

1. **Task 1.1** (SHAP fix) — isolated, low risk
2. **Task 1.3** (Dashboard retry) — isolated, low risk  
3. **Task 1.4** (Drift config) — isolated, low risk
4. **Task 1.2** (Remove customer_id) — requires migration, highest risk, do last

---

## Success Criteria

- [ ] All 175 tests pass
- [ ] `mypy src/` clean
- [ ] `ruff check src/` clean
- [ ] `customer_id` column dropped from `prediction_records`
- [ ] SHAP explanations correct for all model types
- [ ] Dashboard `/explain` not retried
- [ ] Drift thresholds configurable via env vars
- [ ] No plaintext customer IDs in prediction records table