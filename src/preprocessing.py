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
    It replaces empty strings or spaces with NaN and converts to float.
    """
    def fit(self, X: pd.DataFrame, y=None):
        return self

    def transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        # Create a copy to avoid SettingWithCopyWarning
        X_copy = X.copy()

        # If passed a 2D numpy array somehow, handle it gracefully
        if isinstance(X_copy, np.ndarray):
             pass
        else:
            if 'TotalCharges' in X_copy.columns:
                # Replace whitespace strings with NaN, then cast to float
                X_copy['TotalCharges'] = pd.to_numeric(
                    X_copy['TotalCharges'].replace(r'^\s*$', np.nan, regex=True)
                )
        return X_copy

def build_preprocessor() -> ColumnTransformer:
    """
    Constructs a Scikit-Learn ColumnTransformer pipeline for the Telco dataset.
    Handles imputation, scaling, and categorical encoding.
    Expects input dataframe to NOT contain 'customerID' or 'Churn' columns.
    """
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
    """
    Converts 'Yes'/'No' string targets into binary 1/0.
    """
    return df[target_column].map({'Yes': 1, 'No': 0})
