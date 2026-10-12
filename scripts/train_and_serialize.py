import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from src.explainability import get_feature_names
from src.model_management import serialize_model
from src.preprocessing import build_preprocessor, get_binary_target


def run():
    print("Loading data...")
    df = pd.read_csv('/tmp/Telco-Customer-Churn.csv')
    X = df.drop(columns=['customerID', 'Churn'])
    y = get_binary_target(df, 'Churn')

    # Stratified split to simulate how we trained it (though technically we can use full data for final artifact if desired,
    # we'll stick to the 80% to be safe and avoid overfitting bias on any downstream validation)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # 1. Fit Preprocessor
    print("Fitting preprocessor...")
    preprocessor = build_preprocessor()
    X_train_transformed = preprocessor.fit_transform(X_train)

    # 2. Extract Feature Names
    print("Extracting feature names...")
    feature_names = get_feature_names(preprocessor)

    # 3. Train Model
    print("Training Logistic Regression model...")
    model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_train_transformed, y_train)

    # 4. Serialize Model Artifact
    filepath = "models/model_v1.joblib"
    threshold = 0.65  # Chosen based on Milestone 6 findings
    version = "1.0.0"

    print(f"Serializing artifact to {filepath}...")
    serialize_model(
        model=model,
        preprocessor=preprocessor,
        feature_names=feature_names,
        threshold=threshold,
        version=version,
        filepath=filepath
    )

    print("Serialization complete.")

if __name__ == "__main__":
    run()
