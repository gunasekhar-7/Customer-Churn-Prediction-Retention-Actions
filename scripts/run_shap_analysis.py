from pathlib import Path

import pandas as pd
import shap
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from src.explainability import (
    get_feature_names,
    get_global_explanation,
    get_local_explanation,
    get_shap_explainer,
)
from src.inference import predict_with_threshold
from src.preprocessing import build_preprocessor, get_binary_target


def resolve_data_path(data_path: str = None) -> str:
    """Resolve data path relative to project root if not absolute."""
    if data_path is None:
        data_path = "data/Telco-Customer-Churn.csv"
    path = Path(data_path)
    if path.is_absolute():
        return str(path)
    # Try relative to current working directory
    if path.exists():
        return str(path.resolve())
    # Try relative to project root (parent of scripts directory)
    project_root = Path(__file__).parent.parent
    alt_path = (project_root / path).resolve()
    if alt_path.exists():
        return str(alt_path)
    # Return original path (will fail with clear error in pd.read_csv)
    return str(path.resolve())


def run(data_path: str = None):
    print("Loading data...")
    data_path = resolve_data_path(data_path)
    df = pd.read_csv(data_path)
    X = df.drop(columns=['customerID', 'Churn'])
    y = get_binary_target(df, 'Churn')

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Pipeline components isolated so we can pass transformed data directly to SHAP
    preprocessor = build_preprocessor()
    print("Fitting preprocessor...")
    X_train_transformed = preprocessor.fit_transform(X_train)
    X_test_transformed = preprocessor.transform(X_test)

    print("Extracting feature names...")
    feature_names = get_feature_names(preprocessor)

    print("Training Logistic Regression...")
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_train_transformed, y_train)

    # Let's mock a pipeline object just to test the threshold function
    class MockPipeline:
        def predict_proba(self, X):
            return model.predict_proba(preprocessor.transform(X))

    pipeline = MockPipeline()

    print("Testing Threshold mechanism (Threshold = 0.5 vs Threshold = 0.65)...")
    preds_05, _ = predict_with_threshold(pipeline, X_test, threshold=0.5)
    preds_065, _ = predict_with_threshold(pipeline, X_test, threshold=0.65)

    print(f"Total Churn predictions @ 0.5: {sum(preds_05)}")
    print(f"Total Churn predictions @ 0.65: {sum(preds_065)}")

    print("\nCalculating SHAP Explanations...")
    # Background for SHAP (using a small sample of train to speed it up)
    background = shap.sample(X_train_transformed, 100)

    explainer = get_shap_explainer(model, background)

    print("--- Top 5 Global Feature Importances ---")
    global_exp = get_global_explanation(explainer, background, feature_names)
    for feat in global_exp[:5]:
        print(f"{feat['name']}: {feat['importance']:.4f}")

    print("\n--- Local Explanation for 1st Test Customer ---")
    local_exp = get_local_explanation(explainer, X_test_transformed[[0]], feature_names)
    print(f"Base Value: {local_exp['base_value']:.4f}")
    for feat in local_exp['features'][:5]:
         print(f"{feat['name']}: {feat['contribution']:.4f}")

if __name__ == "__main__":
    run()
