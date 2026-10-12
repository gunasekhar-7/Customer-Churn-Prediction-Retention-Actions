# Implementation Roadmap

This document breaks down the development of the Customer Churn Prediction & Retention Intelligence Platform into 16 milestones.

## Milestone 1: Repository and Engineering Foundation
*   **Goal:** Establish the project structure, conventions, and CI checks.
*   **Acceptance Criteria:**
    *   `AGENTS.md` and `docs/` (Architecture, Specs, Roadmap, ADRs) created.
    *   Basic Python project structure (`src/`, `tests/`) established.
    *   Dependency management (e.g., `pyproject.toml`) configured.
    *   Linting and type checking (Ruff, mypy) configured and passing.
    *   Initial CI checks (GitHub Actions placeholder or pre-commit) documented/configured.

## Milestone 2: Data Engineering
*   **Goal:** Implement robust data ingestion and validation.
*   **Acceptance Criteria:**
    *   Configurable data ingestion pipeline implemented.
    *   Schema validation, duplicate detection, and missing-value analysis implemented.
    *   Tests written for valid and invalid datasets.
    *   Data-quality reports generated.

## Milestone 3: Exploratory Data Analysis
*   **Goal:** Analyze the dataset to inform feature engineering.
*   **Acceptance Criteria:**
    *   Reproducible EDA notebook created.
    *   Reusable analysis functions extracted to `src/`.
    *   Analysis covers churn patterns, categorical distributions, class imbalance, and leakage risks based on actual data.

## Milestone 4: Feature Engineering and Preprocessing
*   **Goal:** Create robust, reusable data transformation pipelines.
*   **Acceptance Criteria:**
    *   Feature transformations implemented with Scikit-learn pipelines and `ColumnTransformer`.
    *   Handling of missing values, numerical scaling, and categorical encoding implemented.
    *   Target leakage prevented.

## Milestone 5: Machine Learning
*   **Goal:** Train and evaluate classification models.
*   **Acceptance Criteria:**
    *   Dummy baseline established.
    *   Multiple models (e.g., Logistic Regression, Random Forest, XGBoost) trained and compared.
    *   Stratified evaluation, reproducible configurations, and hyperparameter optimization implemented.
    *   Metrics reported: ROC-AUC, PR-AUC, precision, recall, F1, confusion matrices.

## Milestone 6: Model Selection and Explainability
*   **Goal:** Select the best model and implement SHAP.
*   **Acceptance Criteria:**
    *   Model selected based on documented validation criteria.
    *   Configurable operating threshold chosen based on validation results and business costs.
    *   SHAP global and customer-level explanations implemented.

## Milestone 7: Retention Intelligence
*   **Goal:** Implement business logic for retention.
*   **Acceptance Criteria:**
    *   Independently testable components for customer risk segmentation and revenue exposure estimation implemented.
    *   Rule-based retention recommendations generated.
    *   Business assumptions and thresholds documented.

## Milestone 8: Inference and Model Management
*   **Goal:** Package the model for production use.
*   **Acceptance Criteria:**
    *   Preprocessing pipeline and trained model packaged into a reusable artifact.
    *   Artifact includes feature-schema info, model version, metadata, and selected decision threshold.
    *   Predictions before and after serialization verified as equivalent.
    *   Model loading integrated for application startup.

## Milestone 9: FastAPI
*   **Goal:** Expose the model and business logic via a REST API.
*   **Acceptance Criteria:**
    *   Endpoints implemented: `/health`, `/ready`, `/model/info`, `/predict`, `/predict/batch`, `/explain`, `/retention-recommendation`.
    *   Validated request/response schemas (Pydantic).
    *   Appropriate error handling and structured logs implemented.
    *   Integration tests passing.

## Milestone 10: PostgreSQL
*   **Goal:** Implement data persistence.
*   **Acceptance Criteria:**
    *   Documented persistence model for prediction records and recommendations.
    *   SQLAlchemy models and Alembic migrations created.
    *   Database error handling implemented.

## Milestone 11: Streamlit Dashboard
*   **Goal:** Build the interactive frontend.
*   **Acceptance Criteria:**
    *   Pages created: Executive Overview, Churn Analytics, Customer Risk Explorer, Customer Explanation, Retention Recommendations, Revenue Exposure, Model Performance.
    *   Dashboard consumes the FastAPI backend.
    *   Appropriate filters and interactive charts included.

## Milestone 12: Testing and Quality Assurance
*   **Goal:** Ensure system reliability through comprehensive testing.
*   **Acceptance Criteria:**
    *   Meaningful unit, integration, API, database, model-inference, and end-to-end tests created.
    *   Coverage includes invalid schemas, missing values, artifact failures, and database errors.
    *   Test suite passes without artificially weakened assertions.

## Milestone 13: Docker and CI/CD
*   **Goal:** Containerize the application and set up continuous integration.
*   **Acceptance Criteria:**
    *   API and Dashboard containerized (Dockerfiles).
    *   `docker-compose.yml` created for local development (including PostgreSQL).
    *   GitHub Actions workflow configured for linting, testing, and Docker builds.

## Milestone 14: Monitoring and MLOps
*   **Goal:** Establish observability for the production system.
*   **Acceptance Criteria:**
    *   Monitoring configured for API metrics, data-quality violations, and prediction distributions.
    *   Retraining triggers and model promotion/rollback procedures documented.

## Milestone 15: Deployment Preparation
*   **Goal:** Prepare for cloud deployment on AWS.
*   **Acceptance Criteria:**
    *   AWS deployment architecture documented (ECS/Fargate, RDS, S3).
    *   Infrastructure as Code (or deployment scripts) implemented where appropriate.
    *   Deployment verification and rollback procedures documented.

## Milestone 16: Final Acceptance and Portfolio Preparation
*   **Goal:** Final review and documentation.
*   **Acceptance Criteria:**
    *   Repository audited and complete test suite run.
    *   Professional README produced with architecture, methodology, results, API instructions, and limitations.
    *   Final acceptance audit completed (PASS/FAIL for requirements).
