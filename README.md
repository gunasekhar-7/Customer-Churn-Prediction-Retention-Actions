# Customer Churn Prediction & Retention Intelligence Platform

An end-to-end Machine Learning product designed to predict customer churn, identify risk segments, estimate financial exposure, and automatically generate rule-based retention actions using Explainable AI (SHAP).

## 1. Project Overview
This repository contains a full production-style MLOps pipeline. It ingests data, trains models without leakage, serves predictions asynchronously via FastAPI, stores records in PostgreSQL, and surfaces insights through an interactive Streamlit dashboard.

The objective is to move beyond simple Jupyter notebooks and demonstrate practical, interview-ready software engineering and data science skills.

## 2. Architecture & Tech Stack
*   **Data Processing:** Pandas, NumPy, Scikit-learn (Pipelines, ColumnTransformer).
*   **Modeling:** Logistic Regression, Random Forest, XGBoost. (Logistic Regression was chosen as the primary model due to superior ROC-AUC).
*   **Explainable AI:** SHAP (LinearExplainer).
*   **API Layer:** FastAPI, Pydantic.
*   **Frontend Dashboard:** Streamlit, Plotly, HTTPX.
*   **Database:** PostgreSQL, SQLAlchemy ORM, Alembic.
*   **Infrastructure / CI-CD:** Docker, Docker Compose, GitHub Actions.
*   **Testing:** Pytest (97% Line Coverage), Ruff (Linting).
*   **Security:** API Key authentication, Rate Limiting (SlowAPI), Data Minimization, Configurable Retention Policy.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/AWS_DEPLOYMENT.md`](docs/AWS_DEPLOYMENT.md) for full system diagrams and cloud provisioning details.

## 3. Methodology & Results
*   **Data Strategy:** Built using the IBM Telco Customer Churn dataset. We utilized strict Pydantic schemas for data ingestion validation.
*   **Evaluation:** Evaluated across a stratified 80/20 train/test split to account for the 73/26 target imbalance.
*   **Verified Results (Logistic Regression at Baseline 0.5 Threshold):**
    *   **ROC-AUC:** 0.841
    *   **PR-AUC:** 0.632
    *   **Recall:** 0.783
    *   **Precision:** 0.503
*   **Threshold Tuning:** Because precision was low (~50%), we adjusted the active decision threshold to **0.65** inside the `model_v1.joblib` artifact. This decreases false-positive churn flags, optimizing marketing spend ROI.

## 4. Business Rules & Retention Logic
The platform translates probabilities into actionable intelligence:
*   **Risk Segmentation:** `<30%` (Low), `30-64%` (Medium), `>=65%` (High).
*   **Revenue Exposure:** `Probability * MonthlyCharges * 12 months`.
*   **Rule Engine:** If a customer is high risk *and* SHAP indicates their high Monthly Bill is driving their churn probability, the system automatically recommends an "Offer $10 Monthly Loyalty Credit" intervention. See [`docs/BUSINESS_RULES.md`](docs/BUSINESS_RULES.md) for the full mapping table.

## 5. Security & Data Protection
The platform implements several security and data protection measures:

### API Authentication
*   **API Key Authentication:** All prediction endpoints require a valid API key via the `X-API-Key` header (configurable via `API_KEY_HEADER`).
*   **Environment-based Configuration:** All secrets loaded from environment variables via Pydantic Settings. No hardcoded credentials.
*   **Production Validation:** Startup fails fast if required secrets are missing or set to insecure defaults.

### Rate Limiting
*   **Endpoint-specific Limits:** Configurable rate limits per endpoint (e.g., 60/min for `/predict`, 10/min for `/predict/batch`).
*   **Client Identification:** Uses API key for authenticated clients, falls back to IP address.
*   **Standard Headers:** Returns `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers.

### Data Minimization
*   **Configurable Minimization:** Only non-sensitive fields persisted in `raw_features` (enabled by default via `DATA_MINIMIZATION_ENABLED`).
*   **Sensitive Fields Excluded:** Direct identifiers (customerID), financial data (MonthlyCharges, TotalCharges), demographic data (gender, SeniorCitizen), and billing info (PaymentMethod, Contract) are excluded from `raw_features` when minimization is enabled.
*   **Business Fields Retained:** Fields required for retention logic (Contract, MonthlyCharges, InternetService, TechSupport) and monitoring (tenure) are retained.
*   **Metadata Tracking:** Minimization metadata stored with each record (`_minimized`, `_minimized_at`, field counts).

### Data Retention Policy
*   **Configurable Retention Period:** Default 90 days (configurable via `DATA_RETENTION_DAYS`).
*   **Automated Cleanup:** `scripts/cleanup_retention.py` deletes expired records in bounded batches.
*   **Safe Cleanup:** Dry-run mode (`DATA_RETENTION_DRY_RUN`) for verification before deletion.
*   **Statistics Reporting:** `get_retention_stats()` provides counts of expired vs active records.
*   **Cascade Deletion:** Associated retention recommendations deleted with prediction records.

### Audit & Monitoring
*   **Structured Logging:** JSON-formatted request metrics with no sensitive data.
*   **Drift Detection:** Runtime prediction drift alerts via `check_drift_thresholds()`.
*   **No Secrets in Logs:** Logging configuration excludes sensitive fields.

## 6. Quick Start (Local Setup)
Ensure you have Docker and Docker Compose installed.

```bash
# 1. Clone the repository
git clone <url>
cd churn_platform

# 2. Configure environment (copy example and edit)
cp .env.example .env
# Edit .env with your values (at minimum, generate an API_KEY for production)

# 3. Build and run the containers (API, Dashboard, PostgreSQL)
docker compose up --build

# 4. Access the interfaces
# Streamlit Dashboard: http://localhost:8501
# FastAPI Swagger Docs: http://localhost:8000/docs
```

### Local Development without Docker
```bash
# Install dependencies
pip install -e .[dev]

# Generate test model artifact
python -m scripts.create_test_artifact

# Run API server (requires .env with DATABASE_URL or uses SQLite fallback)
uvicorn src.api:app --reload

# Run dashboard
streamlit run dashboard/app.py
```

## 7. Testing Coverage
The platform maintains **97% Line Coverage** across the `src/` directory.
Run the suite locally using:
```bash
pip install -e .[dev]
pytest --cov=src
ruff check .
mypy src/
```

### Data Protection Tests
```bash
# Run data protection and retention tests specifically
pytest tests/test_data_protection.py -v
```

## 8. Data Retention Cleanup
Run the retention cleanup job manually or schedule via cron/Kubernetes CronJob:
```bash
# Dry run (logs what would be deleted)
python scripts/cleanup_retention.py --dry-run

# Actual cleanup
python scripts/cleanup_retention.py

# Show retention statistics only
python scripts/cleanup_retention.py --stats-only

# Override retention period
python scripts/cleanup_retention.py --retention-days 180
```

## 9. Limitations & Caveats
*   **Dataset Limitations:** The IBM Telco dataset lacks continuous behavioral data (e.g., login frequency, customer support tickets over time). Our retention recommendations are limited to static demographic/contract triggers.
*   **Model Persistence:** Currently, the artifact is built via script and committed to the file structure locally. In a full cloud production environment, the FastAPI app should pull the latest `joblib` artifact directly from AWS S3 upon startup to reduce container image bloat.
*   **Rate Limiting Backend:** Current implementation uses in-memory rate limiting (SlowAPI default). For multi-worker or distributed deployments, configure a shared backend (Redis) via SlowAPI's `RedisStorage`.
*   **Compliance Note:** The implemented technical controls (encryption at rest via PostgreSQL, deletion, minimization) support data protection requirements but do not constitute legal GDPR/CCPA compliance. Legal review required for production deployments handling real customer data.
*   **Data Minimization Trade-off:** Minimization reduces stored data but may limit future analysis. The `raw_features` column can be re-enabled via `DATA_MINIMIZATION_ENABLED=false` if full record retention is required.