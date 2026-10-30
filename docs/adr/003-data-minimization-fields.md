# ADR 003: Data Minimization — Prediction Record Fields

**Status**: Accepted
**Date**: 2026-10-24

## Context

The platform stores prediction records in PostgreSQL for:
- Historical audit trail
- Drift monitoring reference data
- Business intelligence dashboards
- Retention recommendation history

Regulatory requirements (GDPR, CCPA) and security best practices mandate minimizing stored personal data. The raw Telco dataset contains sensitive fields:
- `customerID` (PII — direct identifier)
- `gender`, `SeniorCitizen`, `Partner`, `Dependents` (demographics)
- `PhoneService`, `MultipleLines`, `InternetService` (service details)
- `PaymentMethod` (financial indicator)
- `MonthlyCharges`, `TotalCharges` (financial)

## Decision

Store only **minimized features** in prediction records:
1. `customerID` — hashed (SHA-256 with salt) for linkage without raw PII
2. `churn_probability`, `churn_prediction`, `risk_segment` — model outputs
3. `model_version` — traceability
4. `MonthlyCharges` — needed for revenue exposure calculation
5. `tenure` — needed for retention logic
6. `Contract` — needed for retention logic

All other raw features are **excluded** from persistent storage.

## Implementation

`src/data_protection.py::get_minimized_features()`:

```python
MINIMIZED_FIELDS = {
    "customerID",      # hashed at insert
    "MonthlyCharges",  # revenue exposure
    "tenure",          # retention logic
    "Contract",        # retention logic
}
```

Hashing:
```python
hashed_id = hashlib.sha256(f"{salt}{customer_id}".encode()).hexdigest()[:16]
```

Database schema (`src/models.py`):
```python
raw_features = Column(JSON, nullable=True)  # only minimized fields
```

## Consequences

**Positive**:
- GDPR/CCPA compliant by design
- Reduced storage footprint (~90% reduction in JSON size)
- Lower blast radius if database compromised
- Retention logic still functional with key business fields

**Negative**:
- Cannot reconstruct full customer profile from prediction records
- Some ad-hoc analysis requires re-joining with source data
- Hash salt must be managed securely (stored in secret manager)

## References

- `src/data_protection.py`: Minimization and hashing logic
- `src/models.py`: PredictionRecord schema
- `docs/DATA_PROVENANCE.md`: Data lineage documentation
- `docs/BUSINESS_RULES.md`: Retention logic field requirements