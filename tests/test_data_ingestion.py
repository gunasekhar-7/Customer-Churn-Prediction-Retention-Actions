from io import StringIO

import pandas as pd

from src.data_ingestion import (
    generate_data_quality_report,
    load_data,
    validate_dataframe_schema,
)

# A valid tiny CSV string matching the IBM Telco format
VALID_CSV = """customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges,Churn
7590-VHVEG,Female,0,Yes,No,1,No,No phone service,DSL,No,Yes,No,No,No,No,Month-to-month,Yes,Electronic check,29.85,29.85,No
5575-GNVDE,Male,0,No,No,34,Yes,No,DSL,Yes,No,Yes,No,No,No,One year,No,Mailed check,56.95,1889.5,No"""

def test_load_valid_csv(tmp_path):
    """Test loading a valid CSV file."""
    filepath = tmp_path / "valid.csv"
    filepath.write_text(VALID_CSV)

    df = load_data(str(filepath))
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == VALID_CSV.split('\n')[0].split(',')

def test_schema_validation_success():
    """Test that a valid dataframe passes schema validation with no errors."""
    df = pd.read_csv(StringIO(VALID_CSV))
    errors = validate_dataframe_schema(df)
    assert len(errors) == 0, f"Expected 0 errors, got {len(errors)}: {errors}"

def test_missing_values_report():
    """Test that missing values are correctly identified in the quality report."""
    csv_with_missing = """customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges,Churn
7590-VHVEG,Female,,Yes,No,1,No,No phone service,DSL,No,Yes,No,No,No,No,Month-to-month,Yes,Electronic check,29.85,29.85,No"""
    df = pd.read_csv(StringIO(csv_with_missing))
    report = generate_data_quality_report(df)

    assert report['num_rows'] == 1
    assert report['missing_values']['SeniorCitizen'] == 1

def test_invalid_schema_type_mismatch():
    """Test that schema validation catches type mismatches and invalid values."""
    invalid_csv = """customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges,Churn
7590-VHVEG,Alien,2,Yes,No,-5,No,No phone service,Dial-up,No,Yes,No,No,No,No,Month-to-month,Yes,Cash,29.85,29.85,No"""
    df = pd.read_csv(StringIO(invalid_csv))
    errors = validate_dataframe_schema(df)

    assert len(errors) == 1
    row_errors = errors[0]['errors']

    error_locs = [e['loc'][0] for e in row_errors]
    assert 'gender' in error_locs  # 'Alien' is not valid
    assert 'SeniorCitizen' in error_locs # 2 is not valid
    assert 'tenure' in error_locs # -5 is not valid (must be >= 0)
    assert 'InternetService' in error_locs # 'Dial-up' is not valid
    assert 'PaymentMethod' in error_locs # 'Cash' is not valid
