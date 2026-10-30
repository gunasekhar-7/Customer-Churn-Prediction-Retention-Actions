# ADR 004: Threshold Selection — Highest Precision at Recall ≥ 0.70

**Status**: Accepted
**Date**: 2026-10-24

## Context

The churn prediction model outputs probabilities. Converting to binary predictions requires a decision threshold. The threshold choice directly impacts business outcomes:

- **Low threshold** → more customers flagged as high-risk → higher recall, lower precision → more retention offers sent, higher cost
- **High threshold** → fewer customers flagged → higher precision, lower recall → fewer offers, but miss at-risk customers

The business requirement: "Catch at least 70% of actual churners (recall ≥ 0.70) while minimizing false alarms."

## Decision

Select the threshold that **maximizes precision** subject to **recall ≥ 0.70** on the validation set.

### Algorithm

```python
def select_threshold(y_true, y_prob, min_recall=0.70):
    for threshold in sorted(unique(y_prob)):
        y_pred = (y_prob >= threshold).astype(int)
        recall = TP / (TP + FN)
        precision = TP / (TP + FP)
        if recall >= min_recall and precision > best_precision:
            best_threshold = threshold
    return best_threshold
```

If no threshold achieves recall ≥ 0.70, fall back to best F1 score.

### Why Not Other Methods?

| Method | Problem |
|--------|---------|
| Fixed 0.5 | Ignores class imbalance; recall typically < 0.50 |
| Youden's J (max sensitivity+specificity) | Doesn't guarantee minimum recall |
| F1 maximization | Balances P/R but may yield recall < 0.70 |
| Cost-based | Requires accurate cost matrix (often unavailable) |

### Validation

Threshold is selected on **validation set (20%)**, then evaluated on **held-out test set (20%)** as a quality gate (ROC-AUC ≥ 0.80). Test set is NEVER used for threshold tuning.

## Consequences

**Positive**:
- Guarantees minimum business coverage (70% of churners caught)
- Precision optimization reduces wasted retention spend
- Validation-only tuning prevents test set leakage
- Transparent, auditable selection rule

**Negative**:
- Precision may be modest (~0.45 on Telco dataset)
- Threshold sensitive to validation set composition
- Requires sufficient validation samples (min 100 recommended)

## References

- `scripts/train_and_serialize.py::select_threshold()`: Implementation
- `docs/MODEL_SELECTION_AND_SHAP.md`: Threshold analysis
- `docs/MODEL_METRICS.md`: Test set evaluation results