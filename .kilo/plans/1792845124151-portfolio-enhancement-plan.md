# Portfolio Enhancement Plan: Customer Churn Prediction Platform

**Goal:** Elevate the project from "strong portfolio piece" to "exceptional showcase" while maintaining honesty about scope. Every change must serve the portfolio narrative.

---

## Guiding Principle

> **Show, don't just tell.** Each enhancement should produce a visible artifact (dashboard widget, API endpoint, doc page, CI badge) that a reviewer can interact with in 30 seconds.

---

## Stage 1: High-Impact Visual Upgrades (Weekend-Scale)

*These produce immediate "wow" factor for anyone running the project.*

### 1.1 Wire Dashboard to Real Data (Not Mocks)
- **Files:** `dashboard/pages/*.py`, `dashboard/api_client.py`
- **Change:** Replace hardcoded metrics in `1_Executive_Overview.py`, `2_Churn_Analytics.py`, etc. with live API calls
- **Showcase value:** Proves end-to-end integration; reviewer sees real predictions flowing
- **Effort:** ~2-3 hours

### 1.2 Add Prometheus `/metrics` Endpoint + Grafana Dashboard JSON
- **Files:** `src/api.py` (new endpoint), `monitoring/` (exporters), `grafana/dashboard.json`
- **Change:** Export `request_duration_seconds`, `predictions_total`, `drift_psi`, `model_version` as Prometheus metrics; commit a ready-to-import Grafana dashboard
- **Showcase value:** "Observability" bullet becomes demonstrable; runs in `docker compose up`
- **Effort:** ~3-4 hours

### 1.3 Multi-Stage Docker Build (Slim Image)
- **Files:** `Dockerfile.api`, `Dockerfile.dashboard`
- **Change:** Builder stage → runtime stage; final image <150MB; non-root user preserved
- **Showcase value:** `docker images` shows small size; CI logs show layer caching
- **Effort:** ~1 hour

---

## Stage 2: Production Credibility Signals (1-2 Evenings)

*These address the "would I deploy this" gaps without over-engineering.*

### 2.1 Redis for Distributed Rate Limiting
- **Files:** `docker-compose.yml`, `src/api.py` (lifespan init), `src/config.py`
- **Change:** Add `redis` service; configure SlowAPI `RedisStorage` when `REDIS_URL` set
- **Showcase value:** `docker compose up` now has production-grade rate limiting; config validates it
- **Effort:** ~1 hour

### 2.2 SHAP Background Data Fix
- **Files:** `src/api.py` (lifespan), `scripts/train_and_serialize.py`
- **Change:** Store a small background sample (e.g., 100 rows from validation set) in artifact metadata; use it for `LinearExplainer` instead of zeros
- **Showcase value:** SHAP base values become meaningful; explanations look correct
- **Effort:** ~30 min

### 2.3 API Key Rotation Support
- **Files:** `src/config.py`, `src/api.py` (auth dependency)
- **Change:** Accept comma-separated `API_KEYS` env var; validate any match; document rotation procedure
- **Showcase value:** Security section in README becomes substantive
- **Effort:** ~1 hour

---

## Stage 3: Portfolio Polish (Low Effort, High Signal)

*Documentation and CI artifacts that cost little but signal maturity.*

### 3.1 Dependency Scanning in CI
- **Files:** `.github/workflows/ci.yml`
- **Change:** Add `pip-audit` or `osv-scanner` step; fail on high/critical vulns; upload SARIF to GitHub Security tab
- **Showcase value:** GitHub repo shows "Security" tab with clean bill of health
- **Effort:** ~30 min

### 3.2 SBOM Generation
- **Files:** `.github/workflows/ci.yml`, `Dockerfile.api`
- **Change:** `syft` in CI to generate SPDX SBOM for image; attach as artifact
- **Showcase value:** Supply chain security awareness demonstrated
- **Effort:** ~20 min

### 3.3 Architecture Decision Records (ADRs)
- **Files:** `docs/adr/*.md` (new)
- **Change:** 4-5 short ADRs for key choices: (1) LogisticRegression over XGBoost, (2) PSI+KS for drift, (3) Data minimization fields, (4) Threshold selection rule, (5) SQLite fallback pattern
- **Showcase value:** Shows architectural thinking, not just coding
- **Effort:** ~1 hour

### 3.4 Load Test Script + CI Integration (Optional)
- **Files:** `tests/load/locustfile.py`, `.github/workflows/ci.yml`
- **Change:** Basic Locust script hitting `/predict`; run in CI for 30s; assert p95 < 200ms
- **Showcase value:** Performance baseline documented; CI badge shows "load test passing"
- **Effort:** ~1 hour

---

## Stage 4: Advanced Showcase (If Time Permits)

*Only if you want to go beyond "solid" to "exceptional."*

### 4.1 Model Artifact Integrity Verification
- **Files:** `src/model_management.py`, `scripts/train_and_serialize.py`
- **Change:** Store artifact SHA-256 in metadata; verify on load; reject tampered artifacts

### 4.2 Automated Model Card Generation
- **Files:** `scripts/generate_model_card.py`, `docs/MODEL_CARD.md`
- **Change:** Script reads artifact metadata → renders structured model card (metrics, provenance, limitations, intended use)

### 4.3 Drift Alert Webhook
- **Files:** `src/monitoring.py`, `src/config.py`
- **Change:** Configurable webhook URL (Slack/PagerDuty/HTTP) fired on drift detection; demo with RequestBin

---

## Explicitly Out of Scope

| Item | Reason |
|------|--------|
| Terraform/CDK for AWS | CloudFormation docs sufficient; infra-as-code is separate skill |
| Full TLS termination in compose | Terminates at ALB in prod; local dev doesn't need it |
| Ground-truth model monitoring | Requires label delay simulation; too complex for portfolio |
| A/B testing framework | Out of scope for single-model showcase |
| Kubernetes manifests | ECS/Fargate is the documented target |

---

## Validation Checklist (Definition of Done per Stage)

| Stage | Must Work Before Next Stage |
|-------|----------------------------|
| 1 | `docker compose up` → Dashboard shows live data; Grafana imports cleanly; `docker images` shows <150MB API image |
| 2 | `docker compose up` → Rate limiting works across workers; SHAP explanations have non-zero base values; multiple API keys work |
| 3 | CI passes with security scan; SBOM artifact uploaded; ADRs render in GitHub |
| 4 | (Optional) All above + artifact tampering rejected; model card auto-generates |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Dashboard rewrite breaks existing pages | Stage 1.1: Update one page at a time; keep old pages as `_old_*.py` until verified |
| Redis adds local dev friction | Stage 2.1: Make Redis optional; fallback to memory:// with warning log |
| Prometheus metrics expose internals | Stage 1.2: Only export counters/histograms; no PII, no raw predictions |
| CI time increases | Stage 3.1/3.2: Run security scans in parallel with tests; cache syft/pip-audit |

---

## Execution Order Recommendation

```
Weekend 1:  1.1 → 1.2 → 1.3
Weekend 2:  2.1 → 2.2 → 2.3
Weekend 3:  3.1 → 3.2 → 3.3 → (3.4 if energy)
```

Each stage is independently mergeable and demoable.

---

## Questions for You (Answer One at a Time)

**Q1:** Stage 1.1 (Dashboard real data) — Do you want me to:
- **A)** Update all 7 pages in one pass (higher risk, bigger payoff)
- **B)** Start with just `1_Executive_Overview.py` and `3_Customer_Risk_Explorer.py` (lower risk, shows pattern)

*My recommendation: **B** — prove the pattern on 2 pages, then replicate.*

---

**Q2:** Stage 1.2 (Prometheus/Grafana) — Should the Grafana dashboard be:
- **A)** Committed as JSON in repo (reviewer imports manually)
- **B)** Provisioned automatically via `grafana.ini` + datasource config in docker-compose

*My recommendation: **A** — simpler, no Grafana container dependency in compose.*

---

**Q3:** Stage 3.4 (Load test) — Is a 30-second Locust run in CI worth the ~2 min CI time increase?
- **A)** Yes, include it
- **B)** Skip; document how to run locally instead

*My recommendation: **B** — CI time matters; local load test script is sufficient for showcase.*

---

**Q4:** Any of the Stage 4 items you *do* want to pull forward?
- If yes, which one(s) and I'll slot them into Stage 2/3.