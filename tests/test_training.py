import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.training import evaluate_model, run_hyperparameter_optimization, train_model


@pytest.fixture
def dummy_data():
    X = pd.DataFrame({
        'feature1': np.random.rand(100),
        'feature2': np.random.rand(100)
    })
    y = pd.Series(np.random.randint(0, 2, 100))
    return X, y

@pytest.fixture
def simple_pipeline():
    return Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression())
    ])

def test_train_model(simple_pipeline, dummy_data):
    X, y = dummy_data
    trained_model = train_model(simple_pipeline, X, y)

    # Check if model has been fitted by predicting on dummy data
    preds = trained_model.predict(X)
    assert len(preds) == 100
    assert set(preds).issubset({0, 1})

def test_evaluate_model(simple_pipeline, dummy_data):
    X, y = dummy_data
    trained_model = train_model(simple_pipeline, X, y)
    metrics = evaluate_model(trained_model, X, y)

    expected_keys = ['precision', 'recall', 'f1', 'confusion_matrix', 'roc_auc', 'pr_auc']
    for key in expected_keys:
        assert key in metrics

    assert isinstance(metrics['roc_auc'], float)
    assert isinstance(metrics['confusion_matrix'], list)

def test_run_hyperparameter_optimization(simple_pipeline, dummy_data):
    X, y = dummy_data
    param_grid = {
        'classifier__C': [0.1, 1.0]
    }

    best_model = run_hyperparameter_optimization(simple_pipeline, param_grid, X, y, cv=2)
    assert isinstance(best_model, Pipeline)
    assert best_model.named_steps['classifier'].C in [0.1, 1.0]


class MockModelNoProba:
    def predict(self, X):
        return np.array([0, 1])

def test_evaluate_model_no_predict_proba():
    model = MockModelNoProba()
    X = pd.DataFrame()
    y = pd.Series([0, 1])
    metrics = evaluate_model(model, X, y)
    assert metrics['roc_auc'] is None
    assert metrics['pr_auc'] is None
