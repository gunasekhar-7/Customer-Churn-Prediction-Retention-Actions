from io import StringIO
from unittest.mock import patch

import pandas as pd
import pytest

from src.data_ingestion import (
    generate_data_quality_report,
    load_data,
    validate_dataframe_schema,
)

VALID_CSV = """customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges,Churn
7590-VHVEG,Female,0,Yes,No,1,No,No phone service,DSL,No,Yes,No,No,No,No,Month-to-month,Yes,Electronic check,29.85,29.85,No
5575-GNVDE,Male,0,No,No,34,Yes,No,DSL,Yes,No,Yes,No,No,No,One year,No,Mailed check,56.95,1889.5,No"""

def test_load_valid_csv(tmp_path):
    filepath = tmp_path / "valid.csv"
    filepath.write_text(VALID_CSV)
    df = load_data(str(filepath))
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == VALID_CSV.split('\n')[0].split(',')

def test_schema_validation_success():
    df = pd.read_csv(StringIO(VALID_CSV))
    errors = validate_dataframe_schema(df)
    assert len(errors) == 0

def test_missing_values_report():
    csv_with_missing = """customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges,Churn
7590-VHVEG,Female,,Yes,No,1,No,No phone service,DSL,No,Yes,No,No,No,No,Month-to-month,Yes,Electronic check,29.85,29.85,No"""
    df = pd.read_csv(StringIO(csv_with_missing))
    report = generate_data_quality_report(df)
    assert report['num_rows'] == 1
    assert report['missing_values']['SeniorCitizen'] == 1

def test_invalid_schema_type_mismatch():
    invalid_csv = """customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges,Churn
7590-VHVEG,Alien,2,Yes,No,-5,No,No phone service,Dial-up,No,Yes,No,No,No,No,Month-to-month,Yes,Cash,29.85,29.85,No"""
    df = pd.read_csv(StringIO(invalid_csv))
    errors = validate_dataframe_schema(df)
    assert len(errors) == 1
    row_errors = errors[0]['errors']
    error_locs = [e['loc'][0] for e in row_errors]
    assert 'gender' in error_locs
    assert 'SeniorCitizen' in error_locs
    assert 'tenure' in error_locs
    assert 'InternetService' in error_locs
    assert 'PaymentMethod' in error_locs

def test_data_ingestion_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_data("does_not_exist.csv")

@patch('src.data_ingestion.pd.read_csv')
def test_data_ingestion_value_error(mock_read):
    mock_read.side_effect = Exception("Generic pandas error")
    with pytest.raises(ValueError, match="Error loading file"):
        load_data("dummy.csv")
