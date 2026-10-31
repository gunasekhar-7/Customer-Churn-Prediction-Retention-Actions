#!/usr/bin/env python
"""
Locust load test for Customer Churn Prediction API.

Tests the /predict endpoint with realistic customer data.

Usage:
    # Run in headless mode for CI (30 seconds, 10 users, spawn rate 2/s)
    locust -f scripts/locustfile.py --headless -u 10 -r 2 --run-time 30s --host http://localhost:8000

    # Run with web UI for manual testing
    locust -f scripts/locustfile.py --host http://localhost:8000

Requirements:
    pip install locust
"""

import json
import os
import random

from locust import HttpUser, between, events, task
from locust.env import Environment

# Sample customer data for load testing (Telco schema)
SAMPLE_CUSTOMERS = [
    {
        "customerID": "LOAD-001",
        "gender": "Male",
        "SeniorCitizen": 0,
        "Partner": "No",
        "Dependents": "No",
        "tenure": 2,
        "PhoneService": "Yes",
        "MultipleLines": "No",
        "InternetService": "Fiber optic",
        "OnlineSecurity": "No",
        "OnlineBackup": "No",
        "DeviceProtection": "No",
        "TechSupport": "No",
        "StreamingTV": "Yes",
        "StreamingMovies": "Yes",
        "Contract": "Month-to-month",
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check",
        "MonthlyCharges": 95.0,
        "TotalCharges": 190.0
    },
    {
        "customerID": "LOAD-002",
        "gender": "Female",
        "SeniorCitizen": 0,
        "Partner": "Yes",
        "Dependents": "No",
        "tenure": 12,
        "PhoneService": "Yes",
        "MultipleLines": "Yes",
        "InternetService": "DSL",
        "OnlineSecurity": "Yes",
        "OnlineBackup": "Yes",
        "DeviceProtection": "Yes",
        "TechSupport": "Yes",
        "StreamingTV": "No",
        "StreamingMovies": "No",
        "Contract": "One year",
        "PaperlessBilling": "No",
        "PaymentMethod": "Bank transfer (automatic)",
        "MonthlyCharges": 45.0,
        "TotalCharges": 540.0
    },
    {
        "customerID": "LOAD-003",
        "gender": "Male",
        "SeniorCitizen": 1,
        "Partner": "Yes",
        "Dependents": "Yes",
        "tenure": 48,
        "PhoneService": "Yes",
        "MultipleLines": "Yes",
        "InternetService": "Fiber optic",
        "OnlineSecurity": "Yes",
        "OnlineBackup": "Yes",
        "DeviceProtection": "Yes",
        "TechSupport": "Yes",
        "StreamingTV": "Yes",
        "StreamingMovies": "Yes",
        "Contract": "Two year",
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Credit card (automatic)",
        "MonthlyCharges": 110.0,
        "TotalCharges": 5280.0
    },
    {
        "customerID": "LOAD-004",
        "gender": "Female",
        "SeniorCitizen": 0,
        "Partner": "No",
        "Dependents": "No",
        "tenure": 6,
        "PhoneService": "No",
        "MultipleLines": "No phone service",
        "InternetService": "No",
        "OnlineSecurity": "No internet service",
        "OnlineBackup": "No internet service",
        "DeviceProtection": "No internet service",
        "TechSupport": "No internet service",
        "StreamingTV": "No internet service",
        "StreamingMovies": "No internet service",
        "Contract": "Month-to-month",
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check",
        "MonthlyCharges": 25.0,
        "TotalCharges": 150.0
    },
    {
        "customerID": "LOAD-005",
        "gender": "Male",
        "SeniorCitizen": 0,
        "Partner": "Yes",
        "Dependents": "Yes",
        "tenure": 24,
        "PhoneService": "Yes",
        "MultipleLines": "No",
        "InternetService": "DSL",
        "OnlineSecurity": "No",
        "OnlineBackup": "No",
        "DeviceProtection": "No",
        "TechSupport": "No",
        "StreamingTV": "No",
        "StreamingMovies": "No",
        "Contract": "One year",
        "PaperlessBilling": "No",
        "PaymentMethod": "Mailed check",
        "MonthlyCharges": 55.0,
        "TotalCharges": 1320.0
    }
]


class ChurnAPIUser(HttpUser):
    """Simulates a user making predictions against the Churn API."""

    wait_time = between(0.5, 2.0)  # Wait 0.5-2 seconds between requests

    def on_start(self):
        """Called when a simulated user starts."""
        self.api_key = "dev-api-key-min-32-chars-long"
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    @task(5)
    def predict_single(self):
        """Single prediction endpoint - primary load test target."""
        customer = random.choice(SAMPLE_CUSTOMERS).copy()
        customer["customerID"] = f"LOAD-{random.randint(1000, 9999)}"

        with self.client.post(
            "/predict",
            json=customer,
            headers=self.headers,
            catch_response=True,
            name="/predict"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "churn_probability" in data and "risk_segment" in data:
                        response.success()
                    else:
                        response.failure("Missing expected fields in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")

    @task(1)
    def predict_batch(self):
        """Batch prediction endpoint - less frequent but heavier."""
        batch_size = random.randint(5, 20)
        customers = []
        for _ in range(batch_size):
            customer = random.choice(SAMPLE_CUSTOMERS).copy()
            customer["customerID"] = f"LOAD-{random.randint(1000, 9999)}"
            customers.append(customer)

        with self.client.post(
            "/predict/batch",
            json={"customers": customers},
            headers=self.headers,
            catch_response=True,
            name="/predict/batch"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "predictions" in data and len(data["predictions"]) == batch_size:
                        response.success()
                    else:
                        response.failure("Batch response size mismatch")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")

    @task(1)
    def health_check(self):
        """Health check endpoint - no auth required."""
        with self.client.get("/health", catch_response=True, name="/health") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def ready_check(self):
        """Readiness check endpoint - no auth required."""
        with self.client.get("/ready", catch_response=True, name="/ready") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


# Custom event hooks for CI integration
@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    print(f"Load test starting with {environment.runner.user_count} users")


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs):
    stats = environment.stats
    print("\n=== LOAD TEST SUMMARY ===")
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Failure Rate: {stats.total.fail_ratio * 100:.2f}%")
    print(f"Avg Response Time: {stats.total.avg_response_time:.2f} ms")
    print(f"Median Response Time: {stats.total.median_response_time:.2f} ms")
    print(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f} ms")
    print(f"99th Percentile: {stats.total.get_response_time_percentile(0.99):.2f} ms")
    print(f"Max Response Time: {stats.total.max_response_time:.2f} ms")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")

    # Per-endpoint stats
    print("\n=== PER-ENDPOINT ===")
    for name, entry in stats.entries.items():
        if entry.num_requests > 0:
            print(f"{name}: {entry.num_requests} reqs, "
                  f"avg={entry.avg_response_time:.1f}ms, "
                  f"p95={entry.get_response_time_percentile(0.95):.1f}ms, "
                  f"failures={entry.num_failures}")


# Assertion for CI - fails if p95 > threshold or failure rate > 1%
@events.quitting.add_listener
def on_quitting(environment: Environment, **kwargs):
    stats = environment.stats

    # Check p95 latency
    p95 = stats.total.get_response_time_percentile(0.95)
    p95_threshold = float(os.getenv("LOCUST_P95_THRESHOLD_MS", "250"))
    if p95 > p95_threshold:
        print(f"\n[FAIL] p95 latency ({p95:.1f}ms) exceeds {p95_threshold:.1f}ms threshold")
        environment.process_exit_code = 1
        return

    # Check failure rate
    if stats.total.fail_ratio > 0.01:
        print(f"\n[FAIL] Failure rate ({stats.total.fail_ratio * 100:.2f}%) exceeds 1% threshold")
        environment.process_exit_code = 1
        return

    print(f"\n[PASS] p95={p95:.1f}ms, failure_rate={stats.total.fail_ratio * 100:.2f}%")
    environment.process_exit_code = 0
