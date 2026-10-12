import os
from typing import Any, Dict, List

import httpx

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

def get_health() -> bool:
    try:
        response = httpx.get(f"{API_URL}/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False

def get_model_info() -> Dict[str, Any]:
    response = httpx.get(f"{API_URL}/model/info", timeout=5.0)
    response.raise_for_status()
    return response.json()

def predict(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    response = httpx.post(f"{API_URL}/predict", json=customer_data, timeout=10.0)
    response.raise_for_status()
    return response.json()

def predict_batch(customers_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    response = httpx.post(f"{API_URL}/predict/batch", json={"customers": customers_data}, timeout=30.0)
    response.raise_for_status()
    return response.json()

def explain(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    response = httpx.post(f"{API_URL}/explain", json=customer_data, timeout=10.0)
    response.raise_for_status()
    return response.json()

def get_retention_recommendation(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    response = httpx.post(f"{API_URL}/retention-recommendation", json=customer_data, timeout=10.0)
    response.raise_for_status()
    return response.json()
