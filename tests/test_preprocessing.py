import numpy as np
import pandas as pd
import pytest

from src.preprocessing import build_preprocessor, get_binary_target


@pytest.fixture
def mock_raw_data():
    return pd.DataFrame({
        'gender': ['Female', 'Male'],
        'SeniorCitizen': [0, 1],
        'Partner': ['Yes', 'No'],
        'Dependents': ['No', 'Yes'],
        'tenure': [1, 24],
        'PhoneService': ['No', 'Yes'],
        'MultipleLines': ['No phone service', 'Yes'],
        'InternetService': ['DSL', 'Fiber optic'],
        'OnlineSecurity': ['No', 'Yes'],
        'OnlineBackup': ['Yes', 'No'],
        'DeviceProtection': ['No', 'Yes'],
        'TechSupport': ['No', 'Yes'],
        'StreamingTV': ['No', 'Yes'],
        'StreamingMovies': ['No', 'Yes'],
        'Contract': ['Month-to-month', 'One year'],
        'PaperlessBilling': ['Yes', 'No'],
        'PaymentMethod': ['Electronic check', 'Mailed check'],
        'MonthlyCharges': [29.85, 89.10],
        'TotalCharges': ['29.85', '2138.4']
    })

@pytest.fixture
def mock_raw_data_with_missing():
    df = pd.DataFrame({
        'gender': ['Female', 'Male'],
        'SeniorCitizen': [0, 1],
        'Partner': ['Yes', 'No'],
        'Dependents': ['No', 'Yes'],
        'tenure': [0, 24], # 0 tenure usually means missing TotalCharges
        'PhoneService': ['No', 'Yes'],
        'MultipleLines': ['No phone service', 'Yes'],
        'InternetService': ['DSL', 'Fiber optic'],
        'OnlineSecurity': ['No', 'Yes'],
        'OnlineBackup': ['Yes', 'No'],
        'DeviceProtection': ['No', 'Yes'],
        'TechSupport': ['No', 'Yes'],
        'StreamingTV': ['No', 'Yes'],
        'StreamingMovies': ['No', 'Yes'],
        'Contract': ['Two year', 'One year'],
        'PaperlessBilling': ['Yes', 'No'],
        'PaymentMethod': ['Mailed check', 'Mailed check'],
        'MonthlyCharges': [52.55, 89.10],
        'TotalCharges': [' ', '2138.4'] # Blank space
    })
    return df

def test_build_preprocessor_structure():
    preprocessor = build_preprocessor()
    assert preprocessor is not None

    # Check that it has transformers configured
    transformers = preprocessor.transformers
    assert len(transformers) == 2

    num_tf = [t for t in transformers if t[0] == 'num'][0]
    cat_tf = [t for t in transformers if t[0] == 'cat'][0]

    assert 'TotalCharges' in num_tf[2]
    assert 'gender' in cat_tf[2]

def test_pipeline_transform_valid_data(mock_raw_data):
    preprocessor = build_preprocessor()
    transformed = preprocessor.fit_transform(mock_raw_data)

    # Should return a 2D numpy array
    assert isinstance(transformed, np.ndarray)
    assert transformed.shape[0] == 2
    # Number of columns will be large due to OneHotEncoding
    assert transformed.shape[1] > 10

def test_pipeline_transform_missing_total_charges(mock_raw_data_with_missing):
    preprocessor = build_preprocessor()
    # If the cleaner works, it converts ' ' to NaN, then SimpleImputer fills with median.
    transformed = preprocessor.fit_transform(mock_raw_data_with_missing)

    # Should not contain any NaNs
    assert not np.isnan(transformed).any()

def test_get_binary_target():
    df = pd.DataFrame({'Churn': ['Yes', 'No', 'Yes']})
    target = get_binary_target(df)
    assert target.tolist() == [1, 0, 1]
