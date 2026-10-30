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

### Population-Level Drift Detection (Production)
The `MonitoringService` runs a background thread per worker process that periodically evaluates population-level drift using PSI and KS test against reference distributions from the validation set. It collects prediction scores in a rolling window and evaluates drift at a configurable interval (default: 5 minutes).

**Multi-Worker Limitation:** In a multi-worker deployment (e.g., Gunicorn/Uvicorn with multiple workers, or ECS Fargate with multiple tasks), each worker runs its own independent `MonitoringService` instance with its own rolling window and background thread. This means:
- Drift detection is performed on a per-worker subset of traffic, not the aggregate
- A worker with low traffic may have insufficient samples for reliable drift detection
- Drift alerts may fire inconsistently across workers
- The Prometheus `drift_psi` gauge reflects only the evaluating worker's PSI score

**Mitigation Options:**
1. Use a single-worker deployment for the monitoring component (separate monitoring service)
2. Externalize the rolling window to Redis for shared state across workers
3. Aggregate drift metrics in a centralized monitoring system (e.g., CloudWatch, Prometheus with federation)
4. Accept the limitation and configure alerting thresholds accordingly (higher PSI threshold, longer evaluation windows)

### Legacy Per-Request Drift Check (Deprecated)
A synchronous check (`check_drift_thresholds`) runs during the `/predict` endpoint for backward compatibility.
- If a prediction's probability deviates more than `0.5` from the historical global mean (`0.265`), it emits a structured `drift_alert` JSON warning.
- **Production Extension:** In a fully deployed state, AWS CloudWatch Alarms should be configured to trigger if `drift_alert` volume exceeds a baseline threshold over a 24-hour rolling window.
- **Note:** This per-request check is statistically misleading and deprecated. Use `MonitoringService` for production drift detection.

## 3. Retraining Triggers
The model should *not* be retrained automatically on a simple cron schedule. Retraining is triggered when:
1.  **Data Drift Alerting:** CloudWatch flags continuous high-volume `drift_alert` warnings.
2.  **Concept Drift (Ground Truth):** Monthly reconciliation reveals the model's aggregate ROC-AUC drops below `0.80` on actual realized churn data.
3.  **Schema Evolution:** The core Telco product changes (e.g., adding a "3-Year Contract" or a new "5G Service" category).

## 4. Model Promotion & Rollback
Models are tracked via the `model_version` metadata field embedded inside the `model_v1.joblib` artifact.
*   **Promotion:** A new model (e.g., `v1.1.0`) must pass the full `pytest` suite and display superior (or equal) ROC-AUC on a held-out test set before being serialized. The GitHub Actions CI/CD pipeline enforces this testing standard.
*   **Rollback:** If API latency degrades or prediction anomalies spike after a deployment, AWS ECS allows instant rollback to the previously active Task Definition (which pulls the prior container image tied to the stable artifact).
