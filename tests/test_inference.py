import numpy as np
import pandas as pd
import pytest

from src.inference import predict_with_threshold


class DummyPipeline:
    def predict_proba(self, X):
        # Mocking 2 classes, probabilities for class 0 and 1
        return np.array([[0.8, 0.2], [0.4, 0.6], [0.1, 0.9]])

def test_predict_with_threshold():
    pipeline = DummyPipeline()
    X_mock = pd.DataFrame() # Not used by mock

    # Test standard 0.5 threshold
    preds, probs = predict_with_threshold(pipeline, X_mock, threshold=0.5)
    assert list(preds) == [0, 1, 1]
    assert list(probs) == [0.2, 0.6, 0.9]

    # Test high threshold
    preds_high, _ = predict_with_threshold(pipeline, X_mock, threshold=0.7)
    assert list(preds_high) == [0, 0, 1]

    # Test low threshold
    preds_low, _ = predict_with_threshold(pipeline, X_mock, threshold=0.15)
    assert list(preds_low) == [1, 1, 1]

def test_predict_with_threshold_raises_error():
    class BadPipeline:
        pass

    with pytest.raises(ValueError):
        predict_with_threshold(BadPipeline(), pd.DataFrame())
