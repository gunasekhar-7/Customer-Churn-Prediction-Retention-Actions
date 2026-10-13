# AWS Deployment Architecture and Procedures

This document specifies how the Customer Churn Prediction platform maps to AWS infrastructure for production deployment.

## 1. Architecture Components
*   **Amazon ECS (Elastic Container Service) on Fargate:**
    *   Serverless compute engine for running our Docker containers (`churn-api` and `churn-dashboard`).
    *   Automatically scales based on CPU/Memory thresholds.
*   **Amazon ECR (Elastic Container Registry):**
    *   Hosts our versioned Docker images pushed from GitHub Actions.
*   **Amazon RDS (Relational Database Service):**
    *   Managed PostgreSQL database (`db.t4g.micro` for baseline) hosting `prediction_records` and `retention_recommendations`.
*   **Amazon S3 (Simple Storage Service):**
    *   Stores the compiled model artifacts (e.g., `model_v1.joblib`). The API container fetches these objects upon startup natively.
*   **Amazon CloudWatch:**
    *   Captures `stdout` JSON logs emitted by our `MetricsMiddleware`.
    *   Configured with Alarms to trigger if `drift_alert` is detected.

## 2. Infrastructure as Code (IaC)
We use AWS CloudFormation to define the ECS Cluster, Task Definitions, and Services in a reproducible manner. (See `cloudformation/ecs-cluster.yml` for the compute template).

## 3. Deployment Verification
After merging to `main` and deploying the newest ECR image:
1.  **Health Check:** Ensure `/health` returns HTTP 200 via the AWS Application Load Balancer (ALB).
2.  **Model Loading:** Query `/model/info` to verify the correct artifact version (`1.0.0`) and Threshold (`0.65`) was loaded successfully from S3 into memory.
3.  **End-to-End Test:** Submit a known `POST /retention-recommendation` payload and confirm the database writes the resultant recommendation record seamlessly.

## 4. Rollback Procedures
If post-deployment checks fail or CloudWatch alerts fire:
1.  **Revert ECS Task Definition:** In the ECS console (or via AWS CLI), update the Service to utilize the previous *stable* revision of the Task Definition.
2.  **Automated Drain:** ECS will spin up the old container version, wait for it to pass health checks, and drain network connections away from the broken deployment.
3.  **Database Consideration:** If Alembic migrations were applied, manual database rollback (`alembic downgrade -1`) must be performed before the ECS rollback completes, ensuring schema compatibility.
