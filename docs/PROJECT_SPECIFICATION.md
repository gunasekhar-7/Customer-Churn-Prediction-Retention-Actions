# Project Specification: Customer Churn Prediction & Retention Intelligence Platform

## 1. Project Objective

Build an end-to-end system that:
- Predicts customer churn probability.
- Explains why customers are at risk (Explainable AI).
- Identifies valuable customers and risk segments.
- Estimates potential revenue exposure.
- Recommends appropriate retention actions.

The purpose is to demonstrate practical, production-style machine learning engineering and data science skills. It must be a functioning software product.

## 2. Core Product Requirements

The final application must support the following complete workflow:
Customer Data → Data Validation → Exploratory Analysis → Feature Engineering → Model Training → Model Evaluation → Churn Prediction → Explainable AI → Risk Segmentation → Revenue Exposure Estimation → Retention Recommendations → REST API → Interactive Dashboard → Deployment and Monitoring.

Users must be able to:
- Analyze customer churn patterns.
- Predict churn probabilities for individual customers and batches.
- Understand important factors influencing individual predictions.
- Segment customers by churn risk and available business-value indicators.
- Estimate potential revenue exposure using transparent assumptions.
- Generate explainable, rule-based retention recommendations.
- Explore model performance and customer risk through a dashboard.
- Access predictions programmatically through a REST API.

## 3. Technology Stack

- **Language:** Python 3.11+
- **Data processing:** Pandas, NumPy
- **Machine learning:** Scikit-learn, Logistic Regression, Random Forest and XGBoost where appropriate
- **Explainable AI:** SHAP
- **API:** FastAPI, Pydantic
- **Dashboard:** Streamlit, Plotly
- **Database:** PostgreSQL, SQLAlchemy, Alembic
- **Experiment tracking:** MLflow
- **Testing:** pytest, HTTPX
- **Code quality:** Ruff, typing
- **Containerization:** Docker and Docker Compose
- **CI/CD:** GitHub Actions
- **Cloud deployment:** AWS services (ECS/Fargate, ECR, RDS, S3, CloudWatch)
- **Monitoring:** Structured logging, application metrics, data-quality checks, drift analysis

## 4. Data Strategy

- **Dataset:** IBM Telco Customer Churn dataset as the initial benchmark.
- **Constraints:**
  - Use only verified columns from the dataset. Do not assume missing behavioral features (like login frequency) are present.
  - Inspect the dataset before implementing preprocessing.
  - Keep raw data immutable. Separate raw, validated, and processed data.
  - Document dataset limitations and implications of using a public dataset.

## 5. Definition of Done

The overall project is accepted only when the following are verified:

- [ ] Data ingestion and validation work with documented inputs.
- [ ] EDA is reproducible and based on actual data.
- [ ] Feature engineering and preprocessing are leakage-aware.
- [ ] Models are compared using appropriate evaluation methods.
- [ ] The final evaluation follows a defensible held-out testing strategy.
- [ ] The chosen model and decision threshold are documented.
- [ ] Model artifacts load successfully and produce consistent predictions.
- [ ] SHAP explanations correspond to actual model predictions.
- [ ] Customer segmentation and retention rules have automated tests.
- [ ] Revenue exposure calculations and their assumptions are documented.
- [ ] FastAPI endpoints work and handle invalid inputs correctly.
- [ ] PostgreSQL persistence and migrations work where enabled.
- [ ] Streamlit displays results from the shared prediction and business logic.
- [ ] Automated tests cover important success and failure scenarios.
- [ ] Docker and CI workflows are functional.
- [ ] Monitoring and deployment procedures are documented and appropriately verified.
- [ ] The README contains genuine results and clearly stated limitations.
- [ ] The final acceptance audit reports PASS, FAIL or NOT VERIFIED for each important requirement.
