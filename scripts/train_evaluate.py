import json

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from src.preprocessing import build_preprocessor, get_binary_target
from src.training import evaluate_model, train_model


def run():
    print("Loading data...")
    df = pd.read_csv('/tmp/Telco-Customer-Churn.csv')

    # Preprocessing
    X = df.drop(columns=['customerID', 'Churn'])
    y = get_binary_target(df, 'Churn')

    print("Splitting data (stratified)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    preprocessor = build_preprocessor()

    models = {
        "Dummy": DummyClassifier(strategy="prior"),
        "LogisticRegression": LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42),
        "RandomForest": RandomForestClassifier(class_weight="balanced", random_state=42),
        "XGBoost": XGBClassifier(scale_pos_weight=(y_train==0).sum()/(y_train==1).sum(), random_state=42)
    }

    results = {}

    for name, clf in models.items():
        print(f"Training {name}...")
        pipeline = Pipeline([
            ('preprocessor', preprocessor),
            ('classifier', clf)
        ])

        trained_pipeline = train_model(pipeline, X_train, y_train)

        # Evaluate on test set
        metrics = evaluate_model(trained_pipeline, X_test, y_test)
        results[name] = metrics

    print("\n--- Model Evaluation Results (Test Set) ---")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run()
