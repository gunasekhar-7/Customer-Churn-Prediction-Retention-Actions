# Architecture: Customer Churn Prediction & Retention Intelligence Platform

## Overview

The platform is designed as a modular, containerized application with a backend API (FastAPI) and a frontend dashboard (Streamlit). It leverages a machine learning model for churn prediction, coupled with business logic for retention intelligence and explainability. Data is persisted in a PostgreSQL database.

## High-Level Components

1.  **Machine Learning Pipeline (Offline)**
    *   **Data Ingestion & Validation:** Scripts to load and validate the IBM Telco dataset.
    *   **Feature Engineering:** Reusable Scikit-learn pipelines to transform raw data.
    *   **Model Training & Evaluation:** Logic to train models (Logistic Regression, Random Forest, XGBoost), track experiments with MLflow, and evaluate performance.
    *   **Artifact Generation:** Serialization of the trained model and preprocessing pipeline for use in inference.

2.  **FastAPI Backend (Online Service)**
    *   **Inference Engine:** Loads the serialized model artifact and serves predictions.
    *   **Explainability Module:** Integrates SHAP to provide global and local (customer-level) feature importances.
    *   **Retention Intelligence Module:** Applies business rules to segment customers, estimate revenue exposure, and generate actionable retention recommendations.
    *   **REST API:** Exposes endpoints for health checks, model metadata, single/batch predictions, explanations, and recommendations.
    *   **Persistence Layer:** Uses SQLAlchemy and Alembic to store prediction records and retention recommendations in PostgreSQL.

3.  **Streamlit Dashboard (Frontend)**
    *   **Executive Overview:** High-level metrics and KPIs.
    *   **Churn Analytics:** Visualizations of historical churn patterns.
    *   **Customer Risk Explorer & Explanation:** Detailed view of individual customer risk and SHAP explanations.
    *   **Retention & Revenue:** Dashboards for retention recommendations and revenue exposure analysis.
    *   **Model Performance:** Metrics and visualizations of model efficacy.
    *   *Note: The dashboard consumes the FastAPI backend, ensuring single-source-of-truth for business logic.*

4.  **Database Layer**
    *   **PostgreSQL:** Relational database for storing predictions, model versions, and application state.

## Deployment Architecture

*   **Containerization:** The API, Dashboard, and (for local development) the Database are containerized using Docker and orchestrated with Docker Compose.
*   **Target Cloud (AWS - Planned):**
    *   **Compute:** Amazon ECS (Elastic Container Service) on Fargate for serverless container execution of the API and Dashboard.
    *   **Container Registry:** Amazon ECR for storing Docker images.
    *   **Database:** Amazon RDS (Relational Database Service) for managed PostgreSQL.
    *   **Storage:** Amazon S3 for storing model artifacts and raw data.
    *   **Monitoring:** Amazon CloudWatch for structured logging, application metrics, and drift monitoring.

## Data Flow (Inference)

1.  Client (or Dashboard) sends customer data to FastAPI `POST /predict`.
2.  FastAPI validates the request schema using Pydantic.
3.  The request data is passed through the deserialized Scikit-learn preprocessing pipeline.
4.  The preprocessed data is fed into the ML model to get churn probabilities.
5.  If requested, the Explainability module generates SHAP values.
6.  The Retention Intelligence module calculates risk segments and revenue exposure.
7.  Results are formatted, optionally persisted to PostgreSQL, and returned to the client.
