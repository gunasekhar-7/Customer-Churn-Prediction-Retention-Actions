"""Script to create a minimal test model artifact for API testing.

This artifact is explicitly marked as a TEST artifact (version ends with '-test')
and will be rejected by production model loading code.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.explainability import get_feature_names
from src.model_management import serialize_model
from src.preprocessing import build_preprocessor


def run():
    print("Creating test model artifact...")

    # Create minimal training data
    np.random.seed(42)
    n_samples = 100

    # Create data matching the expected schema
    data = {
        'gender': np.random.choice(['Female', 'Male'], n_samples),
        'SeniorCitizen': np.random.choice([0, 1], n_samples),
        'Partner': np.random.choice(['Yes', 'No'], n_samples),
        'Dependents': np.random.choice(['Yes', 'No'], n_samples),
        'tenure': np.random.randint(0, 72, n_samples),
        'PhoneService': np.random.choice(['Yes', 'No'], n_samples),
        'MultipleLines': np.random.choice(['Yes', 'No', 'No phone service'], n_samples),
        'InternetService': np.random.choice(['DSL', 'Fiber optic', 'No'], n_samples),
        'OnlineSecurity': np.random.choice(['Yes', 'No', 'No internet service'], n_samples),
        'OnlineBackup': np.random.choice(['Yes', 'No', 'No internet service'], n_samples),
        'DeviceProtection': np.random.choice(['Yes', 'No', 'No internet service'], n_samples),
        'TechSupport': np.random.choice(['Yes', 'No', 'No internet service'], n_samples),
        'StreamingTV': np.random.choice(['Yes', 'No', 'No internet service'], n_samples),
        'StreamingMovies': np.random.choice(['Yes', 'No', 'No internet service'], n_samples),
        'Contract': np.random.choice(['Month-to-month', 'One year', 'Two year'], n_samples),
        'PaperlessBilling': np.random.choice(['Yes', 'No'], n_samples),
        'PaymentMethod': np.random.choice([
            'Electronic check', 'Mailed check',
            'Bank transfer (automatic)', 'Credit card (automatic)'
        ], n_samples),
        'MonthlyCharges': np.random.uniform(20, 120, n_samples),
        'TotalCharges': [str(np.random.uniform(20, 5000)) for _ in range(n_samples)]
    }

    df = pd.DataFrame(data)
    X = df
    y = np.random.choice([0, 1], n_samples, p=[0.73, 0.27])

    # 1. Fit Preprocessor
    print("Fitting preprocessor...")
    preprocessor = build_preprocessor()
    X_transformed = preprocessor.fit_transform(X)

    # 2. Extract Feature Names
    print("Extracting feature names...")
    feature_names = get_feature_names(preprocessor)

    # 3. Train Model
    print("Training Logistic Regression model...")
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_transformed, y)

    # 4. Generate minimal reference predictions for drift monitoring
    # Use a subset of training predictions as reference
    ref_probs = model.predict_proba(X_transformed)[:, 1].tolist()

    # 5. Serialize Model Artifact with test metadata
    # Save to default path so tests can load it (TestClient triggers lifespan)
    filepath = "models/model_v1.joblib"
    # Also save to test-specific path for test_test_artifact_on_disk_rejected_for_production
    test_filepath = "models/model_v1_test.joblib"
    threshold = 0.65
    version = "1.0.0-test"

    test_metadata = {
        "threshold_metadata": {
            "selection_rule": "test_fixed_threshold",
            "min_recall_requirement": 0.70,
            "selected_threshold": threshold,
            "selected_precision": 0.0,
            "selected_recall": 0.0,
            "selected_f1": 0.0,
            "threshold_candidates": [],
            "fallback_used": True
        },
        "test_metrics": {
            "roc_auc": 0.5,
            "pr_auc": 0.26,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "confusion_matrix": [[0, 0], [0, 0]]
        },
        "reference_predictions": ref_probs,
        "timestamp": pd.Timestamp.now().isoformat(),
        "training_config": {
            "model_type": "LogisticRegression",
            "class_weight": "balanced",
            "max_iter": 1000,
            "random_state": 42,
            "train_samples": n_samples,
            "val_samples": 0,
            "test_samples": 0,
            "min_recall_requirement": 0.70,
            "is_test_artifact": True
        }
    }

    print(f"Serializing artifact to {filepath}...")
    serialize_model(
        model=model,
        preprocessor=preprocessor,
        feature_names=feature_names,
        threshold=threshold,
        version=version,
        filepath=filepath,
        metadata=test_metadata,
        is_test_artifact=True
    )

    print(f"Serializing artifact to {test_filepath}...")
    serialize_model(
        model=model,
        preprocessor=preprocessor,
        feature_names=feature_names,
        threshold=threshold,
        version=version,
        filepath=test_filepath,
        metadata=test_metadata,
        is_test_artifact=True
    )

    print("Test artifact creation complete.")
    print(f"Created: {filepath} (version: {version})")
    print(f"Created: {test_filepath} (version: {version})")
    print("NOTE: This is a TEST artifact and will be REJECTED in production mode.")


if __name__ == "__main__":
    run()
