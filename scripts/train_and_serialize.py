#!/usr/bin/env python
"""
Train, evaluate, and serialize the churn prediction model with proper
threshold selection and validation.

This script:
1. Splits data into train/validation/test (60/20/20)
2. Trains on train set
3. Selects threshold on validation set (highest precision at recall >= 0.70)
4. Evaluates on held-out test set (quality gate: ROC-AUC >= 0.80)
5. Serializes model with threshold, metrics, and reference predictions

Usage:
    python scripts/train_and_serialize.py --data-path data/Telco-Customer-Churn.csv
    python scripts/train_and_serialize.py --data-path /path/to/data.csv --output models/model_v1.joblib
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from src.explainability import get_feature_names
from src.model_management import serialize_model
from src.preprocessing import build_preprocessor, get_binary_target

DEFAULT_DATA_PATH = Path(__file__).parent.parent / "data" / "Telco-Customer-Churn.csv"
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "models" / "model_v1.joblib"

# Known dataset sources keyed by file SHA-256. Only files whose checksum matches a
# known source are granted a resolvable provenance (source URL + license); see
# docs/DATA_PROVENANCE.md. Unknown files are recorded but flagged, and production
# artifact validation rejects artifacts without resolvable provenance.
KNOWN_DATASET_SOURCES: Dict[str, Dict[str, str]] = {
    # Full IBM Telco Customer Churn dataset (7,043 rows)
    "16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91": {
        "source_url": (
            "https://raw.githubusercontent.com/IBM/"
            "telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
        ),
        "origin_repository": "github.com/IBM/telco-customer-churn-on-icp4d",
        "license": "Apache-2.0",
        "dataset": "IBM Telco Customer Churn (full, 7043 rows)",
    },
}


def compute_sha256(path: Path) -> str:
    """Compute the SHA-256 checksum of a file (streamed, constant memory)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_data_provenance(path: Path, df: pd.DataFrame) -> Dict:
    """
    Build the data-provenance block stored in the model artifact metadata.

    Records the file checksum, row count, target distribution, and — when the
    checksum matches a known source in KNOWN_DATASET_SOURCES — the source URL,
    origin repository, and license.
    """
    sha256 = compute_sha256(path)
    known = KNOWN_DATASET_SOURCES.get(sha256, {})
    if "Churn" in df.columns:
        counts = df["Churn"].value_counts()
        target_distribution = {str(k): int(v) for k, v in counts.items()}
    else:
        target_distribution = {}
    return {
        "file": path.name,
        "sha256": sha256,
        "num_rows": int(len(df)),
        "target_distribution": target_distribution,
        "source_url": known.get("source_url"),
        "origin_repository": known.get("origin_repository"),
        "license": known.get("license"),
        "dataset": known.get("dataset", "unrecognized (checksum not in KNOWN_DATASET_SOURCES)"),
        "provenance_document": "docs/DATA_PROVENANCE.md",
    }


def select_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    min_recall: float = 0.70
) -> Tuple[float, Dict]:
    """
    Select the optimal threshold that achieves at least min_recall
    while maximizing precision.

    Returns:
        Tuple of (selected_threshold, selection_metadata)
    """
    # Sort unique probabilities
    thresholds = np.unique(y_prob)
    thresholds = np.sort(thresholds)

    best_threshold = 0.5
    best_precision = 0.0
    best_recall = 0.0
    best_f1 = 0.0
    candidates = []
    fallback_used = False

    for thresh in thresholds:
        y_pred = (y_prob >= thresh).astype(int)

        tp = np.sum((y_pred == 1) & (y_true == 1))
        fp = np.sum((y_pred == 1) & (y_true == 0))
        fn = np.sum((y_pred == 0) & (y_true == 1))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        candidates.append({
            "threshold": float(thresh),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "meets_recall": recall >= min_recall
        })

        # Track best threshold meeting recall requirement
        if recall >= min_recall and precision > best_precision:
            best_precision = precision
            best_recall = recall
            best_f1 = f1
            best_threshold = float(thresh)

    # If no threshold meets recall requirement, fall back to best F1
    if best_precision == 0.0:
        print(f"WARNING: No threshold achieves recall >= {min_recall}. Falling back to best F1.")
        fallback_used = True
        best_f1 = 0.0
        for c in candidates:
            if c["f1"] > best_f1:
                best_f1 = c["f1"]
                best_threshold = c["threshold"]
                best_precision = c["precision"]
                best_recall = c["recall"]

    metadata = {
        "selection_rule": f"highest_precision_at_recall_ge_{min_recall}",
        "min_recall_requirement": min_recall,
        "selected_threshold": best_threshold,
        "selected_precision": best_precision,
        "selected_recall": best_recall,
        "selected_f1": best_f1,
        "threshold_candidates": candidates[:20],  # Store top 20 for audit
        "fallback_used": fallback_used
    }

    return best_threshold, metadata


def resolve_data_path(data_path: str) -> Path:
    """
    Resolve the data path, supporting both absolute and relative paths.

    Args:
        data_path: Path to the training data CSV file

    Returns:
        Resolved absolute Path object

    Raises:
        FileNotFoundError: If the data file does not exist
    """
    path = Path(data_path)
    if not path.is_absolute():
        # Try relative to current working directory first
        if path.exists():
            return path.resolve()
        # Then try relative to project root
        project_root = Path(__file__).parent.parent
        alt_path = (project_root / path).resolve()
        if alt_path.exists():
            return alt_path

    if path.exists():
        return path.resolve()

    raise FileNotFoundError(
        f"Training data file not found: {data_path}. "
        f"Tried: {path.resolve()} and {(Path(__file__).parent.parent / path).resolve()}"
    )


def run(data_path: str | None = None, output_path: str | None = None, min_recall: float = 0.70, skip_quality_gate: bool = False) -> None:
    """
    Run the full training pipeline.

    Args:
        data_path: Path to training data CSV (uses default if None)
        output_path: Path to save model artifact (uses default if None)
        min_recall: Minimum recall requirement for threshold selection
    """
    # Resolve paths
    data_path_str: str = data_path or str(DEFAULT_DATA_PATH)
    output_path_str: str = output_path or str(DEFAULT_OUTPUT_PATH)

    resolved_data_path = resolve_data_path(data_path_str)
    output_path_obj = Path(output_path_str)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading data from {resolved_data_path}...")
    df = pd.read_csv(resolved_data_path)
    X = df.drop(columns=['customerID', 'Churn'])
    y = get_binary_target(df, 'Churn')

    # 3-way split: train (60%), validation (20%), test (20%)
    print("Splitting data (60/20/20 stratified)...")
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )

    print(f"  Train: {len(X_train)} samples")
    print(f"  Val:   {len(X_val)} samples")
    print(f"  Test:  {len(X_test)} samples")

    # 1. Fit Preprocessor on training data only
    print("Fitting preprocessor...")
    preprocessor = build_preprocessor()
    X_train_transformed = preprocessor.fit_transform(X_train)
    X_val_transformed = preprocessor.transform(X_val)
    X_test_transformed = preprocessor.transform(X_test)

    # 2. Extract Feature Names
    print("Extracting feature names...")
    feature_names = get_feature_names(preprocessor)

    # 3. Train Model
    print("Training Logistic Regression model...")
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_train_transformed, y_train)

    # 4. Get validation probabilities for threshold selection
    print("Computing validation probabilities for threshold selection...")
    val_prob = model.predict_proba(X_val_transformed)[:, 1]

    # 5. Select threshold on validation set
    print("Selecting optimal threshold...")
    threshold, threshold_metadata = select_threshold(
        y_val.values, val_prob, min_recall=min_recall
    )
    print(f"  Selected threshold: {threshold:.4f}")
    print(f"  Validation precision: {threshold_metadata['selected_precision']:.4f}")
    print(f"  Validation recall:    {threshold_metadata['selected_recall']:.4f}")
    print(f"  Validation F1:        {threshold_metadata['selected_f1']:.4f}")

    # 6. Evaluate on held-out test set (FINAL quality gate)
    print("Evaluating on held-out test set...")
    test_prob = model.predict_proba(X_test_transformed)[:, 1]
    test_pred = (test_prob >= threshold).astype(int)

    # Compute metrics at selected threshold
    from sklearn.metrics import (
        average_precision_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    test_precision = float(precision_score(y_test, test_pred, zero_division=0))
    test_recall = float(recall_score(y_test, test_pred, zero_division=0))
    test_f1 = float(f1_score(y_test, test_pred, zero_division=0))
    test_cm = confusion_matrix(y_test, test_pred).tolist()

    # ROC-AUC and PR-AUC
    test_roc_auc = float(roc_auc_score(y_test, test_prob))
    test_pr_auc = float(average_precision_score(y_test, test_prob))

    print(f"  Test ROC-AUC:    {test_roc_auc:.4f}")
    print(f"  Test PR-AUC:     {test_pr_auc:.4f}")
    print(f"  Test Precision:  {test_precision:.4f}")
    print(f"  Test Recall:     {test_recall:.4f}")
    print(f"  Test F1:         {test_f1:.4f}")
    print(f"  Test CM:         {test_cm}")

    # QUALITY GATE: ROC-AUC >= 0.80
    quality_gate_passed = test_roc_auc >= 0.80
    print(f"\n  QUALITY GATE (ROC-AUC >= 0.80): {'PASSED' if quality_gate_passed else 'FAILED'} ({test_roc_auc:.4f})")

    if not quality_gate_passed and not skip_quality_gate:
        raise RuntimeError(
            f"Quality gate failed: ROC-AUC = {test_roc_auc:.4f} < 0.80. "
            "Model does not meet minimum performance requirements."
        )

    # 7. Prepare reference predictions for drift monitoring (from validation set)
    print("\nPreparing reference predictions for drift monitoring...")
    reference_predictions = val_prob.tolist()

    # 7b. Prepare SHAP background sample (100 rows from validation set for LinearExplainer)
    # NO LEAKAGE: Preprocessor is fit ONLY on training data (line 237).
    # X_val_transformed uses the SAME fitted preprocessor (line 238).
    # SHAP background comes from validation set, NOT test set.
    # This ensures the explainer background distribution matches training-time transformations exactly.
    print("Preparing SHAP background sample...")
    n_background = min(100, len(X_val_transformed))
    rng = np.random.default_rng(42)
    background_indices = rng.choice(len(X_val_transformed), n_background, replace=False)
    shap_background = X_val_transformed[background_indices].tolist()
    print(f"  SHAP background sample size: {n_background}")

    # 8. Serialize Model Artifact with full metadata
    print("Serializing model artifact...")
    filepath = output_path_obj
    version = "1.0.0"

    # Data provenance (checksum-verified lineage; see docs/DATA_PROVENANCE.md)
    data_provenance = build_data_provenance(resolved_data_path, df)
    print(f"  Data SHA-256: {data_provenance['sha256']}")
    print(f"  Source:       {data_provenance['source_url'] or 'UNRECOGNIZED CHECKSUM'}")

    # Build comprehensive metadata
    metadata = {
        "version": version,
        "threshold": threshold,
        "threshold_metadata": threshold_metadata,
        "test_metrics": {
            "roc_auc": test_roc_auc,
            "pr_auc": test_pr_auc,
            "precision": test_precision,
            "recall": test_recall,
            "f1": test_f1,
            "confusion_matrix": test_cm,
        },
        "reference_predictions": reference_predictions,
        "shap_background": shap_background,
        "data_provenance": data_provenance,
        "timestamp": pd.Timestamp.now().isoformat(),
        "training_config": {
            "model_type": "LogisticRegression",
            "class_weight": "balanced",
            "max_iter": 1000,
            "random_state": 42,
            "train_samples": int(len(X_train)),
            "val_samples": int(len(X_val)),
            "test_samples": int(len(X_test)),
            "min_recall_requirement": 0.70
        }
    }

    serialize_model(
        model=model,
        preprocessor=preprocessor,
        feature_names=feature_names,
        threshold=threshold,
        version=version,
        filepath=str(filepath),
        metadata=metadata
    )

    print(f"Serialization complete. Artifact saved to {filepath}")
    print("\nArtifact metadata summary:")
    print(json.dumps({
        "version": version,
        "threshold": threshold,
        "test_roc_auc": test_roc_auc,
        "test_recall": test_recall,
        "test_precision": test_precision,
        "quality_gate_passed": quality_gate_passed
    }, indent=2))


def main() -> None:
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Train, evaluate, and serialize the churn prediction model.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Path to training data CSV (default: project-relative data/Telco-Customer-Churn.csv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for model artifact (default: models/model_v1.joblib)"
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=0.70,
        help="Minimum recall requirement for threshold selection (default: 0.70)"
    )
    parser.add_argument(
        "--skip-quality-gate",
        action="store_true",
        help="Skip the ROC-AUC quality gate (for test artifacts with small datasets)"
    )
    args = parser.parse_args()

    run(data_path=args.data_path, output_path=args.output, min_recall=args.min_recall, skip_quality_gate=args.skip_quality_gate)


if __name__ == "__main__":
    main()
