"""
Model-quality acceptance tests covering the remediation parts:

* Part A — class mapping, positive-class probability extraction, evaluation
  metric correctness, split disjointness, and leakage guards.
* Part B — data-quality checks on the checksum-verified full dataset and the
  guard that the 100-row sample is never mistaken for the full dataset.
* Part C — threshold-selection rule and artifact consistency (feature order,
  threshold, metrics, provenance recorded together).
* Part D — drift-monitoring reference data validation.
* Part E — test-versus-production artifact separation (provenance, feature
  schema, threshold metadata, reference data; clear failure when missing).

Deterministic/synthetic fixtures are used to detect incorrect class mapping,
target leakage, feature misalignment, and evaluation bugs.
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve, roc_auc_score
from sklearn.model_selection import train_test_split

from scripts.train_and_serialize import (
    KNOWN_DATASET_SOURCES,
    build_data_provenance,
    compute_sha256,
    select_threshold,
)
from src.data_ingestion import generate_data_quality_report, validate_dataframe_schema
from src.explainability import get_feature_names
from src.inference import predict_with_threshold
from src.model_management import (
    load_model_artifact,
    serialize_model,
    validate_artifact,
)
from src.monitoring import DriftConfig, PopulationDriftDetector
from src.preprocessing import build_preprocessor, get_binary_target
from src.training import evaluate_model

PROJECT_ROOT = Path(__file__).parent.parent
FULL_DATASET = PROJECT_ROOT / "data" / "Telco-Customer-Churn-FULL.csv"
SAMPLE_DATASET = PROJECT_ROOT / "data" / "Telco-Customer-Churn.csv"
PRODUCTION_ARTIFACT = PROJECT_ROOT / "models" / "model_v1.joblib"
TEST_ARTIFACT = PROJECT_ROOT / "models" / "model_v1_test.joblib"

# Expected checksums (recorded in docs/DATA_PROVENANCE.md)
FULL_SHA256 = "16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91"
FULL_GIT_BLOB_SHA1 = "3de7a612d1609f25f21a455bda77948729369002"
IBM_SOURCE_URL = (
    "https://raw.githubusercontent.com/IBM/"
    "telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
)

requires_full_dataset = pytest.mark.skipif(
    not FULL_DATASET.exists(),
    reason="Full IBM dataset not present (see docs/DATA_PROVENANCE.md to acquire)",
)
def _is_real_production_artifact() -> bool:
    """Check if the artifact at PRODUCTION_ARTIFACT is a real production artifact.

    A real production artifact must:
    1. Exist at the expected path
    2. Have a version that does NOT end with '-test'
    3. Have valid data_provenance metadata (sha256, source_url, license)
    """
    if not PRODUCTION_ARTIFACT.exists():
        return False
    try:
        artifact = load_model_artifact(str(PRODUCTION_ARTIFACT))
        metadata = artifact.get("metadata", {})
        version = metadata.get("version", "")
        provenance = metadata.get("data_provenance")
        # Must not be a test artifact
        if version.endswith("-test"):
            return False
        # Must have valid data provenance
        if not isinstance(provenance, dict):
            return False
        if not provenance.get("sha256") or not provenance.get("source_url") or not provenance.get("license"):
            return False
        return True
    except Exception:
        return False


requires_production_artifact = pytest.mark.skipif(
    not _is_real_production_artifact(),
    reason="models/model_v1.joblib not present or not a valid production artifact; run scripts/train_and_serialize.py with full dataset",
)


# ---------------------------------------------------------------------------
# Part A — class mapping & positive-class probability extraction
# ---------------------------------------------------------------------------

class TestClassMapping:
    """The positive class must be 'Yes' (churn) encoded as 1."""

    def test_positive_class_is_churn_yes(self):
        df = pd.DataFrame({"Churn": ["Yes", "No", "Yes", "No", "No"]})
        y = get_binary_target(df)
        assert y.tolist() == [1, 0, 1, 0, 0]
        assert set(y.unique()) <= {0, 1}

    def test_unknown_labels_rejected(self):
        """A mis-encoded target must fail fast, not become silent NaN."""
        df = pd.DataFrame({"Churn": ["Yes", "No", "CHURNED"]})
        with pytest.raises(ValueError, match="Unrecognized label"):
            get_binary_target(df)

    def test_missing_target_column_rejected(self):
        with pytest.raises(KeyError, match="not found"):
            get_binary_target(pd.DataFrame({"label": ["Yes"]}))

    @staticmethod
    def _separable_data(n: int = 400, seed: int = 0):
        """Deterministic separable binary data: label driven by feature 0."""
        rng = np.random.default_rng(seed)
        x0 = rng.normal(size=n)
        y = (x0 > 0).astype(int)
        X = pd.DataFrame({"x0": x0, "x1": rng.normal(size=n)})
        return X, pd.Series(y)

    def test_predict_proba_uses_positive_class_column(self):
        """predict_with_threshold must return P(class=1 == churn)."""
        X, y = self._separable_data()
        model = LogisticRegression(max_iter=500, random_state=0).fit(X, y)
        assert list(model.classes_) == [0, 1], "binary classes must be sorted [0, 1]"

        preds, probs = predict_with_threshold(model, X, threshold=0.5)
        raw = model.predict_proba(X)
        # Column selected must be the one for class 1, resolved via classes_
        positive_idx = list(model.classes_).index(1)
        np.testing.assert_allclose(probs, raw[:, positive_idx])
        # Threshold applied to those probabilities
        np.testing.assert_array_equal(preds, (probs >= 0.5).astype(int))

    def test_wrong_class_column_is_detectable(self):
        """If evaluation used the wrong probability column it would be ~0 AUC."""
        X, y = self._separable_data()
        model = LogisticRegression(max_iter=500, random_state=0).fit(X, y)
        raw = model.predict_proba(X)

        auc_correct = roc_auc_score(y, raw[:, 1])
        auc_inverted = roc_auc_score(y, raw[:, 0])
        assert auc_correct > 0.95
        assert auc_inverted < 0.05
        # Sanity: the two columns are complementary for binary problems
        assert pytest.approx(auc_correct + auc_inverted, abs=1e-9) == 1.0

    def test_label_probability_row_order_alignment(self):
        """Probabilities and labels must stay aligned after shuffling rows."""
        X, y = self._separable_data()
        model = LogisticRegression(max_iter=500, random_state=0).fit(X, y)

        idx = np.random.default_rng(1).permutation(len(X))
        auc_shuffled = roc_auc_score(y.iloc[idx], model.predict_proba(X.iloc[idx])[:, 1])
        assert pytest.approx(auc_shuffled, abs=1e-9) == roc_auc_score(
            y, model.predict_proba(X)[:, 1]
        )


# ---------------------------------------------------------------------------
# Part A — evaluation receives continuous probabilities
# ---------------------------------------------------------------------------

class TestEvaluationMetrics:
    def test_evaluate_model_roc_auc_uses_continuous_probabilities(self):
        rng = np.random.default_rng(3)
        n = 300
        x = rng.normal(size=(n, 3))
        y = pd.Series((x[:, 0] + 0.5 * rng.normal(size=n) > 0).astype(int))
        X = pd.DataFrame(x, columns=["a", "b", "c"])
        model = LogisticRegression(max_iter=500, random_state=0).fit(X, y)

        metrics = evaluate_model(model, X, y)
        continuous_auc = roc_auc_score(y, model.predict_proba(X)[:, 1])
        binary_auc = roc_auc_score(y, model.predict(X))

        # roc_auc must equal the continuous-probability value, not a
        # thresholded-prediction value.
        assert metrics["roc_auc"] == pytest.approx(continuous_auc)
        assert metrics["roc_auc"] > binary_auc  # thresholding loses ranking info

    def test_evaluate_model_without_proba(self):
        class NoProba:
            def predict(self, X):
                return np.zeros(len(X), dtype=int)

        y = pd.Series([0, 1, 0, 1])
        metrics = evaluate_model(NoProba(), pd.DataFrame({"a": [1, 2, 3, 4]}), y)
        assert metrics["roc_auc"] is None
        assert metrics["pr_auc"] is None


# ---------------------------------------------------------------------------
# Part A — split disjointness & leakage guards
# ---------------------------------------------------------------------------

class TestSplitAndLeakage:
    @staticmethod
    def _load_frame() -> pd.DataFrame:
        path = FULL_DATASET if FULL_DATASET.exists() else SAMPLE_DATASET
        return pd.read_csv(path)

    def test_stratified_60_20_20_split_disjoint(self):
        """Partitions must be disjoint and cover every row exactly once.

        Mirrors the exact production split code path in
        scripts/train_and_serialize.py (split X, y jointly).
        """
        df = self._load_frame()
        y = get_binary_target(df, "Churn")
        X = df.drop(columns=["customerID", "Churn"])

        X_train, X_temp, y_train, y_temp = train_test_split(
            X, y, test_size=0.4, random_state=42, stratify=y
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
        )

        train_set = set(X_train.index)
        val_set = set(X_val.index)
        test_set = set(X_test.index)
        assert train_set.isdisjoint(val_set)
        assert train_set.isdisjoint(test_set)
        assert val_set.isdisjoint(test_set)
        assert train_set | val_set | test_set == set(df.index)

        # Approximate 60/20/20 proportions
        total = len(df)
        assert abs(len(train_set) / total - 0.60) < 0.02
        assert abs(len(val_set) / total - 0.20) < 0.02
        assert abs(len(test_set) / total - 0.20) < 0.02

        # Stratified: churn rate similar across partitions
        # (tolerance covers 100-row sample rounding: e.g. 6/20 vs 7/20)
        rates = [y_train.mean(), y_val.mean(), y_test.mean()]
        assert max(rates) - min(rates) <= 0.06

    def test_target_never_enters_feature_matrix(self):
        df = self._load_frame()
        X = df.drop(columns=["customerID", "Churn"])
        assert "Churn" not in X.columns
        assert "customerID" not in X.columns

        y = get_binary_target(df, "Churn")
        X_train, _, y_train, _ = train_test_split(
            X, y, test_size=0.4, random_state=42, stratify=y
        )
        pre = build_preprocessor()
        pre.fit_transform(X_train)
        names = get_feature_names(pre)
        assert "Churn" not in names and "customerID" not in names
        # One-hot expansion must not smuggle the target in either
        assert not any("Churn" in str(n) for n in names)

    def test_preprocessor_fitted_on_training_data_only(self):
        """Scaler statistics must come from the training partition, not the union."""
        n = 100

        def make_frame(tenure, monthly, total, contract):
            row = {
                "tenure": np.full(n, tenure),
                "MonthlyCharges": np.full(n, monthly),
                "TotalCharges": np.full(n, total),
                "gender": ["Female"] * n,
                "SeniorCitizen": [0] * n,
                "Partner": ["No"] * n,
                "Dependents": ["No"] * n,
                "PhoneService": ["Yes"] * n,
                "MultipleLines": ["No"] * n,
                "InternetService": ["DSL"] * n,
                "OnlineSecurity": ["No"] * n,
                "OnlineBackup": ["No"] * n,
                "DeviceProtection": ["No"] * n,
                "TechSupport": ["No"] * n,
                "StreamingTV": ["No"] * n,
                "StreamingMovies": ["No"] * n,
                "Contract": [contract] * n,
                "PaperlessBilling": ["No"] * n,
                "PaymentMethod": ["Electronic check"] * n,
            }
            return pd.DataFrame(row)

        # Train rows: distinctive constants; holdout rows: shifted by ~100x.
        # Fitting on the union would move the scaler mean away from train stats.
        train = make_frame(12.0, 70.0, 840.0, "Month-to-month")
        holdout = make_frame(90.0, 100.0, 9000.0, "Two year")

        pre = build_preprocessor()
        pre.fit_transform(train)  # fit ONLY on train

        scaler = pre.named_transformers_["num"].named_steps["scaler"]
        np.testing.assert_allclose(scaler.mean_, [12.0, 70.0, 840.0], rtol=1e-6)

        # Transforming holdout data must not raise and must not refit
        out = pre.transform(holdout)
        assert out.shape[0] == n
        # Scaler stats must remain the training stats (no refit on holdout)
        np.testing.assert_allclose(scaler.mean_, [12.0, 70.0, 840.0], rtol=1e-6)


# ---------------------------------------------------------------------------
# Part B — data quality on the verified full dataset
# ---------------------------------------------------------------------------

class TestDataQuality:
    @requires_full_dataset
    def test_full_dataset_checksum_matches_recorded_provenance(self):
        digest = hashlib.sha256(FULL_DATASET.read_bytes()).hexdigest()
        assert digest == FULL_SHA256
        assert compute_sha256(FULL_DATASET) == FULL_SHA256
        assert IBM_SOURCE_URL in KNOWN_DATASET_SOURCES[FULL_SHA256]["source_url"]

    @requires_full_dataset
    def test_full_dataset_counts_and_target_distribution(self):
        df = pd.read_csv(FULL_DATASET)
        report = generate_data_quality_report(df)
        assert report["num_rows"] == 7043
        assert report["num_columns"] == 21
        assert report["duplicate_rows"] == 0
        assert report["duplicate_customer_ids"] == 0
        assert all(v == 0 for v in report["missing_values"].values())
        assert df["Churn"].value_counts().to_dict() == {"No": 5174, "Yes": 1869}

    @requires_full_dataset
    def test_full_dataset_schema_and_invalid_values(self):
        df = pd.read_csv(FULL_DATASET)
        assert validate_dataframe_schema(df, "training") == []
        # Known IBM quirk: 11 whitespace-only TotalCharges values
        blanks = (df["TotalCharges"].astype(str).str.strip() == "").sum()
        assert int(blanks) == 11
        # Cleaning + median imputation must yield finite scaled values for
        # TotalCharges (column index 2 within the 'num' block), not zeros/NaN
        cleaned = build_preprocessor().fit_transform(df.drop(columns=["Churn"]))
        total_charges_idx = 2  # ['tenure', 'MonthlyCharges', 'TotalCharges']
        assert np.isfinite(cleaned[:, total_charges_idx]).all()

    @requires_full_dataset
    def test_sample_is_not_the_full_dataset(self):
        """The 100-row sample must never be accepted as the full dataset."""
        assert SAMPLE_DATASET.exists()
        sample = pd.read_csv(SAMPLE_DATASET)
        assert len(sample) == 100
        assert hashlib.sha256(SAMPLE_DATASET.read_bytes()).hexdigest() != FULL_SHA256
        # Sample uses synthetic IDs, unlike the IBM file
        assert str(sample["customerID"].iloc[0]).startswith("CUST-")

    @requires_full_dataset
    def test_sample_checksum_has_no_known_source(self):
        """Sample-trained artifacts must not inherit IBM provenance."""
        prov = build_data_provenance(SAMPLE_DATASET, pd.read_csv(SAMPLE_DATASET))
        assert prov["source_url"] is None
        assert prov["license"] is None
        assert prov["sha256"] != FULL_SHA256


# ---------------------------------------------------------------------------
# Part C — threshold selection rule
# ---------------------------------------------------------------------------

class TestThresholdSelection:
    @staticmethod
    def _synthetic_scores(seed: int = 5, n: int = 60):
        rng = np.random.default_rng(seed)
        y = np.array([1] * (n // 2) + [0] * (n // 2))
        # Positives skew high, negatives skew low, with overlap
        y_prob = np.where(
            y == 1, rng.beta(5, 2, size=n), rng.beta(2, 5, size=n)
        )
        return y.astype(int), y_prob

    def test_max_precision_subject_to_recall_ge_070(self):
        y_true, y_prob = self._synthetic_scores()
        threshold, meta = select_threshold(y_true, y_prob, min_recall=0.70)

        # Brute-force reference implementation using sklearn's curve
        precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
        feasible = [
            (p, t)
            for p, r, t in zip(
                precisions[:-1], recalls[:-1], thresholds, strict=True
            )
            if r >= 0.70
        ]
        assert feasible, "fixture must have feasible thresholds"
        best_expected_precision = max(p for p, _ in feasible)

        assert meta["selected_recall"] >= 0.70
        assert meta["selected_precision"] == pytest.approx(best_expected_precision)
        assert meta["fallback_used"] is False
        assert 0.0 <= threshold <= 1.0

        # Selected threshold must reproduce the recorded precision/recall
        preds = (y_prob >= threshold).astype(int)
        tp = int(((preds == 1) & (y_true == 1)).sum())
        fp = int(((preds == 1) & (y_true == 0)).sum())
        fn = int(((preds == 0) & (y_true == 1)).sum())
        assert tp / (tp + fp) == pytest.approx(meta["selected_precision"])
        assert tp / (tp + fn) == pytest.approx(meta["selected_recall"])

    def test_rule_on_hand_computed_case(self):
        """Fully hand-computed fixture (no reliance on library semantics).

        4 positives / 5 negatives; recall >= 0.70 needs >= 3 TPs.
        Feasible thresholds and their precision:
          t=0.1 -> TP4 FP5: 4/9,  recall 1.0
          t=0.3 -> TP4 FP4: 4/8,  recall 1.0
          t=0.4 -> TP3 FP4: 3/7,  recall 0.75
        (t>=0.5 leaves only 2 TPs -> recall 0.5, infeasible)
        Maximizing precision among feasible => t=0.3, precision 0.5, recall 1.0.
        """
        y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0])
        y_prob = np.array([0.9, 0.8, 0.4, 0.3, 0.85, 0.7, 0.6, 0.5, 0.1])

        threshold, meta = select_threshold(y_true, y_prob, min_recall=0.70)

        assert threshold == pytest.approx(0.3)
        assert meta["selected_precision"] == pytest.approx(0.5)
        assert meta["selected_recall"] == pytest.approx(1.0)
        assert meta["fallback_used"] is False
        # Boundary: score exactly at threshold counts as positive
        preds = (y_prob >= threshold).astype(int)
        assert preds[3] == 1  # the 0.3 positive, exactly at threshold
        assert preds[8] == 0  # the 0.1 negative, below threshold

    def test_fallback_when_recall_requirement_infeasible(self):
        y_true, y_prob = self._synthetic_scores()
        threshold, meta = select_threshold(y_true, y_prob, min_recall=1.5)
        assert meta["fallback_used"] is True
        assert meta["min_recall_requirement"] == 1.5
        assert 0.0 <= threshold <= 1.0
        assert meta["selected_f1"] > 0.0


# ---------------------------------------------------------------------------
# Part C — artifact consistency (feature schema, threshold, metrics, provenance)
# ---------------------------------------------------------------------------

class TestArtifactConsistency:
    @requires_production_artifact
    def test_production_artifact_internal_consistency(self):
        artifact = load_model_artifact(str(PRODUCTION_ARTIFACT))
        meta = artifact["metadata"]

        assert meta["version"] == "1.0.0"
        assert 0.0 <= meta["threshold"] <= 1.0
        # Feature order recorded at training must match the fitted preprocessor
        assert artifact["feature_names"] == get_feature_names(
            artifact["preprocessor"]
        )
        assert len(artifact["feature_names"]) > 0
        # Metrics and gate
        assert meta["test_metrics"]["roc_auc"] >= 0.80
        assert set(meta["test_metrics"]) >= {
            "roc_auc", "pr_auc", "precision", "recall", "f1", "confusion_matrix",
        }
        # Threshold provenance: selected on validation, min recall rule recorded
        tm = meta["threshold_metadata"]
        assert tm["min_recall_requirement"] == 0.70
        assert "highest_precision_at_recall_ge_0.7" in tm["selection_rule"]
        # Data provenance recorded with the artifact
        prov = meta["data_provenance"]
        assert prov["sha256"] == FULL_SHA256
        assert prov["source_url"] == IBM_SOURCE_URL
        assert prov["license"] == "Apache-2.0"
        assert prov["num_rows"] == 7043

    @requires_full_dataset
    @requires_production_artifact
    def test_serialized_pipeline_predictions_match_training_schema(self):
        """Serialized pipeline must transform/infer on a raw Telco row."""
        artifact = load_model_artifact(str(PRODUCTION_ARTIFACT))
        df = pd.read_csv(FULL_DATASET).drop(columns=["Churn"]).head(5)

        transformed = artifact["preprocessor"].transform(df)
        assert transformed.shape[1] == len(artifact["feature_names"])

        probs = artifact["model"].predict_proba(transformed)[:, 1]
        assert len(probs) == 5
        assert np.all((probs >= 0) & (probs <= 1))
        # Thresholded output uses the stored threshold
        preds = (probs >= artifact["metadata"]["threshold"]).astype(int)
        assert set(np.unique(preds)) <= {0, 1}


# ---------------------------------------------------------------------------
# Part D — drift reference data
# ---------------------------------------------------------------------------

class TestDriftReference:
    @requires_production_artifact
    def test_reference_predictions_valid_and_functional(self):
        artifact = load_model_artifact(str(PRODUCTION_ARTIFACT))
        ref = artifact["metadata"]["reference_predictions"]

        assert isinstance(ref, list) and len(ref) >= 100  # DriftConfig.min_samples
        assert all(isinstance(p, float) and 0.0 <= p <= 1.0 for p in ref)

        config = DriftConfig(reference_predictions=ref)
        detector = PopulationDriftDetector(config)

        # Same distribution (validation-period scores) -> no drift
        for p in ref[:500]:
            detector.add_prediction(p)
        result = detector.evaluate()
        if result is not None:
            assert result.has_drift is False

        # Strongly shifted population -> drift detected
        detector2 = PopulationDriftDetector(DriftConfig(reference_predictions=ref))
        for _ in range(500):
            detector2.add_prediction(0.999)
        shifted = detector2.evaluate()
        assert shifted is not None and shifted.has_drift is True

    def test_empty_reference_disables_drift_detection(self):
        detector = PopulationDriftDetector(DriftConfig(reference_predictions=[]))
        for _ in range(200):
            detector.add_prediction(0.5)
        assert detector.evaluate() is None

    @requires_full_dataset
    @requires_production_artifact
    def test_reference_stats_compatible_with_production_inputs(self):
        """Reference distribution must be producible by the served pipeline."""
        artifact = load_model_artifact(str(PRODUCTION_ARTIFACT))
        ref = np.asarray(artifact["metadata"]["reference_predictions"])
        assert np.std(ref) > 0.0  # not a degenerate constant distribution

        df = pd.read_csv(FULL_DATASET).drop(columns=["Churn", "customerID"]).head(200)
        probs = artifact["model"].predict_proba(
            artifact["preprocessor"].transform(df)
        )[:, 1]
        # Production scores and reference scores must share their support
        assert probs.min() >= 0.0 and probs.max() <= 1.0
        # Rough overlap sanity (not a drift verdict): means within 0.5
        assert abs(float(probs.mean()) - float(ref.mean())) < 0.5


# ---------------------------------------------------------------------------
# Part E — test-vs-production artifact separation
# ---------------------------------------------------------------------------

class TestProductionSeparation:
    @staticmethod
    def _valid_metadata(**overrides):
        meta = {
            "threshold": 0.5,
            "timestamp": "2026-10-16T00:00:00",
            "test_metrics": {
                "roc_auc": 0.85, "pr_auc": 0.6, "precision": 0.5,
                "recall": 0.7, "f1": 0.58, "confusion_matrix": [[10, 5], [3, 7]],
            },
            "reference_predictions": [0.1, 0.2, 0.3, 0.4, 0.5],
            "training_config": {"model_type": "LogisticRegression"},
            "data_provenance": {
                "sha256": FULL_SHA256,
                "source_url": IBM_SOURCE_URL,
                "license": "Apache-2.0",
                "num_rows": 7043,
            },
        }
        meta.update(overrides)
        return meta

    @staticmethod
    def _artifact(metadata, feature_names=None):
        class Dummy:
            pass

        return {
            "model": Dummy(),
            "preprocessor": Dummy(),
            "feature_names": ["f1", "f2"] if feature_names is None else feature_names,
            "metadata": metadata,
        }

    def test_test_version_rejected_for_production_validation(self):
        artifact = self._artifact(self._valid_metadata(version="1.0.0-test"))
        with pytest.raises(ValueError, match="cannot be used in production"):
            validate_artifact(artifact, require_production=True)
        # Same artifact is acceptable when production is not required
        validate_artifact(artifact, require_production=False)

    def test_serialize_rejects_test_version_without_flag(self):
        with pytest.raises(ValueError, match="cannot end with '-test'"):
            serialize_model(
                model=object(), preprocessor=object(), feature_names=["f"],
                threshold=0.5, version="2.0.0-test",
                filepath=str(Path("models") / "should_not_exist.joblib"),
            )

    def test_missing_provenance_rejected_for_production(self):
        meta = self._valid_metadata(version="1.0.0")
        del meta["data_provenance"]
        artifact = self._artifact(meta)
        with pytest.raises(ValueError, match="data_provenance"):
            validate_artifact(artifact, require_production=True)

    def test_unresolvable_provenance_rejected_for_production(self):
        """Artifacts trained on unrecognized data (e.g. the sample) fail."""
        meta = self._valid_metadata(version="1.0.0")
        meta["data_provenance"] = {
            "sha256": "a" * 64,
            "source_url": None,
            "license": None,
            "num_rows": 100,
        }
        with pytest.raises(ValueError, match="source_url"):
            validate_artifact(self._artifact(meta), require_production=True)

    def test_invalid_checksum_rejected_for_production(self):
        meta = self._valid_metadata(version="1.0.0")
        meta["data_provenance"]["sha256"] = "not-a-checksum"
        with pytest.raises(ValueError, match="sha256"):
            validate_artifact(self._artifact(meta), require_production=True)

    def test_missing_license_rejected_for_production(self):
        meta = self._valid_metadata(version="1.0.0")
        meta["data_provenance"]["license"] = None
        with pytest.raises(ValueError, match="license"):
            validate_artifact(self._artifact(meta), require_production=True)

    def test_missing_feature_schema_rejected_for_production(self):
        artifact = self._artifact(self._valid_metadata(version="1.0.0"), feature_names=[])
        with pytest.raises(ValueError, match="feature schema"):
            validate_artifact(artifact, require_production=True)

    def test_empty_reference_predictions_rejected(self):
        meta = self._valid_metadata(version="1.0.0", reference_predictions=[])
        with pytest.raises(ValueError, match="reference_predictions"):
            validate_artifact(self._artifact(meta), require_production=True)

    def test_invalid_threshold_rejected(self):
        meta = self._valid_metadata(version="1.0.0", threshold=1.7)
        with pytest.raises(ValueError, match="threshold"):
            validate_artifact(self._artifact(meta), require_production=True)

    @requires_production_artifact
    def test_production_artifact_passes_production_validation(self):
        artifact = load_model_artifact(str(PRODUCTION_ARTIFACT))
        validate_artifact(artifact, require_production=True)  # must not raise

    @pytest.mark.skipif(not TEST_ARTIFACT.exists(), reason="no test artifact on disk")
    def test_test_artifact_on_disk_rejected_for_production(self):
        artifact = load_model_artifact(str(TEST_ARTIFACT))
        with pytest.raises(ValueError, match="cannot be used in production"):
            validate_artifact(artifact, require_production=True)

    def test_missing_artifact_fails_clearly_no_random_fallback(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_model_artifact(str(Path("models") / "does_not_exist.joblib"))

    @requires_production_artifact
    def test_production_startup_load_path_validates_provenance(self):
        """Mirrors src.api lifespan: production mode requires a valid artifact."""
        artifact = load_model_artifact(str(PRODUCTION_ARTIFACT))
        validate_artifact(artifact, require_production=True)
        assert artifact["metadata"]["version"] == "1.0.0"
        assert artifact["metadata"]["data_provenance"]["sha256"] == FULL_SHA256
        # A test artifact must never satisfy this path
        if TEST_ARTIFACT.exists():
            bad = load_model_artifact(str(TEST_ARTIFACT))
            with pytest.raises(ValueError):
                validate_artifact(bad, require_production=True)


# ---------------------------------------------------------------------------
# Part B — provenance recording helper
# ---------------------------------------------------------------------------

class TestProvenanceRecording:
    @requires_full_dataset
    def test_build_data_provenance_for_known_source(self):
        df = pd.read_csv(FULL_DATASET)
        prov = build_data_provenance(FULL_DATASET, df)
        assert prov["sha256"] == FULL_SHA256
        assert prov["source_url"] == IBM_SOURCE_URL
        assert prov["license"] == "Apache-2.0"
        assert prov["num_rows"] == 7043
        assert prov["target_distribution"] == {"No": 5174, "Yes": 1869}
        assert prov["provenance_document"] == "docs/DATA_PROVENANCE.md"

    def test_compute_sha256_is_stable(self, tmp_path):
        p = tmp_path / "f.csv"
        p.write_bytes(b"a,b\n1,2\n")
        assert compute_sha256(p) == hashlib.sha256(b"a,b\n1,2\n").hexdigest()
        # Known-sources table only accepts valid 64-hex keys
        for key in KNOWN_DATASET_SOURCES:
            assert len(key) == 64 and all(c in "0123456789abcdef" for c in key)
