"""Provider-neutral gateway contract. This implementation does not collect payments."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


class PaymentNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutOrder:
    provider: str
    order_id: str
    amount_paise: int
    currency: str
    checkout_url: str | None = None
    checkout_payload: dict | None = None


@dataclass(frozen=True)
class VerifiedPayment:
    provider: str
    order_id: str
    payment_reference: str
    amount_paise: int
    currency: str
    paid: bool


class PaymentGateway(Protocol):
    provider_name: str

    def create_order(self, *, amount_paise: int, currency: str, receipt: str,
                     customer_email: str, customer_name: str) -> CheckoutOrder: ...

    def verify_webhook(self, *, raw_body: bytes, headers: dict[str, str]) -> VerifiedPayment: ...


class DisabledPaymentGateway:
    provider_name = "disabled"

    def create_order(self, **_kwargs):
        raise PaymentNotConfigured("Secure checkout has not been configured by the organiser.")

    def verify_webhook(self, **_kwargs):
        raise PaymentNotConfigured("Payment webhook verification has not been configured.")


def get_payment_gateway() -> PaymentGateway:
    return DisabledPaymentGateway()
