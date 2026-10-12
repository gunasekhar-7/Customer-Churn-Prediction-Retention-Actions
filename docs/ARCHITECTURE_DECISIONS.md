# Architecture Decision Records (ADRs)

This document tracks important technical decisions made during the development of the Customer Churn Prediction & Retention Intelligence Platform.

## ADR 1: Use FastAPI for the Backend API
*   **Status:** Accepted
*   **Context:** The platform requires a performant, type-safe REST API to serve model predictions and business logic to a frontend dashboard and external clients.
*   **Decision:** We will use FastAPI.
*   **Consequences:**
    *   Benefits from asynchronous support and high performance.
    *   Automatic validation using Pydantic schemas.
    *   Automatic generation of OpenAPI documentation.

## ADR 2: Use Streamlit for the Dashboard
*   **Status:** Accepted
*   **Context:** A rapid, data-focused frontend is needed for executives and analysts to explore churn patterns, model explanations, and retention recommendations. Building a custom React/Vue app would add unnecessary overhead for a data product portfolio project.
*   **Decision:** We will use Streamlit.
*   **Consequences:**
    *   Fast development cycle entirely in Python.
    *   Easy integration with Pandas and Plotly.
    *   The Streamlit app will act strictly as a presentation layer, making HTTP requests to the FastAPI backend where all business and ML logic resides.

## ADR 3: Use Scikit-learn Pipelines for Preprocessing
*   **Status:** Accepted
*   **Context:** To prevent data leakage and ensure consistency between training and inference, data transformations must be applied identically.
*   **Decision:** We will encapsulate all data preprocessing steps (imputation, scaling, encoding) within Scikit-learn `Pipeline` and `ColumnTransformer` objects.
*   **Consequences:**
    *   The entire pipeline (preprocessing + estimator) can be serialized as a single artifact.
    *   Reduces the risk of drift or transformation errors during inference.

## ADR 4: Use PostgreSQL with SQLAlchemy for Persistence
*   **Status:** Accepted
*   **Context:** We need to store prediction records, retention recommendations, and model metadata for auditing and monitoring purposes.
*   **Decision:** We will use PostgreSQL as the relational database, accessed via SQLAlchemy ORM, with Alembic for database migrations.
*   **Consequences:**
    *   Provides robust, ACID-compliant storage.
    *   Allows schema evolution through Alembic.
    *   Requires managing a database instance (via Docker Compose locally, and AWS RDS in production).

## ADR 5: Separate Data Science Logic from API Logic
*   **Status:** Accepted
*   **Context:** Mixing model training code with API serving code leads to bloated dependencies and unmaintainable services.
*   **Decision:** The repository will clearly separate offline tasks (EDA, model training, artifact generation) from online tasks (FastAPI serving). The API will only load serialized model artifacts.
*   **Consequences:**
    *   Cleaner separation of concerns.
    *   The API container can be kept lightweight (e.g., omitting Jupyter, EDA plotting libraries).
