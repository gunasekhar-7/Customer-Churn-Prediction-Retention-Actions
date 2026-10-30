# Decision Log

## Customer Churn Prediction & Retention Intelligence Platform

This document records key technical decisions, their rationale, and alternatives considered.

---

## ML & Model Decisions

### DL-001: Logistic Regression over XGBoost/Random Forest
**Date:** 2026-10-15  
**Decision:** Selected Logistic Regression as primary production model.  
**Rationale:** 
- ROC-AUC 0.841 (vs XGBoost 0.814, RF 0.821) on full dataset
- Native SHAP LinearExplainer (fast, exact) vs TreeExplainer/KernelExplainer approximations
- Regulatory interpretability: coefficients directly explainable to business stakeholders
- 10x faster inference than ensemble methods
- Lower memory footprint for container deployment

**Alternatives:** XGBoost (better calibration but slower SHAP), Random Forest (more complex, no LinearExplainer)  
**ADR:** [001-model-selection-logistic-regression.md](adr/001-model-selection-logistic-regression.md)

---

### DL-002: Threshold Selection Rule
**Date:** 2026-10-16  
**Decision:** Maximize precision subject to recall ≥ 0.70 on validation set.  
**Rationale:**
- Business requirement: catch at least 70% of churners
- Precision optimization minimizes false-positive retention spend
- Threshold selected on validation only; test set used once for final gate
- Selected threshold: 0.6478 (val precision 0.5950, val recall 0.7032)

**Alternatives:** F1-maximizing (recall ~0.55), fixed 0.5 (recall ~0.78, precision ~0.45), cost-based (requires intervention cost data)  
**ADR:** [004-threshold-selection-rule.md](adr/004-threshold-selection-rule.md)

---

### DL-003: Quality Gate on Held-Out Test Set
**Date:** 2026-10-16  
**Decision:** Enforce ROC-AUC ≥ 0.80 on held-out test set; refuse serialization if failed.  
**Rationale:**
- Prevents optimistic bias from threshold tuning on test set
- Test set used exactly once — for final quality gate
- CI enforces gate; test artifact creation uses `--skip-quality-gate`
- Full dataset passes (0.8320); 100-row sample fails (0.3214)

**Alternatives:** Cross-validation only, no gate, PR-AUC gate — rejected for production rigor

---

### DL-004: SHAP Background from Validation Set
**Date:** 2026-10-16  
**Decision:** Use 100 samples from validation set for LinearExplainer background.  
**Rationale:**
- Preprocessor fit on train only → no leakage
- Validation set distribution matches training-time transformations
- Test set never used for any model configuration
- Sample size 100 balances speed and stability for LinearExplainer

**Alternatives:** Training set (leakage risk), test set (contamination), synthetic (distribution mismatch)  
**Documented:** `scripts/train_and_serialize.py:311-314` comment

---

## Data & Privacy Decisions

### DL-005: Three-Tier Field Taxonomy for Minimization
**Date:** 2026-10-18  
**Decision:** Classify 44 fields as Sensitive (44), Safe (1: tenure), Business-Required (4: Contract, MonthlyCharges, InternetService, TechSupport).  
**Rationale:**
- Safe default: only tenure persisted unless business fields opt-in
- Business fields needed for retention rules and revenue exposure
- Sensitive fields (PII, financial, demographic) excluded by default
- Metadata tracks minimization (`_minimized`, `_minimized_at`, counts)

**Alternatives:** Full retention, all-field minimization, per-field config — rejected for operational simplicity  
**ADR:** [003-data-minimization-fields.md](adr/003-data-minimization-fields.md)

---

### DL-006: Salted SHA-256 Pseudonymization with Lookup Table
**Date:** 2026-10-24  
**Decision:** Hash customer IDs with salted SHA-256; maintain authorized lookup table for re-identification.  
**Rationale:**
- Pseudonymization (reversible by authorized) ≠ Anonymization (irreversible)
- Salt prevents rainbow tables; per-deployment salt via `PSEUDONYMIZATION_SALT`
- Lookup table (`customer_pseudonym_lookup`) enables DSAR compliance
- Access logging (count, timestamp) for audit trail
- Production requires 16+ char salt; dev uses default with warning

**Alternatives:** Tokenization (external service), encryption (key management), full anonymization (breaks retention logic)

---

### DL-007: Configurable Retention with Dry-Run
**Date:** 2026-10-18  
**Decision:** 90-day default retention, batch cleanup (1000 records), dry-run mode, cascade delete.  
**Rationale:**
- 90 days aligns with typical analytics retention policies
- Batch size prevents long transactions/locks
- Dry-run (`DATA_RETENTION_DRY_RUN`) enables safe verification
- Cascade deletes recommendations with predictions (FK constraint)
- Stats endpoint (`get_retention_stats`) for monitoring

---

## Monitoring & Drift Decisions

### DL-008: Population-Level PSI/KS Drift (Not Per-Request)
**Date:** 2026-10-16  
**Decision:** Background `MonitoringService` evaluates PSI/KS on rolling 1000-prediction window every 5 minutes.  
**Rationale:**
- Per-request drift (single sample vs historical mean) is statistically meaningless
- Population PSI on 1000-sample window has statistical power
- PSI > 0.1 = drift alert, PSI > 0.05 = warning, KS p-value < 0.05 = alert
- Reference distribution from 1409 validation predictions

**Removed:** `check_drift_thresholds()` deprecated per-request function  
**ADR:** [002-drift-detection-psi-ks.md](adr/002-drift-detection-psi-ks.md)

---

### DL-009: Multi-Worker Drift Limitation Documented
**Date:** 2026-10-25  
**Decision:** Document that each worker runs independent `MonitoringService` with separate window.  
**Rationale:**
- No shared state across workers in current architecture
- Worker with low traffic may have insufficient samples
- Alerts may fire inconsistently across workers
- Mitigation options documented: Redis externalization, centralized aggregation, single-worker monitor

**Documented:** `docs/MLOPS_AND_MONITORING.md:20-45`

---

## API & Serving Decisions

### DL-010: File-Based Model Versioning (No MLflow)
**Date:** 2026-10-25  
**Decision:** Semantic versioning via `models/*.joblib` filenames + embedded metadata; test artifacts excluded.  
**Rationale:**
- Zero external dependencies for version management
- Artifact metadata contains version, metrics, provenance, threshold
- `list_model_versions()` scans filesystem, parses semver
- `X-Model-Version` header on all responses for client tracking
- Extensible to A/B testing via API key routing

**Alternatives:** MLflow (extra infra), DB-backed (coupling), single model (no rollback)  
**ADR:** [006-model-versioning-strategy.md](adr/006-model-versioning-strategy.md)

---

### DL-011: API Key Hashed in Rate Limit Keys
**Date:** 2026-10-25  
**Decision:** Rate limit key uses `sha256(api_key)[:8]` instead of raw prefix.  
**Rationale:**
- Original code used `api_key[:8]` — leaked partial key in logs/metrics
- Hash prevents key reconstruction from rate limit identifiers
- First 8 chars of SHA-256 sufficient for cardinality
- Consistent with security-first logging principle

**Fixed:** `src/api.py:204` — `get_rate_limit_key()` now hashes

---

### DL-012: Request ID Propagation Middleware
**Date:** 2026-10-25  
**Decision:** `RequestIDMiddleware` extracts/generates `X-Request-ID`, stores in `request.state`, adds to response headers and logs.  
**Rationale:**
- Enables distributed tracing across API, workers, database
- Clients can correlate requests with logs
- UUID v4 generation if client doesn't provide
- Structured JSON logs include `request_id` field

---

### DL-013: Model Version Header on All Responses
**Date:** 2026-10-25  
**Decision:** `ModelVersionHeaderMiddleware` adds `X-Model-Version` to every response.  
**Rationale:**
- Clients detect model changes without polling `/model/info`
- Enables debugging: "which model served this prediction?"
- Works with `RequestIDMiddleware` for full request context

---

## Infrastructure Decisions

### DL-014: SQLite Fallback for Local Development
**Date:** 2026-10-12  
**Decision:** `config.py:226-237` — `database_url_or_sqlite` returns SQLite if `DATABASE_URL` unset.  
**Rationale:**
- Enables `pip install -e . && uvicorn src.api:app` without Docker
- CI can run tests without PostgreSQL service
- Production requires explicit `DATABASE_URL` (validated in `validate_production_config`)

**ADR:** [005-sqlite-fallback-pattern.md](adr/005-sqlite-fallback-pattern.md)

---

### DL-015: SHA-256 Placeholder Pattern for Artifact Integrity
**Date:** 2026-10-16  
**Decision:** Serialize with `0*64` placeholder, compute hash, binary-replace, re-serialize.  
**Rationale:**
- Hash of artifact with placeholder = hash of artifact with actual hash
- Binary replacement preserves pickle structure (both 64-char hex)
- Verification reverses process: replace stored hash with placeholder, recompute
- Tampering changes hash → startup validation fails

**Implementation:** `src/model_management.py:70-116` (serialize), `168-188` (verify)

---

### DL-016: Webhook Secret Required When URL Set
**Date:** 2026-10-25  
**Decision:** `model_validator` in `Settings` requires `DRIFT_WEBHOOK_SECRET` if `DRIFT_WEBHOOK_URL` configured.  
**Rationale:**
- Webhook without secret is spoofable
- HMAC-SHA256 signature verification in `send_drift_webhook`
- Validation at config load fails fast in production

**Implementation:** `src/config.py:238-243` — `validate_webhook_config` model_validator

---

## Rejected Alternatives

| Decision | Rejected Alternative | Reason |
|----------|---------------------|--------|
| DL-001 | XGBoost as primary | Slower SHAP, no LinearExplainer, marginal ROC-AUC gain |
| DL-002 | F1-maximizing threshold | Recall 0.55 misses too many churners |
| DL-003 | No quality gate | Risk of deploying degraded models |
| DL-004 | SHAP background from training | Leakage: preprocessor fit on train |
| DL-005 | Per-field minimization config | Operational complexity, inconsistent defaults |
| DL-006 | Full anonymization | Breaks retention logic needing customer linkage |
| DL-008 | Per-request drift check | Statistically invalid, high false positives |
| DL-010 | MLflow model registry | Infrastructure overhead for single-model service |
| DL-014 | Required PostgreSQL always | Blocks local development without Docker |

---

## Future Decisions (Deferred)

| ID | Topic | Trigger |
|----|-------|---------|
| FD-001 | Async SQLAlchemy | Throughput requirements exceed sync ORM |
| FD-002 | Redis rate limiting | Multi-worker deployment |
| FD-003 | Feature store (Feast) | Point-in-time correctness, lineage |
| FD-004 | A/B testing framework | Business request for gradual rollout |
| FD-005 | Automated retraining trigger | Drift alerts sustained > 24h |
| FD-006 | Model registry UI | Team growth, model lineage needs |

---

## Change Log

| Date | Decision IDs | Summary |
|------|--------------|---------|
| 2026-10-15 | DL-001, DL-014 | Model selection, SQLite fallback |
| 2026-10-16 | DL-002, DL-003, DL-004, DL-008, DL-015 | Threshold, quality gate, SHAP, drift, artifact integrity |
| 2026-10-18 | DL-005, DL-007 | Minimization taxonomy, retention policy |
| 2026-10-24 | DL-006 | Pseudonymization |
| 2026-10-25 | DL-009, DL-010, DL-011, DL-012, DL-013, DL-016 | Multi-worker docs, versioning, rate limit hash, request ID, model header, webhook secret |