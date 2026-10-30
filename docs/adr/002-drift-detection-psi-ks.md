# ADR 002: Drift Detection — PSI + KS Test

**Status**: Accepted
**Date**: 2026-10-24

## Context

Production ML systems require monitoring for distribution shift (drift) between training data and live predictions. We need a method that:
- Runs in background (not per-request)
- Detects both gradual and sudden drift
- Works with only prediction scores (no ground truth labels in real-time)
- Provides actionable thresholds

## Decision

We use a **dual-metric approach**: Population Stability Index (PSI) + Kolmogorov-Smirnov (KS) two-sample test.

### Population Stability Index (PSI)

PSI measures the shift between two probability distributions by binning and comparing proportions:

```
PSI = Σ (actual% - expected%) × ln(actual% / expected%)
```

Thresholds:
- PSI < 0.05: No significant drift (green)
- 0.05 ≤ PSI < 0.10: Warning — investigate (yellow)
- PSI ≥ 0.10: Drift detected — alert (red)

### Kolmogorov-Smirnov (KS) Test

KS test compares cumulative distributions:

```
D = sup|F₁(x) - F₂(x)|
```

Null hypothesis: both samples drawn from same distribution.
Threshold: p-value < 0.05 rejects null (drift detected).

### Implementation

- **Reference distribution**: 1000 validation set predictions (stored in model artifact)
- **Window**: Rolling 1000 predictions
- **Evaluation interval**: Every 5 minutes (configurable)
- **Minimum samples**: 100 before evaluation

Both metrics must agree for alert:
- PSI > 0.10 AND KS p-value < 0.05 → drift alert
- PSI > 0.05 OR KS p-value < 0.10 → warning

## Consequences

**Positive**:
- PSI is industry standard for credit risk / churn monitoring
- KS test is non-parametric (no distribution assumptions)
- Dual metric reduces false positives
- Runs in O(n) time with small memory footprint (deque)
- Prometheus gauge export for Grafana dashboards

**Negative**:
- Requires sufficient reference data (1000 samples minimum)
- Binning choice affects PSI sensitivity
- KS test less sensitive to tail differences
- No ground-truth label monitoring (requires separate feedback loop)

## References

- `src/monitoring.py`: PopulationDriftDetector and MonitoringService
- `docs/MLOPS_AND_MONITORING.md`: Monitoring architecture
- `src/api.py`: Lifespan initialization with drift callback