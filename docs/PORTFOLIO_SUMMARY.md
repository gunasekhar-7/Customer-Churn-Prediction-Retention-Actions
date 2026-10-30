# Technical Portfolio Summary

## Customer Churn Prediction & Retention Intelligence Platform

**Role:** Senior ML Engineer (Portfolio Project)  
**Duration:** End-to-end implementation  
**Tech Stack:** Python 3.11, FastAPI, PostgreSQL, SQLAlchemy, Scikit-learn, SHAP, Docker, GitHub Actions

---

## Problem Statement
Telecommunications companies lose 15-25% of customers annually to churn. Retaining existing customers is 5-7x cheaper than acquiring new ones. This platform predicts churn probability, quantifies revenue exposure, and generates automated retention actions using Explainable AI.

---

## Solution Overview

### Architecture
```
Data → Preprocessing → Training (Logistic Regression) → 
Artifact (SHA-256 verified) → FastAPI → PostgreSQL + Monitoring → Streamlit Dashboard
```

### Key Components
| Component | Technology | Purpose |
|-----------|------------|---------|
| API | FastAPI, Pydantic | Async prediction serving, OpenAPI docs |
| Model | Scikit-learn, Logistic Regression | ROC-AUC 0.8320, threshold 0.6478 |
| Explainability | SHAP (LinearExplainer) | Per-prediction feature contributions |
| Database | PostgreSQL, SQLAlchemy, Alembic | Predictions, pseudonyms, recommendations |
| Monitoring | Custom PSI/KS detector | Population drift detection (5-min intervals) |
| Dashboard | Streamlit, Plotly | Business intelligence UI |

---

## Engineering Highlights

### 1. ML Hygiene & Validation
- **Strict 60/20/20 split** with threshold selection on validation only
- **Quality gate:** ROC-AUC ≥ 0.80 on held-out test set (enforced in CI)
- **No leakage:** Preprocessor fit on train only; SHAP background from validation
- **Artifact integrity:** SHA-256 with placeholder replacement pattern

### 2. Production-Grade API
- **Rate limiting:** Per-endpoint, API-key hashed in keys (SHA-256)
- **Authentication:** API key rotation support, dev/prod modes
- **Observability:** Structured JSON logs, Prometheus metrics, Request ID propagation
- **Model versioning:** `/model/versions`, `/model/current`, `X-Model-Version` header

### 3. Data Protection (GDPR/CCPA Aligned)
- **Data minimization:** Only 5/44 fields persisted by default
- **Pseudonymization:** Salted SHA-256 customer IDs + authorized lookup table
- **Retention policy:** Configurable 90-day cleanup with dry-run mode
- **Audit trail:** All de-pseudonymization requests logged

### 4. MLOps & Monitoring
- **Population drift:** PSI + KS test on rolling 1000-prediction window
- **Multi-worker aware:** Documented limitations, mitigation strategies
- **Webhook alerts:** HMAC-SHA256 signed drift notifications
- **Model registry:** File-based with semantic versioning, test artifact rejection

### 5. Code Quality
- **Type hints:** 100% coverage with mypy strict mode
- **Linting:** Ruff (import sorting, complexity checks)
- **Testing:** 175 tests, 85% coverage (core modules >90%)
- **Documentation:** Auto-generated Model Card, ADRs, OpenAPI examples

---

## Metrics & Results

| Metric | Value | Notes |
|--------|-------|-------|
| Test ROC-AUC | 0.8320 | Quality gate: ✅ PASSED |
| Test Recall | 0.6604 | Threshold: 0.6478 |
| Test Precision | 0.5588 | Selected on val @ recall≥0.70 |
| Decision Threshold | 0.6478 | Validation-optimized |
| API Coverage | 100% | All endpoints typed, documented |
| Test Coverage | 85% | Core modules >90% |
| Lines of Code | ~3,500 | src/ directory |

---

## Key Technical Decisions (ADRs)

1. **Model Selection:** Logistic Regression over XGBoost/RF for interpretability + competitive ROC-AUC
2. **Drift Detection:** PSI/KS population-level (not per-request) with background monitoring
3. **Data Minimization:** Field taxonomy (sensitive/safe/business-required) with configurable enable
4. **Threshold Rule:** Max precision at recall ≥ 0.70 on validation set
5. **SQLite Fallback:** Dev-friendly local development without Docker
6. **Model Versioning:** File-based semantic versioning with SHA-256 integrity

---

## Deployment Readiness

- ✅ Docker Compose for local stack (API, Dashboard, PostgreSQL, Redis)
- ✅ GitHub Actions CI (lint, type-check, test, Docker build)
- ✅ Alembic migrations for schema evolution
- ✅ Production config validation at startup
- ✅ Health/readiness endpoints for K8s probes
- ⚠️ AWS deployment documented but not executed (CloudFormation exists)

---

## Portfolio Artifacts
- **Architecture Diagram:** Mermaid in README
- **Model Card:** Auto-generated from artifact metadata
- **ADRs:** 6 architectural decision records
- **API Examples:** curl commands in README
- **Demo Script:** End-to-end prediction flow
- **Interview Talking Points:** 7 concrete stories mapped to code

---

## Lessons Learned

1. **Validation discipline pays off:** Strict train/val/test separation prevented optimistic bias
2. **Artifact integrity matters:** SHA-256 placeholder pattern enables tamper detection
3. **Monitoring must be population-level:** Per-request drift is statistically invalid
4. **Pseudonymization ≠ Anonymization:** Lookup tables require strict RBAC
5. **Versioning from day one:** File-based approach scales to model registry later
6. **Documentation as code:** Auto-generated Model Card ensures consistency with artifacts