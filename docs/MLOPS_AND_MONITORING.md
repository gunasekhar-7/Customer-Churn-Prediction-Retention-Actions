# MLOps and Monitoring Procedures

This document outlines the operational guidelines for the Customer Churn Prediction platform.

## 1. Monitoring & Logging Strategy
The FastAPI backend utilizes `MetricsMiddleware` to output structured JSON logs containing:
*   `event_type`: Identifies the log (e.g., `api_request`, `drift_alert`).
*   `endpoint`: The API path executed.
*   `process_time_ms`: Processing latency.
*   `status_code`: HTTP result.

These JSON strings are printed to standard output (`stdout`), making them natively ingestible by AWS CloudWatch (via ECS) or an ELK stack.

## 2. Drift Detection
A synchronous check (`check_drift_thresholds`) runs during the `/predict` endpoint.
- If a prediction's probability deviates more than `0.5` from the historical global mean (`0.265`), it emits a structured `drift_alert` JSON warning.
- **Production Extension:** In a fully deployed state, AWS CloudWatch Alarms should be configured to trigger if `drift_alert` volume exceeds a baseline threshold over a 24-hour rolling window.

## 3. Retraining Triggers
The model should *not* be retrained automatically on a simple cron schedule. Retraining is triggered when:
1.  **Data Drift Alerting:** CloudWatch flags continuous high-volume `drift_alert` warnings.
2.  **Concept Drift (Ground Truth):** Monthly reconciliation reveals the model's aggregate ROC-AUC drops below `0.80` on actual realized churn data.
3.  **Schema Evolution:** The core Telco product changes (e.g., adding a "3-Year Contract" or a new "5G Service" category).

## 4. Model Promotion & Rollback
Models are tracked via the `model_version` metadata field embedded inside the `model_v1.joblib` artifact.
*   **Promotion:** A new model (e.g., `v1.1.0`) must pass the full `pytest` suite and display superior (or equal) ROC-AUC on a held-out test set before being serialized. The GitHub Actions CI/CD pipeline enforces this testing standard.
*   **Rollback:** If API latency degrades or prediction anomalies spike after a deployment, AWS ECS allows instant rollback to the previously active Task Definition (which pulls the prior container image tied to the stable artifact).
