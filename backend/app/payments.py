"""Razorpay Standard Checkout API routes.

Payment status is verified cryptographically here. This milestone intentionally
does not persist candidate registrations or payment records to the database.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import uuid
from typing import Any, Callable

import razorpay
from fastapi import APIRouter, Body, HTTPException
from razorpay.errors import BadRequestError, GatewayError, ServerError

from app.config import Settings

logger = logging.getLogger("sutravya.payments")

_AUTH_FAILURE = re.compile(
    r"unauthori[sz]ed|authentication|invalid (?:api )?key|key_id|auth failure|"
    r"access denied",
    re.IGNORECASE,
)


def _credentials_ready(settings: Settings) -> bool:
    return bool(settings.razorpay_key_id and settings.razorpay_key_secret)


def _client(settings: Settings):
    if not _credentials_ready(settings):
        raise HTTPException(
            status_code=503,
            detail="Online payment is not configured. Please contact the event organiser.",
        )
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def _raise_gateway_error(exc: Exception) -> None:
    """Translate SDK failures without returning provider details or credentials."""
    if _AUTH_FAILURE.search(str(exc)):
        logger.warning("razorpay_authentication_failed", extra={"error_type": type(exc).__name__})
        raise HTTPException(
            status_code=401,
            detail="Payment service authentication failed. Please contact the event organiser.",
        ) from None
    logger.error("razorpay_api_request_failed", extra={"error_type": type(exc).__name__})
    raise HTTPException(
        status_code=500,
        detail="Unable to process the payment request. Please try again later.",
    ) from None


def create_payment_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["payments"])

    @router.post("/create-order")
    async def create_order(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Create an INR order using the server-configured registration fee."""
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="A JSON object is required.")

        required_fields = ("name", "email", "phone", "program")
        missing = [
            key for key in required_fields
            if not isinstance(payload.get(key), str) or not payload[key].strip()
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing)}.",
            )

        amount = settings.razorpay_registration_amount_paise
        if amount < 100:
            logger.error("razorpay_registration_amount_invalid")
            raise HTTPException(
                status_code=500,
                detail="The registration amount is not configured correctly.",
            )

        # A client may send amount for display compatibility, but may not choose it.
        requested_amount = payload.get("amount")
        if requested_amount is not None and (
            isinstance(requested_amount, bool)
            or not isinstance(requested_amount, int)
            or requested_amount != amount
        ):
            raise HTTPException(status_code=400, detail="The registration amount is invalid.")

        email = payload["email"].strip()
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise HTTPException(status_code=400, detail="Enter a valid email address.")

        name = payload["name"].strip()
        phone = payload["phone"].strip()
        program = payload["program"].strip()
        if len(name) > 100 or len(phone) > 20 or len(program) > 80:
            raise HTTPException(status_code=400, detail="One or more registration fields are too long.")

        client = _client(settings)
        order_request = {
            "amount": amount,
            "currency": "INR",
            "receipt": f"sv-{uuid.uuid4().hex[:24]}",
            "notes": {
                "candidate_name": name,
                "candidate_email": email,
                "candidate_phone": phone,
                "candidate_program": program,
            },
        }
        try:
            order = client.order.create(data=order_request)
        except (BadRequestError, GatewayError, ServerError) as exc:
            _raise_gateway_error(exc)
        except Exception as exc:  # network, timeout, or unexpected SDK transport errors
            _raise_gateway_error(exc)

        order_id = order.get("id") if isinstance(order, dict) else None
        if not isinstance(order_id, str) or not order_id:
            logger.error("razorpay_order_response_invalid")
            raise HTTPException(
                status_code=500,
                detail="The payment service returned an invalid order. Please try again.",
            )

        return {
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "key_id": settings.razorpay_key_id,
            "name": "Sutrāvya",
            "description": f"Assessment registration — {program}",
        }

    @router.post("/verify-payment")
    async def verify_payment(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Verify Razorpay's HMAC-SHA256 checkout signature."""
        required_fields = (
            "razorpay_order_id",
            "razorpay_payment_id",
            "razorpay_signature",
        )
        missing = [
            key for key in required_fields
            if not isinstance(payload.get(key), str) or not payload[key].strip()
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing)}.",
            )
        if not _credentials_ready(settings):
            raise HTTPException(
                status_code=503,
                detail="Online payment verification is not configured.",
            )

        order_id = payload["razorpay_order_id"].strip()
        payment_id = payload["razorpay_payment_id"].strip()
        supplied_signature = payload["razorpay_signature"].strip()
        message = f"{order_id}|{payment_id}".encode("utf-8")
        expected_signature = hmac.new(
            settings.razorpay_key_secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, supplied_signature):
            logger.warning("razorpay_signature_verification_failed")
            raise HTTPException(status_code=400, detail="Payment signature verification failed.")

        return {
            "success": True,
            "status": "verified",
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "message": (
                "Payment signature verified. This prototype does not yet save "
                "registration or payment records."
            ),
        }

    return router
