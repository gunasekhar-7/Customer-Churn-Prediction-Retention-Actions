# Portfolio Enhancement Plan: Customer Churn Prediction Platform

**Goal**: Elevate codebase from "strong portfolio project" to "exceptional portfolio showcase" in 1-2 weeks, demonstrating senior ML engineering skills across ML ops, production operations, and full-stack product.

**Constraints**: 1-2 weeks, codebase-only (no AWS deployment), balanced showcase.

---

## Phase 1: Critical Fixes & Credibility (Days 1-3)

*Must complete — these affect whether reviewers trust the project's quality.*

| # | Task | File(s) | Portfolio Signal |
|---|------|---------|------------------|
| 1.1 | Fix fragile XGBoost detection in SHAP explainer | `src/explainability.py:40` | Attention to library versioning, type-safe code |
| 1.2 | Add webhook secret validator (require secret if URL set) | `src/config.py:183-191` | Security mindset, defensive config |
| 1.3 | Regenerate MODEL_CARD from production artifact (v1.0.0, ROC-AUC 0.8320) | `scripts/generate_model_card.py` → `docs/MODEL_CARD.md` | Honest reporting, artifact-driven docs |
| 1.4 | Document multi-worker drift limitation in MLOPS_AND_MONITORING.md | `docs/MLOPS_AND_MONITORING.md` | Transparency about architecture tradeoffs |
| 1.5 | Add comment clarifying no leakage: SHAP background from val, preprocessor fit on train | `scripts/train_and_serialize.py:311` | ML hygiene awareness |
| 1.6 | Hash API key prefix in rate limit key (sha256[:8]) | `src/api.py:178` | Privacy-aware logging |
| 1.7 | Add "OVERRIDE IN PRODUCTION" comment to docker-compose DB password | `docker-compose.yml:22` | Dev vs prod discipline |

**Validation**: All tests pass, MODEL_CARD matches MODEL_METRICS, no security warnings.

---

## Phase 2: Engineering Depth Showcase (Days 3-7)

*Features that demonstrate senior-level design — pick 3-4 based on time.*

| # | Task | File(s) | Portfolio Signal |
|---|------|---------|------------------|
| 2.1 | **Model Versioning API** — Add `/model/versions`, `/model/current`, version header on `/predict` | `src/api.py`, `src/schema.py`, `src/model_management.py` | ML lifecycle management, API design |
| 2.2 | **A/B Testing Framework** — Traffic splitting by API key suffix, per-version metrics | `src/api.py`, `src/monitoring.py` | Experimentation culture |
| 2.3 | **Customer ID Pseudonymization** — Salted SHA-256 in DB, lookup table for authorized access | `src/data_protection.py`, `src/models.py`, `src/database.py` | GDPR/privacy engineering |
| 2.4 | **Async DB Operations** — Migrate to SQLAlchemy 2.0 async for higher throughput demo | `src/database.py`, `src/api.py` (async endpoints) | Modern Python, performance awareness |
| 2.5 | **Request ID Propagation** — Middleware adds `X-Request-ID`, flows through logs, metrics, DB | `src/api.py`, `src/monitoring.py` | Observability, distributed tracing |
| 2.6 | **Feature Store Light** — Persist transformed features to DB for drift analysis, lineage | `src/preprocessing.py`, `src/database.py`, `src/models.py` | Data engineering, reproducibility |
| 2.7 | **Retraining Trigger API** — `/admin/retrain` endpoint that validates drift, kicks off training job | `src/api.py`, `scripts/train_and_serialize.py` | MLOps automation |

**Recommendation for 1-2 weeks**: Do **2.1, 2.3, 2.5** (high visibility, moderate effort) + one of {2.2, 2.4, 2.6}.

---

## Phase 3: Polish & Presentation (Days 7-10)

*Makes the repo look professionally maintained.*

| # | Task | File(s) | Portfolio Signal |
|---|------|---------|------------------|
| 3.1 | Remove deprecated `check_drift_thresholds` (or add `@deprecated` with removal date) | `src/monitoring.py:405-423` | Code hygiene |
| 3.2 | Extract magic numbers to constants with docstrings (e.g., `MAX_TOP_DRIVERS = 3`) | `src/retention_intelligence.py:59`, others | Clean code habits |
| 3.3 | Add OpenAPI tags, descriptions, examples to all endpoints | `src/api.py` | API product thinking |
| 3.4 | Update README with: architecture diagram, quickstart, API examples, limitations section | `README.md` | Communication skills |
| 3.5 | Add ADR for model versioning decision (if 2.1 done) | `docs/adr/003-model-versioning.md` | Architectural decision records |
| 3.6 | Ensure 97%+ coverage maintained after changes | `pytest --cov=src` | Quality discipline |

---

## Phase 4: Portfolio Artifacts (Day 10-14)

*Create materials that make the project interview-ready.*

| # | Task | Output |
|---|------|--------|
| 4.1 | **Architecture Diagram** (Mermaid in README) showing data flow, components, deployment target | `README.md` |
| 4.2 | **One-pager Technical Summary** — problem, approach, metrics, tech stack, lessons learned | `docs/PORTFOLIO_SUMMARY.md` |
| 4.3 | **Interview Talking Points** — 5-7 concrete stories mapped to code locations | `docs/INTERVIEW_TALKING_POINTS.md` |
| 4.4 | **Demo Script** — curl commands + dashboard walkthrough for live demo | `docs/DEMO_SCRIPT.md` |
| 4.5 | **Decision Log** — why Logistic Regression, why 0.7 recall, why PSI/KS, etc. | `docs/DECISION_LOG.md` |

---

## Dependency Graph

```
Phase 1 (Critical) ──────► Phase 2 (Depth) ──────► Phase 3 (Polish) ──────► Phase 4 (Artifacts)
    │                         │                        │                        │
    ├─ 1.1, 1.2, 1.3         ├─ 2.1 needs 1.3         ├─ 3.5 needs 2.1         ├─ 4.1 needs all
    ├─ 1.4, 1.5              ├─ 2.3 standalone        ├─ 3.1 standalone        ├─ 4.2 needs 1.3, 1.4
    ├─ 1.6, 1.7              ├─ 2.5 standalone        ├─ 3.2, 3.3 standalone   ├─ 4.3 needs all
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Scope creep in Phase 2 | Time-box each task to 4hrs max; cut if not done |
| Test breakage | Run `pytest -x` after each task; fix immediately |
| Inconsistent docs | Update MODEL_CARD, MODEL_METRICS, README together in 1.3 |
| Over-engineering | Skip 2.2, 2.4, 2.6, 2.7 if time < 10 days |

---

## Success Criteria

- [ ] All Phase 1 tasks complete and tested
- [ ] 3 Phase 2 features implemented with tests
- [ ] MODEL_CARD, MODEL_METRICS, README consistent
- [ ] Coverage ≥ 95%
- [ ] Portfolio artifacts (4.1-4.5) created
- [ ] Can run `docker-compose up` and demo end-to-end in < 5 min

---

## Out of Scope (Explicit)

- Actual AWS deployment (CloudFormation exists as documentation)
- Real-time streaming inference (Kafka/Flink)
- Advanced feature store (Feast)
- Model registry UI
- Load testing beyond existing Locust script

---

## Next Step

If this plan aligns with your goals, I'll create detailed task breakdowns for Phase 1-2 (the implementation work). Phase 3-4 can be done in parallel or after.