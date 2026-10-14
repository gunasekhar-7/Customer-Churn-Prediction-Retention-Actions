"""Script to create a minimal test model artifact for API testing."""
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

    # 4. Serialize Model Artifact
    filepath = "models/model_v1.joblib"
    threshold = 0.65
    version = "1.0.0-test"

    print(f"Serializing artifact to {filepath}...")
    serialize_model(
        model=model,
        preprocessor=preprocessor,
        feature_names=feature_names,
        threshold=threshold,
        version=version,
        filepath=filepath
    )

    print("Test artifact creation complete.")


if __name__ == "__main__":
    run()
