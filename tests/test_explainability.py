import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from src.explainability import (
    get_feature_names,
    get_global_explanation,
    get_local_explanation,
    get_shap_explainer,
)


@pytest.fixture
def mock_preprocessor():
    ct = ColumnTransformer(transformers=[
        ('num', StandardScaler(), ['A', 'B'])
    ])
    ct.fit(pd.DataFrame({'A': [1, 2], 'B': [3, 4]}))
    return ct

@pytest.fixture
def mock_model():
    model = LogisticRegression()
    X = np.array([[1, 2], [3, 4], [5, 6]])
    y = np.array([0, 1, 1])
    model.fit(X, y)
    return model, X

def test_get_feature_names(mock_preprocessor):
    features = get_feature_names(mock_preprocessor)
    assert features == ['A', 'B']

def test_explainability_functions(mock_model):
    model, X_bg = mock_model
    feature_names = ['A', 'B']

    explainer = get_shap_explainer(model, X_bg)
    assert explainer is not None

    X_instance = np.array([[2, 3]])
    local_exp = get_local_explanation(explainer, X_instance, feature_names)

    assert "base_value" in local_exp
    assert len(local_exp["features"]) == 2
    assert local_exp["features"][0]["name"] in feature_names

    global_exp = get_global_explanation(explainer, X_bg, feature_names)
    assert len(global_exp) == 2
    assert "importance" in global_exp[0]
