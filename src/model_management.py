import os
from datetime import datetime
from typing import Any, Dict, cast

import joblib
from sklearn.pipeline import Pipeline

# Global cache for the loaded artifact to avoid disk I/O on every request
_MODEL_CACHE: Dict[str, Any] = {}

def serialize_model(
    model: Pipeline,
    preprocessor: Pipeline,
    feature_names: list,
    threshold: float,
    version: str,
    filepath: str
) -> None:
    """
    Packages the trained model, preprocessor, and metadata into a single artifact and saves it.
    """
    artifact = {
        "model": model,
        "preprocessor": preprocessor,
        "feature_names": feature_names,
        "metadata": {
            "version": version,
            "threshold": threshold,
            "timestamp": datetime.now().isoformat()
        }
    }

    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    joblib.dump(artifact, filepath)

def load_model_artifact(filepath: str) -> Dict[str, Any]:
    """
    Loads the artifact from disk.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Artifact not found at {filepath}")
    return cast(Dict[str, Any], joblib.load(filepath))

def get_model_artifact(filepath: str = "models/model_v1.joblib") -> Dict[str, Any]:
    """
    Singleton pattern loader. Reads from disk once, then serves from memory.
    Useful for application startup (FastAPI lifespan).
    """
    global _MODEL_CACHE
    if "artifact" not in _MODEL_CACHE:
        _MODEL_CACHE["artifact"] = load_model_artifact(filepath)
    return cast(Dict[str, Any], _MODEL_CACHE["artifact"])

def clear_model_cache() -> None:
    """Clears the cached model artifact (useful for testing)."""
    global _MODEL_CACHE
    _MODEL_CACHE.clear()
