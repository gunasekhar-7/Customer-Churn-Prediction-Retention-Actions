from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


class TelcoCustomerFeatures(BaseModel):
    """
    Customer features for inference - does NOT include the target label (Churn).
    Use this schema for prediction, explanation, and retention recommendation endpoints.
    """
    model_config = {"extra": "forbid"}

    customerID: str
    gender: Literal["Female", "Male"]
    SeniorCitizen: Literal[0, 1]
    Partner: Literal["Yes", "No"]
    Dependents: Literal["Yes", "No"]
    tenure: int = Field(ge=0)
    PhoneService: Literal["Yes", "No"]
    MultipleLines: Literal["Yes", "No", "No phone service"]
    InternetService: Literal["DSL", "Fiber optic", "No"]
    OnlineSecurity: Literal["Yes", "No", "No internet service"]
    OnlineBackup: Literal["Yes", "No", "No internet service"]
    DeviceProtection: Literal["Yes", "No", "No internet service"]
    TechSupport: Literal["Yes", "No", "No internet service"]
    StreamingTV: Literal["Yes", "No", "No internet service"]
    StreamingMovies: Literal["Yes", "No", "No internet service"]
    Contract: Literal["Month-to-month", "One year", "Two year"]
    PaperlessBilling: Literal["Yes", "No"]
    PaymentMethod: Literal[
        "Electronic check",
        "Mailed check",
        "Bank transfer (automatic)",
        "Credit card (automatic)"
    ]
    MonthlyCharges: float = Field(ge=0.0)
    TotalCharges: Union[float, str]


class TelcoCustomerRecord(TelcoCustomerFeatures):
    """
    Complete customer record including the target label (Churn).
    Use this schema for training data ingestion and validation.
    """
    Churn: Literal["Yes", "No"]


class PredictionResponse(BaseModel):
    customerID: str
    churn_probability: float
    churn_prediction: int
    risk_segment: str
    model_version: str


class BatchPredictionRequest(BaseModel):
    customers: List[TelcoCustomerFeatures]


class BatchPredictionResponse(BaseModel):
    predictions: List[PredictionResponse]


class FeatureContribution(BaseModel):
    name: str
    contribution: float


class ExplainResponse(BaseModel):
    customerID: str
    base_value: float
    features: List[FeatureContribution]


class RecommendationAction(BaseModel):
    action: str
    reason: str


class RetentionResponse(BaseModel):
    customerID: str
    risk_segment: str
    annual_revenue_exposure: float
    recommendations: List[RecommendationAction]


class DashboardMetricsResponse(BaseModel):
    total_customers: int
    high_risk_customers: int
    medium_risk_customers: int
    low_risk_customers: int
    annual_revenue_at_risk: float
    risk_distribution: dict


class ModelVersionInfo(BaseModel):
    """Information about a single model version."""
    version: str
    threshold: float
    timestamp: str
    test_roc_auc: Optional[float] = None
    test_recall: Optional[float] = None
    test_precision: Optional[float] = None
    is_current: bool = False


class ModelVersionsResponse(BaseModel):
    """Response for /model/versions endpoint."""
    versions: List[ModelVersionInfo]
    current_version: Optional[str] = None


class ModelCurrentResponse(BaseModel):
    """Response for /model/current endpoint."""
    version: str
    threshold: float
    timestamp: str
    test_roc_auc: Optional[float] = None
    test_recall: Optional[float] = None
    test_precision: Optional[float] = None
    feature_count: int
