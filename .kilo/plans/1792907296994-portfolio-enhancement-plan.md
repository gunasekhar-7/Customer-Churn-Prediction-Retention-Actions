# Portfolio Enhancement Plan: Customer Churn Prediction Platform

**Goal:** Elevate an already strong ML platform to a best-in-class portfolio showcase demonstrating senior ML engineering skills.

**Context:** This project already has excellent fundamentals (85% test coverage, clean architecture, proper ML hygiene, data protection, monitoring). The enhancements below focus on *portfolio signal* — features that clearly demonstrate senior-level thinking to hiring managers.

---

## Stage 1: Critical Fixes (Week 1) — "No Red Flags"

These eliminate any doubt about production readiness.

| Task | Why It Matters for Portfolio | Files |
|------|------------------------------|-------|
| 1.1 Fix SHAP KernelExplainer fallback to use preprocessor | Prevents incorrect explanations; shows attention to ML pipeline integrity | `src/explainability.py:52` |
| 1.2 Remove plaintext `customer_id` from `PredictionRecord` — keep only hash | True pseudonymization; GDPR compliance signal | `src/models.py`, `src/api.py`, `src/data_protection.py`, new Alembic migration |
| 1.3 Fix dashboard `/explain` retry logic — POST should not auto-retry | Correct idempotency understanding; avoids duplicate predictions | `dashboard/api_client.py:26-30` |
| 1.4 Move hardcoded `DriftConfig` to `config.py` with env vars | 12-factor app compliance; shows configurability discipline | `src/config.py`, `src/api.py:270-278` |

**Validation:** All tests pass, `mypy`/`ruff` clean, manual API smoke test.

---

## Stage 2: Senior Engineering Signals (Week 2) — "Architecture Depth"

These demonstrate system design thinking beyond the model.

| Task | Portfolio Signal | Files |
|------|------------------|-------|
| 2.1 Add **A/B Testing Framework** — traffic splitting by API key suffix, per-version metrics | Production ML lifecycle; gradual rollout capability | `src/api.py` (new router), `src/model_management.py`, `src/schema.py` |
| 2.2 Implement **Async SQLAlchemy** for prediction endpoints | Throughput awareness; modern Python async patterns | `src/database.py`, `src/api.py`, `requirements.txt` |
| 2.3 Add **Feature Store abstraction** (local Parquet + interface) | Feature engineering discipline; point-in-time correctness | New `src/feature_store.py`, `src/preprocessing.py` |
| 2.4 **Model Promotion API** — `/model/promote/{version}` with validation gate | MLops maturity; deployment automation readiness | `src/api.py`, `src/model_management.py` |

**Validation:** Load test showing async throughput improvement; A/B test demo in dashboard.

---

## Stage 3: ML Engineering Excellence (Week 3) — "Model Lifecycle"

These show you think about models as living systems.

| Task | Portfolio Signal | Files |
|------|------------------|-------|
| 3.1 **Automated Retraining Trigger** — drift alert → retraining job (CLI + API) | Closed-loop ML; production operations mindset | `scripts/retrain_on_drift.py`, `src/monitoring.py` webhook |
| 3.2 **Model Card Auto-Generation** with data lineage, fairness metrics, caveats | Responsible AI; regulatory awareness | `scripts/generate_model_card.py`, `docs/MODEL_CARD.md` |
| 3.3 **Shadow Mode Deployment** — new model scores silently, metrics compared | Risk mitigation; canary deployment patterns | `src/api.py` (shadow endpoint), `dashboard/pages/Model_Performance.py` |
| 3.3 **Feature Importance Drift** — monitor SHAP distribution shifts | Deep monitoring; model degradation detection | `src/monitoring.py`, `src/explainability.py` |

**Validation:** Simulated drift triggers retraining; model card renders in dashboard.

---

## Stage 4: Portfolio Presentation (Week 4) — "Hiring Manager Ready"

Polish that makes the repo immediately impressive on GitHub.

| Task | Portfolio Signal | Files |
|------|------------------|-------|
| 4.1 **Architecture Decision Records (ADRs)** — 4 new ADRs for async DB, A/B testing, feature store, shadow mode | Documents *why*, not just *what* | `docs/adr/007-*.md` through `010-*.md` |
| 4.2 **Interactive Dashboard Demo Mode** — synthetic data, guided tour, talking points | Live demo capability; interview ready | `dashboard/pages/0_Demo.py`, `docs/DEMO_SCRIPT.md` |
| 4.3 **One-Pager Technical Summary** (PDF) — architecture, metrics, decisions, links | Resume attachment; quick scan for recruiters | `docs/PORTFOLIO_SUMMARY.pdf` |
| 4.4 **GitHub Actions: Deploy Preview** — PRs deploy to staging (Render/Fly.io) | CI/CD maturity; live portfolio link | `.github/workflows/deploy-preview.yml` |
| 4.5 **README Badges** — coverage, build, license, python version, docker pulls | Professional polish | `README.md` |

---

## Stage 5: Advanced Differentiators (Optional, Week 5+) — "Staff+ Signals"

Pick 1-2 to discuss in interviews even if not fully implemented.

| Task | Portfolio Signal | Effort |
|------|------------------|--------|
| 5.1 **Cost-Aware Threshold Optimization** — business cost matrix, profit curves | Business alignment; not just ML metrics | Medium |
| 5.2 **Counterfactual Explanations** — "what would change this prediction?" | Advanced XAI; product thinking | High |
| 5.3 **Data Quality Contracts** — Great Expectations / Pandera schemas | Data engineering rigor | Medium |
| 5.4 **Multi-Region Deployment Plan** — Aurora Global, S3 CRR, latency routing | Cloud architecture depth | High |

---

## Implementation Principles

1. **No feature without tests** — every new endpoint gets unit + integration test
2. **Document decisions** — ADR for each Stage 2+ feature
3. **Keep it runnable** — `docker compose up` must work at every stage
4. **Show, don't tell** — dashboard demos > documentation claims
5. **Portfolio-first** — if a feature doesn't make a good interview story, skip it

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Scope creep | Strict 1-week timeboxes; Stage 5 explicitly optional |
| Breaking existing tests | Run full suite after each task; fix before moving on |
| Over-engineering | Each feature must answer "what interview question does this answer?" |
| Dashboard complexity | Keep demo mode separate from production pages |

---

## Success Criteria

- [ ] All critical fixes merged, tests green
- [ ] At least 2 Stage 2 features implemented with ADRs
- [ ] Dashboard demo runs in <2 minutes with `docker compose up`
- [ ] README has live badges, architecture diagram, 3-minute quickstart
- [ ] Can answer 10+ interview questions from `docs/INTERVIEW_TALKING_POINTS.md` with code references

---

## Open Questions (Resolve Before Starting)

1. **A/B testing scope:** Full traffic splitting with persistence, or just in-memory routing for demo?
2. **Async DB:** Full async SQLAlchemy 2.0, or just `run_in_executor` for prediction endpoints?
3. **Feature store:** Local Parquet only, or also Feast integration for cloud story?
4. **Deploy preview:** Render, Fly.io, Railway, or GitHub Pages for static demo?

---

## Recommended Next Step

Start with **Stage 1** — these are pure fixes with no design ambiguity. Then schedule a 30-min sync to decide Stage 2 scope based on which interview stories you want to tell.