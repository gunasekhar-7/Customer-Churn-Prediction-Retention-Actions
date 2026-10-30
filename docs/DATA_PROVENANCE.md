# Data Provenance & Data-Quality Record

This document records the origin, license, integrity checksums, and quality checks for
the datasets used by the Customer Churn Prediction platform. It satisfies the
provenance requirement of the model-quality acceptance gate (Part B).

## 1. Full dataset — IBM Telco Customer Churn

| Field | Value |
| :--- | :--- |
| **Source URL** | `https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv` |
| **Origin repository** | `github.com/IBM/telco-customer-churn-on-icp4d` (IBM) |
| **License / usage terms** | Apache License 2.0 (file `LICENSE` at the repository root, verified 2026-10-16). Apache-2.0 permits reproduction and redistribution with attribution. |
| **Local path** | `data/Telco-Customer-Churn-FULL.csv` (**not tracked by Git**; see §3) |
| **Retrieved** | 2026-10-14 |

### Integrity / reproducibility

| Checksum | Value |
| :--- | :--- |
| **SHA-256** | `16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91` |
| **Git blob SHA-1** | `3de7a612d1609f25f21a455bda77948729369002` |
| **Upstream blob SHA-1** | `3de7a612d1609f25f21a455bda77948729369002` — **identical**, i.e. the local file is byte-identical to the file served by the source URL (verified with `git hash-object data/Telco-Customer-Churn-FULL.csv` against `GET .../contents/data/Telco-Customer-Churn.csv`). |

Re-verify at any time:

```bash
python -c "import hashlib; print(hashlib.sha256(open('data/Telco-Customer-Churn-FULL.csv','rb').read()).hexdigest())"
# expect: 16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91
```

Re-acquire:

```bash
python -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv', 'data/Telco-Customer-Churn-FULL.csv')"
```

### Expected schema

21 columns: `customerID, gender, SeniorCitizen, Partner, Dependents, tenure,
PhoneService, MultipleLines, InternetService, OnlineSecurity, OnlineBackup,
DeviceProtection, TechSupport, StreamingTV, StreamingMovies, Contract,
PaperlessBilling, PaymentMethod, MonthlyCharges, TotalCharges, Churn`.

Target: `Churn` with labels `Yes` / `No`. Encoded as `Yes = 1` (positive class =
customer churned), `No = 0` by `src.preprocessing.get_binary_target`.

### Actual data quality (measured 2026-10-16)

| Check | Result |
| :--- | :--- |
| Record count | **7,043 rows × 21 columns** |
| Duplicate rows | **0** |
| Duplicate `customerID` | **0** |
| Pydantic schema errors (`validate_dataframe_schema`, training schema) | **0** |
| Null values (all columns) | **0** |
| Invalid / blank `TotalCharges` | **11 rows** with whitespace-only values (known quirk of the IBM file). Handled by `TotalChargesCleaner`, which coerces them to `NaN`; the `SimpleImputer` (median, fitted on training data only) fills them at transform time. |
| Target-class distribution | `No = 5,174 (73.46%)`, `Yes = 1,869 (26.54%)` — matches the documented ~26.5% baseline churn rate. |

The file was **not** accepted on the basis of its filename: row count, duplicate
count, schema validation, missing/invalid values, target distribution, and two
independent checksums were measured before use.

## 2. Sample dataset (100 rows) — pipeline smoke tests only

| Field | Value |
| :--- | :--- |
| Local path | `data/Telco-Customer-Churn.csv` |
| Rows | 100 (`No = 68`, `Yes = 32`) |
| Nature | **Synthetic** sample: `customerID` values (`CUST-0000`…) do not exist in the IBM file, and per-row charges are generated. It is a fixture for exercising the pipeline, **not** a subset of the IBM data. |
| Permitted use | Pipeline/CI smoke testing only. Model metrics computed on it (e.g. test ROC-AUC 0.3214) are **not** production metrics and must never be presented as such. |

## 3. Repository policy for datasets

* The full IBM dataset (**~948 KB**, Apache-2.0) is kept **out of Git** (`data/*FULL*.csv`
  is gitignored). Its provenance, license, and checksums above make it
  reproducibly re-acquirable instead of committed.
* The 100-row synthetic sample (**~17 KB**) **is** tracked by Git so that the
  documented "100-row sample included in this repository" claim holds and the
  pipeline runs on a fresh clone.
* Model artifacts (`models/*.joblib`) remain gitignored; see `.gitignore`.
* The dataset was **not** synthetically expanded or substituted: all production
  metrics in `docs/MODEL_METRICS.md` derive from the verified 7,043-row IBM file.

## 4. Where provenance is recorded in the artifact

`scripts/train_and_serialize.py` writes a `data_provenance` block (source URL,
SHA-256, license, row count, target distribution) into the serialized model
artifact metadata, alongside threshold, evaluation metrics, feature schema, and
version metadata, so a production artifact carries its own data lineage.
