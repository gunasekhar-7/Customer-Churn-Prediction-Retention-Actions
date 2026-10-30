# Demo Script: Customer Churn Prediction Platform

## Prerequisites
```bash
# Start the stack
docker compose up --build -d

# Wait for services (check with docker compose ps)
# API: http://localhost:8000/docs
# Dashboard: http://localhost:8501
```

## Demo Flow (5 minutes)

---

### 1. Health & Model Info (30 seconds)

**Show the API is live and model loaded:**
```bash
# Public health check (no auth)
curl http://localhost:8000/health
# → {"status": "ok"}

# Readiness (model loaded?)
curl http://localhost:8000/ready
# → {"status": "ready"}

# Model info (requires API key)
curl -H "X-API-Key: dev-api-key-min-32-chars-long" \
  http://localhost:8000/model/info
# → version, threshold, feature count
```

**Talking point:** "Health/ready endpoints are unauthenticated for load balancers. Model info shows v1.0.0 with threshold 0.6478."

---

### 2. Single Prediction with Explanation (90 seconds)

**Predict churn for a high-risk customer:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-min-32-chars-long" \
  -d '{
    "customerID": "DEMO-HIGH-001",
    "gender": "Male",
    "SeniorCitizen": 0,
    "Partner": "No",
    "Dependents": "No",
    "tenure": 3,
    "PhoneService": "Yes",
    "MultipleLines": "No",
    "InternetService": "Fiber optic",
    "OnlineSecurity": "No",
    "OnlineBackup": "No",
    "DeviceProtection": "No",
    "TechSupport": "No",
    "StreamingTV": "Yes",
    "StreamingMovies": "Yes",
    "Contract": "Month-to-month",
    "PaperlessBilling": "Yes",
    "PaymentMethod": "Electronic check",
    "MonthlyCharges": 95.0,
    "TotalCharges": "285.0"
  }'
```

**Expected response:**
```json
{
  "customerID": "DEMO-HIGH-001",
  "churn_probability": 0.82,
  "churn_prediction": 1,
  "risk_segment": "High Risk",
  "model_version": "1.0.0"
}
```

**Headers to note:** `X-Model-Version: 1.0.0`, `X-Request-ID: <uuid>`

**Get SHAP explanation:**
```bash
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-min-32-chars-long" \
  -d '{...same payload...}'
```

**Show top drivers:** MonthlyCharges (+0.18), Contract_Month-to-month (+0.12), TechSupport_No (+0.09)

**Get retention recommendation:**
```bash
curl -X POST http://localhost:8000/retention-recommendation \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-min-32-chars-long" \
  -d '{...same payload...}'
```

**Show actions:** "Offer Annual Upgrade Discount" (month-to-month), "Offer $10 Monthly Loyalty Credit" (high charges driver), "Offer Free Tech Support Add-on" (fiber + no tech support)

---

### 3. Low-Risk Customer Comparison (30 seconds)

**Predict for a loyal customer:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-min-32-chars-long" \
  -d '{
    "customerID": "DEMO-LOW-001",
    "gender": "Female",
    "SeniorCitizen": 0,
    "Partner": "Yes",
    "Dependents": "Yes",
    "tenure": 48,
    "PhoneService": "Yes",
    "MultipleLines": "Yes",
    "InternetService": "DSL",
    "OnlineSecurity": "Yes",
    "OnlineBackup": "Yes",
    "DeviceProtection": "Yes",
    "TechSupport": "Yes",
    "StreamingTV": "No",
    "StreamingMovies": "No",
    "Contract": "Two year",
    "PaperlessBilling": "No",
    "PaymentMethod": "Bank transfer (automatic)",
    "MonthlyCharges": 45.0,
    "TotalCharges": "2160.0"
  }'
```

**Expected:** Low Risk (~0.15 probability), recommendation: "Maintain Relationship"

---

### 4. Batch Prediction (30 seconds)

```bash
curl -X POST http://localhost:8000/predict/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-min-32-chars-long" \
  -d '{
    "customers": [
      {"customerID": "BATCH-001", "gender": "Male", "SeniorCitizen": 0, "Partner": "No", "Dependents": "No", "tenure": 5, "PhoneService": "Yes", "MultipleLines": "No", "InternetService": "Fiber optic", "OnlineSecurity": "No", "OnlineBackup": "No", "DeviceProtection": "No", "TechSupport": "No", "StreamingTV": "Yes", "StreamingMovies": "Yes", "Contract": "Month-to-month", "PaperlessBilling": "Yes", "PaymentMethod": "Electronic check", "MonthlyCharges": 85.0, "TotalCharges": "425.0"},
      {"customerID": "BATCH-002", "gender": "Female", "SeniorCitizen": 1, "Partner": "Yes", "Dependents": "Yes", "tenure": 36, "PhoneService": "Yes", "MultipleLines": "Yes", "InternetService": "DSL", "OnlineSecurity": "Yes", "OnlineBackup": "Yes", "DeviceProtection": "Yes", "TechSupport": "Yes", "StreamingTV": "No", "StreamingMovies": "No", "Contract": "Two year", "PaperlessBilling": "No", "PaymentMethod": "Bank transfer (automatic)", "MonthlyCharges": 45.0, "TotalCharges": "1620.0"}
    ]
  }'
```

**Show:** Array of predictions with individual risk segments.

---

### 5. Model Versioning (30 seconds)

```bash
# List all versions
curl -H "X-API-Key: dev-api-key-min-32-chars-long" \
  http://localhost:8000/model/versions

# Current production model details
curl -H "X-API-Key: dev-api-key-min-32-chars-long" \
  http://localhost:8000/model/current
```

**Show:** Multiple versions if available, current marked with `is_current: true`.

---

### 6. Dashboard Walkthrough (60 seconds)

Open `http://localhost:8501` in browser.

**Tabs to show:**
1. **Overview** — Total customers, risk distribution pie chart, revenue at risk
2. **Predictions Table** — Recent predictions with risk segments
3. **Drift Monitoring** — PSI gauge, historical drift chart
4. **Model Metrics** — ROC-AUC, precision/recall, confusion matrix

**Point out:** Data minimization in action — only tenure, contract, monthly charges, tech support shown in raw features.

---

### 7. Security & Data Protection Demo (30 seconds)

**Rate limiting headers:**
```bash
curl -i -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-min-32-chars-long" \
  -d '{...minimal payload...}'
```
**Show headers:** `X-RateLimit-Limit: 60`, `X-RateLimit-Remaining: 59`

**Pseudonymization check (query DB):**
```bash
# In docker container
docker exec -it churn_db psql -U postgres -d churn_db -c "
  SELECT customer_id, customer_id_hash, created_at 
  FROM prediction_records 
  ORDER BY created_at DESC LIMIT 5;
"
```
**Show:** `customer_id_hash` is 64-char SHA-256, not the real ID.

**Lookup table (authorized only):**
```bash
docker exec -it churn_db psql -U postgres -d churn_db -c "
  SELECT customer_id_hash, customer_id, access_count 
  FROM customer_pseudonym_lookup 
  LIMIT 5;
"
```

---

### 8. Monitoring & Metrics (30 seconds)

**Prometheus metrics:**
```bash
curl http://localhost:8000/metrics | grep -E "(predictions_total|drift_psi|model_version)"
```

**Model metrics:**
```bash
curl -H "X-API-Key: dev-api-key-min-32-chars-long" \
  http://localhost:8000/model/metrics
```
**Show:** Test ROC-AUC 0.8320, threshold selection metadata, data provenance.

---

## Troubleshooting Quick Fixes

| Issue | Fix |
|-------|-----|
| API returns 401 | Check `X-API-Key` header matches `.env` value |
| Model not loaded | Check `docker compose logs api` for startup errors |
| DB connection failed | Ensure PostgreSQL container is healthy (`docker compose ps`) |
| Dashboard blank | Check `docker compose logs dashboard` for API connection errors |

---

## Key Talking Points During Demo

1. **"Notice the `X-Request-ID` header — it flows through logs, metrics, and DB for full traceability."**
2. **"The SHAP explanation uses LinearExplainer with validation-set background — no test data leakage."**
3. **"Customer ID is stored as salted SHA-256 hash. The lookup table requires authorized access with audit logging."**
4. **"Rate limit keys use hashed API keys — we never log the raw key even partially."**
5. **"Model versioning is file-based with semantic ordering. Test artifacts (`*-test`) are excluded from production."**
6. **"Data minimization is on by default — only 5 of 44 fields persisted. Business fields opt-in."**
7. **"Drift detection runs every 5 minutes on a rolling 1000-prediction window using PSI + KS test."**