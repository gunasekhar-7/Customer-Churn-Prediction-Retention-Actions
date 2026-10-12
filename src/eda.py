from typing import Dict

import pandas as pd


def calculate_class_imbalance(df: pd.DataFrame, target_column: str) -> Dict[str, float]:
    """
    Calculates the distribution of classes in the target column.
    Returns a dictionary mapping class labels to their percentage representation.
    """
    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in dataframe.")

    counts = df[target_column].value_counts(normalize=True)
    return counts.to_dict()

def get_numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a statistical summary of all numeric columns in the dataframe.
    """
    numeric_df = df.select_dtypes(include=['number'])
    if numeric_df.empty:
        return pd.DataFrame()
    return numeric_df.describe().T

def get_categorical_summary(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """
    Returns value counts for all categorical columns (object or category dtype).
    Excludes high-cardinality columns (e.g., more than 50 unique values).
    """
    # updated to include 'str' as recommended by pandas 3.0 migration warning
    categorical_df = df.select_dtypes(include=['object', 'category', 'string'])
    summary = {}

    for col in categorical_df.columns:
        if categorical_df[col].nunique() <= 50:
            summary[col] = categorical_df[col].value_counts().to_dict()

    return summary
