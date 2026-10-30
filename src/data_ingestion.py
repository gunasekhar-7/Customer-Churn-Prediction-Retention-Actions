from typing import Any, Dict, List, Literal

import pandas as pd
from pydantic import ValidationError

from src.schema import TelcoCustomerFeatures, TelcoCustomerRecord


def load_data(filepath: str) -> pd.DataFrame:
    """
    Loads data from a CSV file into a pandas DataFrame.
    """
    try:
        df = pd.read_csv(filepath)
        return df
    except FileNotFoundError as err:
        raise FileNotFoundError(f"File not found: {filepath}") from err
    except Exception as e:
        raise ValueError(f"Error loading file {filepath}: {e}") from e

def validate_dataframe_schema(
    df: pd.DataFrame,
    schema_type: Literal["training", "inference"] = "training"
) -> List[Dict[str, Any]]:
    """
    Validates a pandas DataFrame against the appropriate Pydantic schema.

    Args:
        df: DataFrame to validate
        schema_type: "training" for records with Churn label, "inference" for features only

    Returns:
        List of errors if any. Empty list means successful validation.
    """
    schema_class = TelcoCustomerRecord if schema_type == "training" else TelcoCustomerFeatures
    errors = []
    records = df.to_dict(orient="records")

    for i, record in enumerate(records):
        try:
            schema_class(**{str(k): v for k, v in record.items()})
        except ValidationError as e:
            errors.append({
                "row_index": i,
                "customerID": record.get("customerID"),
                "errors": e.errors()
            })
    return errors

def generate_data_quality_report(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generates a basic data quality report for the dataframe.
    """
    report = {
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "columns": list(df.columns),
        "missing_values": df.isnull().sum().to_dict(),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_customer_ids": int(df.duplicated(subset=['customerID']).sum()) if 'customerID' in df.columns else 0
    }
    return report
