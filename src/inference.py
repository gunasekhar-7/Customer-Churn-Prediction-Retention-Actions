from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline


def predict_with_threshold(pipeline: Pipeline, X: pd.DataFrame, threshold: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates binary predictions using a custom probability threshold.
    Returns a tuple of (binary_predictions, probabilities).
    """
    if not hasattr(pipeline, "predict_proba"):
        raise ValueError("Model in pipeline does not support probability prediction.")

    probabilities = pipeline.predict_proba(X)[:, 1]
    predictions = (probabilities >= threshold).astype(int)

    return predictions, probabilities
