from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


class TelcoCustomerRecord(BaseModel):
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
    Churn: Optional[Literal["Yes", "No"]] = None

class PredictionResponse(BaseModel):
    customerID: str
    churn_probability: float
    churn_prediction: int
    risk_segment: str
    model_version: str

class BatchPredictionRequest(BaseModel):
    customers: List[TelcoCustomerRecord]

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
