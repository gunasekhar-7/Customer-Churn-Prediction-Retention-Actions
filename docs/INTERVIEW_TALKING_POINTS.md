# Interview Talking Points

## Customer Churn Prediction & Retention Intelligence Platform

This document maps 7 concrete technical stories to specific code locations for interview discussions.

---

## 1. ML Hygiene: Preventing Data Leakage in Training & SHAP

**Story:** "I designed the training pipeline to prevent leakage at three levels: data split, preprocessing, and explainability."

**Evidence:**
- **3-way split (60/20/20):** `scripts/train_and_serialize.py:222-228` — stratified split before any preprocessing
- **Preprocessor fit on train only:** `train_and_serialize.py:237` — `fit_transform` on train, `transform` on val/test
- **SHAP background from validation:** `train_and_serialize.py:311-314` — explicit comment: "NO LEAKAGE: Preprocessor fit ONLY on training data... SHAP background comes from validation set, NOT test set"

**Why it matters:** Many projects leak by fitting preprocessor on full data or using test set for SHAP background. This affects reported metrics and production reliability.

**Follow-up:** "How would you verify no leakage in a new feature engineering step?" → Add assertion that feature statistics match between train and transformed val/test.

---

## 2. Artifact Integrity: SHA-256 with Placeholder Replacement

**Story:** "I implemented a tamper-evident model artifact format using SHA-256 with binary placeholder replacement."

**Evidence:**
- **Serialization:** `src/model_management.py:70-116` — serialize with `0*64` placeholder, compute hash, binary-replace in bytes, re-serialize
- **Verification:** `model_management.py:168-188` — reverse process: replace stored hash with placeholder, recompute, compare
- **Production check:** `model_management.py:219-224` — rejects `-test` artifacts when `require_production=True`

**Why it matters:** In production, model artifacts can be swapped or corrupted. This pattern ensures the loaded artifact exactly matches the serialized bytes.

**Follow-up:** "How would you extend this for multi-model ensembles?" → Compute combined hash of all component artifacts, store in parent manifest.

---

## 3. Population-Level Drift Detection (Not Per-Request)

**Story:** "I recognized that per-request drift checks are statistically invalid and built a proper population-level monitor."

**Evidence:**
- **Deprecated removal:** `tests/test_monitoring.py` — removed `check_drift_thresholds` tests
- **Population monitor:** `src/monitoring.py:156-398` — `PopulationDriftDetector` with rolling window, PSI/KS evaluation every 5 min
- **Multi-worker docs:** `docs/MLOPS_AND_MONITORING.md:20-45` — documented limitation: each worker has independent window, alerts may fire inconsistently
- **Mitigation options:** Redis externalization, centralized aggregation, or single-worker monitor

**Why it matters:** Per-request KS test on single prediction vs historical mean has no statistical power. Population PSI on 1000-sample windows is the industry standard.

**Follow-up:** "How would you implement feature-level drift?" → `DriftConfig.feature_names` + `feature_psi_threshold` in `monitoring.py:132-134` — computes PSI per feature using reference feature distributions.

---

## 4. Customer ID Pseudonymization with Authorized Lookup

**Story:** "I implemented GDPR-aligned pseudonymization: salted SHA-256 hashes in main table, reversible lookup for authorized personnel only."

**Evidence:**
- **Hashing:** `src/data_protection.py:77-90` — `pseudonymize_customer_id()` uses `SHA-256(salt:customer_id)`
- **Lookup table:** `src/models.py:48-68` — `CustomerPseudonymLookup` with unique hash, access count, timestamps
- **Authorized resolution:** `data_protection.py:136-170` — `resolve_customer_id()` requires `authorized=True`, logs unauthorized attempts
- **Audit trail:** Access count and `last_accessed_at` updated on each resolution

**Why it matters:** Raw customer IDs in prediction tables are PII. Pseudonymization reduces blast radius; lookup table enables legal compliance (DSAR) without exposing IDs to all analysts.

**Follow-up:** "How would you rotate the salt?" → Re-hash all `customer_id_hash` values with new salt, update lookup table in transaction, maintain old salt for grace period.

---

## 5. Model Versioning Without External Registry

**Story:** "I built file-based model versioning with semantic ordering, test artifact exclusion, and client-side headers — no MLflow dependency."

**Evidence:**
- **Discovery:** `src/model_management.py:339-385` — `list_model_versions()` scans `models/*.joblib`, parses metadata
- **Current selection:** `model_management.py:388-402` — `get_current_model_version()` returns latest non-test by semver
- **API endpoints:** `src/api.py:513-570` — `/model/versions`, `/model/current` with full metadata
- **Client header:** `src/api.py:340-347` — `ModelVersionHeaderMiddleware` adds `X-Model-Version` to all responses

**Why it matters:** External registries add infrastructure complexity. For a single-model service, filesystem + metadata is sufficient and auditable.

**Follow-up:** "How would you add A/B testing?" → Extend `get_rate_limit_key` or new middleware to route by API key suffix to different model versions loaded in same process.

---

## 6. Configurable Data Minimization with Field Taxonomy

**Story:** "I designed a three-tier field classification (sensitive/safe/business-required) with production-safe defaults."

**Evidence:**
- **Taxonomy:** `src/data_protection.py:24-62` — 44 sensitive, 1 safe (tenure), 4 business-required fields
- **Minimization logic:** `data_protection.py:173-210` — `get_minimized_features()` returns only allowed fields + metadata
- **Config-driven:** `src/config.py:141-144` — `DATA_MINIMIZATION_ENABLED` toggle
- **Retention fields:** `data_protection.py:258-272` — `create_prediction_record()` applies minimization automatically

**Why it matters:** Storing 44 fields per prediction creates compliance risk. Default-minimized with business-field override balances privacy and analytics needs.

**Follow-up:** "How would you handle a new field that's needed for a new retention rule?" → Add to `BUSINESS_REQUIRED_FIELDS` in `data_protection.py:57-62`, no code changes elsewhere.

---

## 7. Request ID Propagation for Distributed Tracing

**Story:** "I implemented end-to-end request ID flow: generated/extracted at edge, stored in request state, logged, added to response headers."

**Evidence:**
- **Middleware:** `src/api.py:352-373` — `RequestIDMiddleware` extracts `X-Request-ID` or generates UUID
- **State storage:** `api.py:364-365` — `request.state.request_id = request_id`
- **Metrics logging:** `api.py:323` — `log_request_metrics()` includes `request_id` in extra metadata
- **Response header:** `api.py:371` — `response.headers["X-Request-ID"] = request_id`

**Why it matters:** In multi-worker deployments, request IDs correlate logs across workers, enable traceability from API gateway to database.

**Follow-up:** "How would you integrate with OpenTelemetry/Jaeger?" → Add `X-B3-TraceId` header propagation, emit spans in middleware and route handlers.

---

## Quick Reference: Code Location Index

| Topic | Primary Files |
|-------|---------------|
| Training pipeline | `scripts/train_and_serialize.py` |
| Model artifact I/O | `src/model_management.py` |
| API endpoints | `src/api.py` |
| Drift monitoring | `src/monitoring.py` |
| Data protection | `src/data_protection.py` |
| Database models | `src/models.py` |
| Configuration | `src/config.py` |
| Retention logic | `src/retention_intelligence.py` |
| Explainability | `src/explainability.py` |

---

## Behavioral Questions Preparation

**"Tell me about a time you made a trade-off between model performance and engineering constraints."**
→ Chose Logistic Regression (ROC-AUC 0.841) over XGBoost (0.814) for SHAP LinearExplainer compatibility, faster inference, and regulatory interpretability. Documented in ADR 001.

**"Describe a production incident you prevented through design."**
→ Artifact SHA-256 validation catches tampered models at startup. Test artifact rejection prevents CI artifacts from reaching production. Both enforced in `model_management.py:219-224`.

**"How do you handle schema evolution in ML pipelines?"**
→ Pydantic `TelcoCustomerFeatures` with `extra="forbid"` catches unexpected fields at API boundary. Alembic migrations for DB. Preprocessor handles missing categories via `handle_unknown="ignore"`.

**"What would you improve given more time?"**
1. Async SQLAlchemy for higher throughput (Phase 2.4)
2. Redis-backed rate limiting for multi-worker
3. Feature store for lineage and point-in-time correctness
4. Automated retraining trigger API (Phase 2.7)
5. Canary deployment with traffic splitting