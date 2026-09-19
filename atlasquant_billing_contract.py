"""Provider-agnostic billing safety contract for AtlasQuant.

This module never charges a card, calls a payment network, stores card data,
activates subscriptions or changes user roles. It only validates the shape of
an already verified external billing event for future integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA="ATLASQUANT_BILLING_CONTRACT_V1"
ALLOWED_STATUSES=frozenset({"pending","active","past_due","cancelled","refunded"})

@dataclass(frozen=True)
class BillingEvent:
    event_id: str
    customer_ref: str
    subscription_ref: str
    status: str

    def validated(self)->"BillingEvent":
        event_id=str(self.event_id or "").strip()
        customer_ref=str(self.customer_ref or "").strip()
        subscription_ref=str(self.subscription_ref or "").strip()
        status=str(self.status or "").strip().casefold()
        if not event_id or not customer_ref or not subscription_ref:
            raise ValueError("referências de cobrança incompletas")
        if status not in ALLOWED_STATUSES:
            raise ValueError("status de cobrança não permitido")
        return BillingEvent(event_id,customer_ref,subscription_ref,status)

def evaluate_verified_billing_event(event:BillingEvent, *, signature_verified:bool=False)->dict[str,Any]:
    item=event.validated()
    verified=bool(signature_verified)
    return {
        "schema":SCHEMA,
        "event_id":item.event_id,
        "status":item.status,
        "signature_verified":verified,
        "accepted_for_review":verified,
        "automatic_entitlement":False,
        "automatic_role_change":False,
        "automatic_charge":False,
        "card_data_stored":False,
        "requires_human_review":True,
    }

def billing_contract_ready()->bool:
    return ALLOWED_STATUSES==frozenset({"pending","active","past_due","cancelled","refunded"})

__all__=["SCHEMA","ALLOWED_STATUSES","BillingEvent","evaluate_verified_billing_event","billing_contract_ready"]
