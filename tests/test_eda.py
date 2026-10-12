import pandas as pd
import pytest

from src.eda import (
    calculate_class_imbalance,
    get_categorical_summary,
    get_numeric_summary,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        'Churn': ['Yes', 'No', 'No', 'No'],
        'tenure': [1, 10, 20, 30],
        'MonthlyCharges': [29.85, 56.95, 53.85, 42.30],
        'gender': ['Female', 'Male', 'Male', 'Female'],
        'customerID': ['id1', 'id2', 'id3', 'id4'] # High cardinality
    })

def test_calculate_class_imbalance(sample_df):
    imbalance = calculate_class_imbalance(sample_df, 'Churn')
    assert imbalance['No'] == 0.75
    assert imbalance['Yes'] == 0.25

    with pytest.raises(ValueError):
        calculate_class_imbalance(sample_df, 'NonExistentColumn')

def test_get_numeric_summary(sample_df):
    summary = get_numeric_summary(sample_df)
    assert 'tenure' in summary.index
    assert 'MonthlyCharges' in summary.index
    assert 'mean' in summary.columns
    assert summary.loc['tenure', 'count'] == 4.0

    empty_df = pd.DataFrame({'a': ['x', 'y']})
    assert get_numeric_summary(empty_df).empty

def test_get_categorical_summary(sample_df):
    summary = get_categorical_summary(sample_df)
    assert 'Churn' in summary
    assert 'gender' in summary
    assert summary['gender']['Female'] == 2
    assert summary['gender']['Male'] == 2
    # customerID should be excluded due to high cardinality relative to 50, but here it's 4.
    # However, in real data it's 7000. For our tiny mock, it is included since 4 <= 50.
    assert 'customerID' in summary
