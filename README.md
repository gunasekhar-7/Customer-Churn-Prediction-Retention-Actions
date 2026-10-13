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

## 5. Quick Start (Local Setup)
Ensure you have Docker and Docker Compose installed.

```bash
# 1. Clone the repository
git clone <url>
cd churn_platform

# 2. Build and run the containers (API, Dashboard, PostgreSQL)
docker compose up --build

# 3. Access the interfaces
# Streamlit Dashboard: http://localhost:8501
# FastAPI Swagger Docs: http://localhost:8000/docs
```

## 6. Testing Coverage
The platform maintains **97% Line Coverage** across the `src/` directory.
Run the suite locally using:
```bash
pip install -e .[dev]
pytest --cov=src
ruff check .
```

## 7. Limitations & Caveats
*   **Dataset Limitations:** The IBM Telco dataset lacks continuous behavioral data (e.g., login frequency, customer support tickets over time). Our retention recommendations are limited to static demographic/contract triggers.
*   **Model Persistence:** Currently, the artifact is built via script and committed to the file structure locally. In a full cloud production environment, the FastAPI app should pull the latest `joblib` artifact directly from AWS S3 upon startup to reduce container image bloat.
