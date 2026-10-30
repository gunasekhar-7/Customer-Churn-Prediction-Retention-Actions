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

## ADR 6: One NAT Gateway per Availability Zone
*   **Status:** Accepted
*   **Context:** The template originally created a single NAT Gateway in `PublicSubnetIds[0]` and one shared private route table, so both private subnets depended on one AZ for egress (audit finding: availability gap).
*   **Decision:** Create `NatGatewayA`/`NatGatewayB` with separate EIPs and separate private route tables, each private subnet egressing through the NAT in its own AZ. The S3 gateway endpoint is attached to both route tables.
*   **Consequences:**
    *   Egress survives the loss of the NAT's AZ; avoids cross-AZ NAT dependency.
    *   +≈$32.40/month (us-east-1 list, 720 h) plus $0.045/GB processed per gateway.
    *   Does **not** provide database or regional failover; still depends on correctly AZ-aligned subnet ordering supplied as parameters (statically unverifiable).

## ADR 7: Optional In-Stack RDS with Parameterised Class and Explicit Multi-AZ
*   **Status:** Accepted
*   **Context:** The template previously had no `AWS::RDS::DBInstance` at all (endpoint passed in), so no instance class or Multi-AZ setting could be declared or reviewed, and the audit could not evaluate database capacity or availability.
*   **Decision:** Add `DatabaseMode` = `external` (unchanged behaviour, endpoint + secret ARN enforced by a `Rules` section) or `create` (stack provisions PostgreSQL 15 in the private subnets). Class is a parameter (`DbInstanceClass`, default `db.r6g.large` for staging), availability is a separate parameter (`DbMultiAZ`, default `true`), with `DeletionPolicy: Snapshot`.
*   **Consequences:**
    *   Connection budget is verifiable: 2 workers × (5+10) × 10 tasks + migration/ops = 303 vs ≈1,800 default `max_connections` on `db.r6g.large` (the old `db.t4g.micro` baseline allows only ≈112).
    *   `DbMultiAZ=true` costs ≈2× instance and ≈2× storage; `false` is documented as explicitly single-AZ, not highly available.
    *   Credentials generated in-stack are still handed to tasks via CloudFormation dynamic references (see ADR 7 follow-up in `docs/AWS_DEPLOYMENT.md` §10).
