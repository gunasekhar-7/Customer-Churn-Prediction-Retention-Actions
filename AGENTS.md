# Customer Churn Prediction & Retention Intelligence Platform - Agent Instructions

## Scope
This project is an end-to-end customer churn prediction and retention intelligence platform. It includes data engineering, EDA, feature engineering, machine learning, explainable AI, business intelligence, a REST API (FastAPI), a dashboard (Streamlit), and deployment infrastructure.

## Engineering Standards

When working on this repository, you must adhere to the following rules:

1. **Inspect Before Modifying**: Always inspect existing files and understand the current state before modifying or creating replacements.
2. **Follow Architecture**: Adhere to this `AGENTS.md` and the documented architecture in `docs/ARCHITECTURE.md` and `docs/PROJECT_SPECIFICATION.md`.
3. **Small, Reviewable Changes**: Make small, incremental, and reviewable changes. Do not attempt to rewrite the entire application at once.
4. **Separation of Concerns**: Separate data science notebooks from reusable production logic. Production code should be in `src/`.
5. **Code Quality**:
   - Use Python 3.11+.
   - Use type hints everywhere (`typing`).
   - Write meaningful docstrings (e.g., Google or NumPy style).
   - Use structured errors.
   - Lint and type-check with `ruff` and `mypy` (or as configured).
6. **Configuration Management**: Keep configuration outside of business logic. Use environment variables and configuration files.
7. **ML Principles**:
   - Prevent data leakage. Ensure training and inference use identical transformations.
   - Maintain a proper training, validation, and held-out test strategy. Do not tune thresholds or select models using the final test set.
8. **Testing**:
   - Write unit, integration, API, database, model-inference, and end-to-end tests using `pytest`.
   - Test meaningful feature and failure paths (e.g., invalid schemas, missing values, malformed requests).
   - Do not weaken assertions or use excessive mocking just to get tests to pass.
9. **Security & Deployment**:
   - Never hardcode secrets, machine-specific paths, or production credentials.
   - Keep CI separate from cloud deployment and protect credentials.
10. **Honesty & Integrity**:
    - Never fabricate datasets, evaluation metrics, performance improvements, or deployment results. Base all conclusions on actual results.
    - Do not declare the system production-ready while critical failures remain unresolved.
    - Report actual commands executed and their genuine outcomes.
11. **Refactoring**: Preserve working functionality and avoid unrelated refactoring.
12. **Documentation**: Document technical decisions (ADRs) and assumptions.

## Tech Stack
- **Language**: Python 3.11+
- **Data/ML**: Pandas, NumPy, Scikit-learn (Logistic Regression, Random Forest, XGBoost), SHAP, MLflow
- **API**: FastAPI, Pydantic
- **Dashboard**: Streamlit, Plotly
- **Database**: PostgreSQL, SQLAlchemy, Alembic
- **Testing/Quality**: pytest, HTTPX, Ruff
- **Infra/CI**: Docker, Docker Compose, GitHub Actions, AWS (ECS/Fargate, ECR, RDS, S3, CloudWatch)

## Workflow
Follow the milestones defined in `docs/IMPLEMENTATION_ROADMAP.md`. Verify functionality at every step. Ensure the definition of done is met for each task.
