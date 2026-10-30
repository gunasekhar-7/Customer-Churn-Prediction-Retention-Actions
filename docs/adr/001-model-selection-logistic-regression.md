# ADR 001: Model Selection — Logistic Regression over XGBoost

**Status**: Accepted
**Date**: 2026-10-24

## Context

The churn prediction platform requires a binary classification model to predict customer churn probability. The primary candidates considered were:
- Logistic Regression (scikit-learn)
- XGBoost (gradient boosting)

Key requirements:
- Explainability is critical for retention recommendations (SHAP values needed)
- Training must be fast and reproducible
- Model artifacts must be small for container deployment
- Regulatory/audit requirements favor interpretable models

## Decision

We chose **Logistic Regression** as the primary model.

### Rationale

| Criterion | Logistic Regression | XGBoost |
|-----------|---------------------|---------|
| SHAP explainability | LinearExplainer (exact, fast) | TreeExplainer (approximate, slower) |
| Training time | <10 seconds | 30-60 seconds |
| Artifact size | ~2 MB | ~50+ MB |
| Interpretability | Coefficients directly show feature effects | Requires SHAP for interpretation |
| Performance (ROC-AUC) | ~0.82 on Telco dataset | ~0.84 on Telco dataset |
| Monotonicity guarantees | Yes (with proper constraints) | No (unless constrained) |

The marginal ROC-AUC gain from XGBoost (~0.02) does not justify:
- 10x larger model artifacts
- 5-10x slower SHAP computation
- Reduced direct interpretability

Logistic Regression with L2 regularization and balanced class weights provides sufficient performance while meeting all operational constraints.

## Consequences

**Positive**:
- Fast SHAP explanations enabling real-time retention recommendations
- Small Docker images (<150 MB target achievable)
- Direct coefficient inspection for audit/compliance
- Deterministic training with fixed random seed

**Negative**:
- May miss non-linear feature interactions captured by trees
- Requires careful feature engineering (handled by preprocessor)
- Slightly lower peak ROC-AUC

## References

- `src/training.py`: Model training pipeline
- `docs/MODEL_SELECTION_AND_SHAP.md`: Detailed comparison
- `docs/MODEL_METRICS.md`: Benchmark results