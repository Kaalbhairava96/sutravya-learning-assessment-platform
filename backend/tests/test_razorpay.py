from __future__ import annotations

import hashlib
import hmac
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from razorpay.errors import ServerError

from app.config import Settings
from app.main import create_app


TEST_SECRET = "razorpay-test-secret"


def make_settings(**overrides):
    values = {
        "app_env": "test",
        "log_level": "CRITICAL",
        "database_url": "postgresql+psycopg://user:pass@127.0.0.1:55432/sutravya_m3_test",
        "razorpay_key_id": "rzp_test_unit_key",
        "razorpay_key_secret": TEST_SECRET,
        "razorpay_registration_amount_paise": 50000,
    }
    values.update(overrides)
    return Settings(**values)


class RazorpayCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.settings = make_settings()
        self.client = TestClient(create_app(self.settings))
        self.candidate = {
            "name": "Test Candidate",
            "email": "candidate@example.invalid",
            "phone": "9876543210",
            "program": "B.Sc. Nursing",
        }

    def test_create_order_uses_server_configured_amount_and_returns_public_key(self):
        with patch("app.payments.razorpay.Client") as razorpay_client:
            razorpay_client.return_value.order.create.return_value = {"id": "order_test_123"}
            response = self.client.post("/api/create-order", json=self.candidate)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "order_id": "order_test_123",
                "amount": 50000,
                "currency": "INR",
                "key_id": "rzp_test_unit_key",
                "name": "Sutrāvya",
                "description": "Assessment registration — B.Sc. Nursing",
            },
        )
        sent_order = razorpay_client.return_value.order.create.call_args.kwargs["data"]
        self.assertEqual(sent_order["amount"], 50000)
        self.assertEqual(sent_order["currency"], "INR")
        self.assertTrue(sent_order["receipt"].startswith("sv-"))
        self.assertNotIn("notes", sent_order)

    def test_create_order_rejects_missing_registration_fields_with_400(self):
        response = self.client.post("/api/create-order", json={"name": "Candidate"})
        self.assertEqual(response.status_code, 400)

    def test_create_order_rejects_client_supplied_amount_tampering(self):
        response = self.client.post("/api/create-order", json={**self.candidate, "amount": 100})
        self.assertEqual(response.status_code, 400)

    def test_create_order_rejects_invalid_email(self):
        response = self.client.post(
            "/api/create-order",
            json={**self.candidate, "email": "not-an-email"},
        )
        self.assertEqual(response.status_code, 400)

    def test_create_order_returns_401_for_gateway_authentication_failure(self):
        with patch("app.payments.razorpay.Client") as razorpay_client:
            razorpay_client.return_value.order.create.side_effect = ServerError("Authentication failed")
            response = self.client.post("/api/create-order", json=self.candidate)
        self.assertEqual(response.status_code, 401)

    def test_create_order_returns_500_for_other_gateway_failures(self):
        with patch("app.payments.razorpay.Client") as razorpay_client:
            razorpay_client.return_value.order.create.side_effect = ServerError("Gateway unavailable")
            response = self.client.post("/api/create-order", json=self.candidate)
        self.assertEqual(response.status_code, 500)

    def test_create_order_rejects_configured_amount_below_minimum(self):
        client = TestClient(create_app(make_settings(razorpay_registration_amount_paise=99)))
        response = client.post("/api/create-order", json=self.candidate)
        self.assertEqual(response.status_code, 500)

    def test_create_order_requires_credentials(self):
        client = TestClient(create_app(make_settings(razorpay_key_id="", razorpay_key_secret="")))
        response = client.post("/api/create-order", json=self.candidate)
        self.assertEqual(response.status_code, 503)

    def test_verify_payment_accepts_valid_hmac_signature(self):
        order_id = "order_test_123"
        payment_id = "pay_test_456"
        signature = hmac.new(
            TEST_SECRET.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        response = self.client.post(
            "/api/verify-payment",
            json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["status"], "verified")

    def test_verify_payment_rejects_wrong_signature_and_does_not_succeed(self):
        response = self.client.post(
            "/api/verify-payment",
            json={
                "razorpay_order_id": "order_test_123",
                "razorpay_payment_id": "pay_test_456",
                "razorpay_signature": "not-a-valid-signature",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("success", response.json())

    def test_verify_payment_returns_400_for_missing_fields(self):
        response = self.client.post(
            "/api/verify-payment",
            json={"razorpay_order_id": "order_test_123"},
        )
        self.assertEqual(response.status_code, 400)

    def test_verify_payment_requires_server_secret(self):
        client = TestClient(create_app(make_settings(razorpay_key_secret="")))
        response = client.post(
            "/api/verify-payment",
            json={
                "razorpay_order_id": "order_test_123",
                "razorpay_payment_id": "pay_test_456",
                "razorpay_signature": "abcd",
            },
        )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
