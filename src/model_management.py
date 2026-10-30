import glob
import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import joblib
from sklearn.pipeline import Pipeline

from src.config import get_settings

# Global cache for the loaded artifact to avoid disk I/O on every request
_MODEL_CACHE: Dict[str, Any] = {}

REQUIRED_METADATA_KEYS = {
    "version",
    "threshold",
    "timestamp",
    "test_metrics",
    "reference_predictions",
    "training_config",
}


def serialize_model(
    model: Pipeline,
    preprocessor: Pipeline,
    feature_names: list,
    threshold: float,
    version: str,
    filepath: str,
    metadata: Optional[Dict[str, Any]] = None,
    is_test_artifact: bool = False
) -> None:
    """
    Packages the trained model, preprocessor, and metadata into a single artifact and saves it.

    Args:
        model: Trained model pipeline
        preprocessor: Fitted preprocessor pipeline
        feature_names: List of feature names
        threshold: Decision threshold for classification
        version: Model version string (must not end with '-test' for production)
        filepath: Output filepath
        metadata: Optional additional metadata (test metrics, threshold selection info, etc.)
        is_test_artifact: If True, allows version ending with '-test' and relaxes metadata requirements
    """
    # Validate version format
    if version.endswith("-test") and not is_test_artifact:
        raise ValueError(
            "Production model version cannot end with '-test'. "
            "Use a version like '1.0.0' for production artifacts, "
            "or pass is_test_artifact=True for test artifacts."
        )

    base_metadata = {
        "version": version,
        "threshold": threshold,
        "timestamp": datetime.now().isoformat()
    }

    if metadata:
        base_metadata.update(metadata)

    # For production artifacts, ensure required metadata keys are present
    if not is_test_artifact:
        missing_keys = REQUIRED_METADATA_KEYS - set(base_metadata.keys())
        if missing_keys:
            raise ValueError(f"Missing required metadata keys: {missing_keys}")

    # Use a placeholder for artifact_sha256 that will be replaced after computing the hash
    PLACEHOLDER_HASH = "0" * 64
    base_metadata["artifact_sha256"] = PLACEHOLDER_HASH

    artifact = {
        "model": model,
        "preprocessor": preprocessor,
        "feature_names": feature_names,
        "metadata": base_metadata
    }

    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Serialize with placeholder hash
    import io
    buffer = io.BytesIO()
    joblib.dump(artifact, buffer)
    artifact_bytes = buffer.getvalue()

    # Compute SHA-256 of the serialized bytes (with placeholder)
    actual_sha256 = hashlib.sha256(artifact_bytes).hexdigest()

    # Replace placeholder with actual hash in the serialized bytes
    # Both are 64-char hex strings, so binary replace preserves structure
    placeholder_bytes = PLACEHOLDER_HASH.encode('ascii')
    actual_bytes = actual_sha256.encode('ascii')
    final_bytes = artifact_bytes.replace(placeholder_bytes, actual_bytes)

    # Verify the replacement worked
    if final_bytes.count(actual_bytes) != artifact_bytes.count(placeholder_bytes):
        raise RuntimeError("Failed to replace placeholder hash in artifact")

    # Store the hash of the PLACEHOLDER version in metadata for verification
    base_metadata["artifact_sha256"] = actual_sha256

    # Update artifact with metadata that includes the stored hash
    artifact["metadata"] = base_metadata

    # Re-serialize with the stored hash (for loading)
    buffer = io.BytesIO()
    joblib.dump(artifact, buffer)
    final_bytes_for_disk = buffer.getvalue()

    # Write the final artifact to disk
    with open(filepath, "wb") as f:
        f.write(final_bytes_for_disk)


def _load_from_s3(bucket: str, key: str) -> Dict[str, Any]:
    """Load model artifact from S3."""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError as exc:
        raise RuntimeError("boto3 is required for S3 artifact loading. Install with: pip install boto3") from exc

    s3 = boto3.client("s3")
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        artifact_bytes = response["Body"].read()
        return cast(Dict[str, Any], joblib.load(artifact_bytes))
    except NoCredentialsError as exc:
        raise RuntimeError("AWS credentials not found. Configure credentials for S3 access.") from exc
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            raise FileNotFoundError(f"Artifact not found in S3: s3://{bucket}/{key}") from e
        raise RuntimeError(f"Failed to load artifact from S3: {e}") from e


def load_model_artifact(filepath: str, verify_integrity: bool = True) -> Dict[str, Any]:
    """
    Loads the artifact from disk and optionally verifies its integrity.

    Args:
        filepath: Path to the model artifact file
        verify_integrity: If True, verify SHA-256 checksum matches metadata

    Returns:
        Loaded artifact dictionary

    Raises:
        FileNotFoundError: If artifact file doesn't exist
        ValueError: If integrity verification fails
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Artifact not found at {filepath}")

    # Read file bytes for integrity verification
    with open(filepath, "rb") as f:
        artifact_bytes = f.read()

    # Load artifact
    import io
    artifact = cast(Dict[str, Any], joblib.load(io.BytesIO(artifact_bytes)))

    # Verify SHA-256 if requested
    if verify_integrity:
        metadata_sha256 = artifact.get("metadata", {}).get("artifact_sha256")
        if metadata_sha256:
            # For verification, replace the stored hash in the file bytes with the placeholder
            # and compute SHA-256 of the result
            PLACEHOLDER_HASH = "0" * 64
            placeholder_bytes = PLACEHOLDER_HASH.encode('ascii')
            stored_bytes = metadata_sha256.encode('ascii')

            # Replace stored hash with placeholder in the file bytes
            verification_bytes = artifact_bytes.replace(stored_bytes, placeholder_bytes)

            # Compute SHA-256 of the verification bytes (with placeholder)
            computed_sha256 = hashlib.sha256(verification_bytes).hexdigest()

            if metadata_sha256 != computed_sha256:
                raise ValueError(
                    f"Artifact integrity check failed: SHA-256 mismatch. "
                    f"Expected {metadata_sha256}, got {computed_sha256}. "
                    "Artifact may have been tampered with or corrupted."
                )

    return artifact


def validate_artifact(artifact: Dict[str, Any], require_production: bool = False) -> None:
    """
    Validates that the artifact has all required components and metadata.

    Args:
        artifact: The loaded model artifact
        require_production: If True, reject test artifacts and require
            production-grade provenance, feature schema, and reference data

    Raises:
        ValueError: If artifact is invalid or is a test artifact when production is required
    """
    # Check required top-level keys
    required_keys = {"model", "preprocessor", "feature_names", "metadata"}
    missing_keys = required_keys - set(artifact.keys())
    if missing_keys:
        raise ValueError(f"Artifact missing required keys: {missing_keys}")

    metadata = artifact.get("metadata", {})

    # Check required metadata keys
    missing_metadata = REQUIRED_METADATA_KEYS - set(metadata.keys())
    if missing_metadata:
        raise ValueError(f"Artifact metadata missing required keys: {missing_metadata}")

    # Check version
    version = metadata.get("version", "")
    if require_production and version.endswith("-test"):
        raise ValueError(
            f"Test artifact (version '{version}') cannot be used in production mode. "
            "Provide a production artifact with version like '1.0.0'."
        )

    # Validate test_metrics structure
    test_metrics = metadata.get("test_metrics", {})
    required_metrics = {"roc_auc", "pr_auc", "precision", "recall", "f1", "confusion_matrix"}
    missing_metrics = required_metrics - set(test_metrics.keys())
    if missing_metrics:
        raise ValueError(f"test_metrics missing required keys: {missing_metrics}")

    # Validate reference_predictions
    reference_predictions = metadata.get("reference_predictions", [])
    if not isinstance(reference_predictions, list) or len(reference_predictions) == 0:
        raise ValueError("reference_predictions must be a non-empty list for drift monitoring")

    # Validate threshold is a valid float
    threshold = metadata.get("threshold")
    if not isinstance(threshold, (int, float)) or not (0 <= threshold <= 1):
        raise ValueError(f"Invalid threshold value: {threshold}. Must be float between 0 and 1.")

    if require_production:
        _validate_production_requirements(artifact, metadata)


def _validate_production_requirements(
    artifact: Dict[str, Any], metadata: Dict[str, Any]
) -> None:
    """
    Part E production checks: feature schema, threshold metadata, drift
    reference data, and resolvable data provenance must all be present.

    Raises:
        ValueError: If any production requirement is not met.
    """
    # Feature schema must be declared
    feature_names = artifact.get("feature_names")
    if not isinstance(feature_names, list) or not feature_names:
        raise ValueError(
            "Production artifact must declare a non-empty feature schema "
            "('feature_names') matching training-time feature order."
        )

    # Data provenance must be present and resolvable (provenance validation)
    provenance = metadata.get("data_provenance")
    if not isinstance(provenance, dict):
        raise ValueError(
            "Production artifact must include a 'data_provenance' metadata block "
            "(sha256, source_url, license). See docs/DATA_PROVENANCE.md."
        )
    sha256 = provenance.get("sha256")
    if not (
        isinstance(sha256, str)
        and len(sha256) == 64
        and all(c in "0123456789abcdef" for c in sha256.lower())
    ):
        raise ValueError(f"Invalid data_provenance.sha256: {sha256!r}")
    if not provenance.get("source_url"):
        raise ValueError(
            "data_provenance.source_url is missing; the artifact's dataset origin "
            "cannot be established (unrecognized checksum?). Training on an unknown "
            "dataset does not qualify for production."
        )
    if not provenance.get("license"):
        raise ValueError("data_provenance.license is missing; usage terms are unknown.")


def get_model_artifact(
    filepath: Optional[str] = None,
    require_production: bool = False
) -> Dict[str, Any]:
    """
    Singleton pattern loader. Reads from disk/S3 once, then serves from memory.
    Useful for application startup (FastAPI lifespan).

    Args:
        filepath: Local path to artifact (uses config default if None)
        require_production: If True, validate that artifact is production-ready

    Returns:
        Loaded and validated artifact dictionary

    Raises:
        FileNotFoundError: If artifact not found locally or in S3
        ValueError: If artifact validation fails
        RuntimeError: If S3 loading fails
    """
    global _MODEL_CACHE
    cache_key = f"artifact:{filepath}:{require_production}"

    if cache_key not in _MODEL_CACHE:
        settings = get_settings()

        # Determine artifact source
        if settings.is_production and settings.MODEL_ARTIFACTS_BUCKET and settings.MODEL_ARTIFACTS_KEY:
            # Load from S3 in production
            artifact = _load_from_s3(settings.MODEL_ARTIFACTS_BUCKET, settings.MODEL_ARTIFACTS_KEY)
        else:
            # Load from local path with integrity verification
            local_path = filepath or settings.MODEL_ARTIFACT_LOCAL_PATH
            artifact = load_model_artifact(local_path, verify_integrity=True)

        # Validate artifact
        validate_artifact(artifact, require_production=require_production)

        _MODEL_CACHE[cache_key] = artifact

    return cast(Dict[str, Any], _MODEL_CACHE[cache_key])


def clear_model_cache() -> None:
    """Clears the cached model artifact (useful for testing)."""
    global _MODEL_CACHE
    _MODEL_CACHE.clear()


def list_model_versions(models_dir: str = "models") -> List[Dict[str, Any]]:
    """
    Scan the models directory and return metadata for all available model artifacts.

    Args:
        models_dir: Directory containing model artifacts

    Returns:
        List of model version metadata dictionaries, sorted by version (newest first)
    """
    versions: List[Dict[str, Any]] = []

    if not os.path.exists(models_dir):
        return versions

    # Find all .joblib files
    for filepath in glob.glob(os.path.join(models_dir, "*.joblib")):
        try:
            # Load artifact without requiring production validation
            artifact = load_model_artifact(filepath, verify_integrity=False)
            metadata = artifact.get("metadata", {})

            version_info: Dict[str, Any] = {
                "version": metadata.get("version", "unknown"),
                "threshold": metadata.get("threshold", 0.0),
                "timestamp": metadata.get("timestamp", ""),
                "test_roc_auc": metadata.get("test_metrics", {}).get("roc_auc"),
                "test_recall": metadata.get("test_metrics", {}).get("recall"),
                "test_precision": metadata.get("test_metrics", {}).get("precision"),
                "filepath": filepath,
                "is_test_artifact": metadata.get("version", "").endswith("-test"),
            }
            versions.append(version_info)
        except Exception:
            # Skip corrupted or unreadable artifacts
            continue

    # Sort by version (semantic versioning) - newest first
    def version_key(v: Dict[str, Any]) -> tuple:
        try:
            parts = v["version"].replace("-test", "").split(".")
            return tuple(int(p) for p in parts)
        except (ValueError, AttributeError):
            return (0, 0, 0)

    versions.sort(key=version_key, reverse=True)
    return versions


def get_current_model_version(models_dir: str = "models") -> Optional[str]:
    """
    Get the current (latest production) model version.

    Args:
        models_dir: Directory containing model artifacts

    Returns:
        Current production version string, or None if no production artifact found
    """
    versions = list_model_versions(models_dir)
    for v in versions:
        if not v["is_test_artifact"]:
            return str(v["version"])
    return None
