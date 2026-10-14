from typing import Any, Optional, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class TotalChargesCleaner(BaseEstimator, TransformerMixin):
    """
    Custom transformer to clean the 'TotalCharges' column.
    """
    def fit(self, X: pd.DataFrame, y: Optional[Any] = None) -> "TotalChargesCleaner":
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> pd.DataFrame:
        if isinstance(X, np.ndarray):
            raise TypeError(
                "TotalChargesCleaner only accepts pandas DataFrame input. "
                "Received numpy.ndarray. This transformer requires column-based operations."
            )
        X_copy = X.copy()
        if 'TotalCharges' in X_copy.columns:
            X_copy['TotalCharges'] = pd.to_numeric(
                X_copy['TotalCharges'].replace(r'^\s*$', np.nan, regex=True)
            )
        return X_copy

    def get_feature_names_out(self, input_features: Optional[Any] = None) -> Any:
        return input_features

def build_preprocessor() -> ColumnTransformer:
    numeric_features = ['tenure', 'MonthlyCharges', 'TotalCharges']

    categorical_features = [
        'gender', 'SeniorCitizen', 'Partner', 'Dependents', 'PhoneService',
        'MultipleLines', 'InternetService', 'OnlineSecurity', 'OnlineBackup',
        'DeviceProtection', 'TechSupport', 'StreamingTV', 'StreamingMovies',
        'Contract', 'PaperlessBilling', 'PaymentMethod'
    ]

    numeric_transformer = Pipeline(steps=[
        ('cleaner', TotalChargesCleaner()),
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features),
            ('cat', categorical_transformer, categorical_features)
        ]
    )

    return preprocessor

def get_binary_target(df: pd.DataFrame, target_column: str = 'Churn') -> pd.Series:
    return df[target_column].map({'Yes': 1, 'No': 0})
