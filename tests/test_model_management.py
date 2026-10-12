import os

import numpy as np
import pandas as pd
import pytest

from src.model_management import (
    clear_model_cache,
    get_model_artifact,
    load_model_artifact,
    serialize_model,
)


# Joblib cannot pickle local classes defined inside fixtures,
# so we must define the mock at the module level.
class GlobalMockModel:
    def predict_proba(self, X):
        return np.array([[0.1, 0.9], [0.8, 0.2]])

@pytest.fixture
def dummy_pipeline():
    return GlobalMockModel()

@pytest.fixture
def artifact_path(tmp_path):
    return str(tmp_path / "models" / "test_model.joblib")

def test_model_serialization(dummy_pipeline, artifact_path):
    serialize_model(
        model=dummy_pipeline,
        preprocessor=dummy_pipeline,
        feature_names=["f1", "f2"],
        threshold=0.65,
        version="v1.0-test",
        filepath=artifact_path
    )

    assert os.path.exists(artifact_path)

    artifact = load_model_artifact(artifact_path)
    assert "model" in artifact
    assert "preprocessor" in artifact
    assert "metadata" in artifact
    assert artifact["metadata"]["threshold"] == 0.65
    assert artifact["metadata"]["version"] == "v1.0-test"
    assert artifact["feature_names"] == ["f1", "f2"]

def test_prediction_equivalence(dummy_pipeline, artifact_path):
    serialize_model(dummy_pipeline, dummy_pipeline, [], 0.5, "v1", artifact_path)

    X_mock = pd.DataFrame({"a": [1, 2]})
    pre_probs = dummy_pipeline.predict_proba(X_mock)

    loaded_artifact = load_model_artifact(artifact_path)
    loaded_model = loaded_artifact["model"]
    post_probs = loaded_model.predict_proba(X_mock)

    np.testing.assert_array_almost_equal(pre_probs, post_probs)

def test_cached_loader(dummy_pipeline, artifact_path):
    serialize_model(dummy_pipeline, dummy_pipeline, [], 0.5, "v1", artifact_path)
    clear_model_cache()

    artifact1 = get_model_artifact(artifact_path)
    artifact2 = get_model_artifact(artifact_path)

    assert artifact1 is artifact2
