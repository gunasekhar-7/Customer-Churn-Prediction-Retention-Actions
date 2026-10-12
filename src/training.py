from typing import Any, Dict

import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline


def train_model(pipeline: Pipeline, X: pd.DataFrame, y: pd.Series) -> Pipeline:
    """
    Fits a Scikit-Learn pipeline to the training data.
    """
    pipeline.fit(X, y)
    return pipeline

def evaluate_model(model: Pipeline, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
    """
    Evaluates a trained model on a dataset.
    Returns a dictionary of classification metrics.
    """
    y_pred = model.predict(X)

    metrics = {
        "precision": float(precision_score(y, y_pred, zero_division=0)),
        "recall": float(recall_score(y, y_pred, zero_division=0)),
        "f1": float(f1_score(y, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y, y_pred).tolist()
    }

    # Attempt to get probabilities for AUC scores
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X)[:, 1]
        metrics["roc_auc"] = float(roc_auc_score(y, y_prob))
        metrics["pr_auc"] = float(average_precision_score(y, y_prob))
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None

    return metrics

def run_hyperparameter_optimization(
    pipeline: Pipeline,
    param_grid: dict,
    X: pd.DataFrame,
    y: pd.Series,
    cv: int = 5,
    scoring: str = 'roc_auc'
) -> Pipeline:
    """
    Runs GridSearch to find the best hyperparameters.
    Returns the best estimator pipeline.
    """
    grid_search = GridSearchCV(
        pipeline,
        param_grid,
        cv=cv,
        scoring=scoring,
        n_jobs=-1
    )
    grid_search.fit(X, y)
    return grid_search.best_estimator_
