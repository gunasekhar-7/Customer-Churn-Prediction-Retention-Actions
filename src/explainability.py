from typing import Any, Dict, List

import numpy as np
import shap
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer


def get_feature_names(preprocessor: ColumnTransformer) -> List[str]:
    """
    Extracts ordered feature names from the fitted Scikit-Learn ColumnTransformer.
    """
    feature_names = []

    for name, transformer, columns in preprocessor.transformers_:
        if name == 'drop' or transformer == 'drop':
            continue
        if name == 'remainder' and transformer == 'drop':
            continue

        if hasattr(transformer, 'get_feature_names_out'):
            # Generally handles OneHotEncoder, StandardScaler, etc.
            names = transformer.get_feature_names_out(columns)
            feature_names.extend(names)
        else:
            feature_names.extend(columns)

    return feature_names


def get_shap_explainer(model: BaseEstimator, X_background: np.ndarray) -> shap.Explainer:
    """
    Returns a fitted SHAP Explainer.
    Handles Linear models gracefully. Tree-based models are also supported but
    this specifically defaults to LinearExplainer or KernelExplainer depending on the model.
    """
    if hasattr(model, 'coef_'):
        # Linear model (Logistic Regression)
        return shap.LinearExplainer(model, X_background)
    elif hasattr(model, 'estimators_') or 'XGB' in str(type(model)):
        # Tree based
        return shap.TreeExplainer(model)
    else:
        # Fallback to Kernel (slow but universal)
        return shap.KernelExplainer(model.predict_proba, shap.sample(X_background, 100))


def get_local_explanation(
    explainer: shap.Explainer,
    X_instance: np.ndarray,
    feature_names: List[str]
) -> Dict[str, Any]:
    """
    Computes SHAP values for a single prediction instance.
    Returns a dictionary mapping feature names to their SHAP contributions.
    """
    shap_values = explainer.shap_values(X_instance)

    # LinearExplainer returns shape (n_samples, n_features) directly.
    # TreeExplainer might return a list of shapes if multi-class. For binary, we usually take index 1.
    if isinstance(shap_values, list):
        # Taking the positive class (Churn = 1)
        values = shap_values[1][0]
    else:
        # Some explainers just return a 1D array for single instances, others 2D
        if len(shap_values.shape) > 1:
            values = shap_values[0]
        else:
            values = shap_values

    # Base value logic varies by explainer
    base_val = explainer.expected_value
    if isinstance(base_val, (list, np.ndarray)):
        base_val = base_val[1] if len(base_val) > 1 else base_val[0]

    explanation: Dict[str, Any] = {
        "base_value": float(base_val),
        "features": []
    }

    for feature_name, value in zip(feature_names, values, strict=False):
        explanation["features"].append({
            "name": feature_name,
            "contribution": float(value)
        })

    # Sort by absolute magnitude of contribution
    explanation["features"] = sorted(explanation["features"], key=lambda x: abs(x["contribution"]), reverse=True)
    return explanation


def get_global_explanation(
    explainer: shap.Explainer,
    X_background: np.ndarray,
    feature_names: List[str]
) -> List[Dict[str, Any]]:
    """
    Computes the mean absolute SHAP value for each feature across the dataset to show global feature importance.
    """
    shap_values = explainer.shap_values(X_background)

    if isinstance(shap_values, list):
        values = shap_values[1]
    else:
        values = shap_values

    mean_abs_shap = np.abs(values).mean(axis=0)

    global_importance: List[Dict[str, Any]] = []
    for feature_name, value in zip(feature_names, mean_abs_shap, strict=False):
        global_importance.append({
            "name": feature_name,
            "importance": float(value)
        })

    global_importance = sorted(global_importance, key=lambda x: x["importance"], reverse=True)
    return global_importance
