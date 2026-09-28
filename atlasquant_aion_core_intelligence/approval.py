"""Human approval state contract; even APPROVED never authorizes execution."""
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol
from uuid import uuid4

from .context import Context
from .evidence import digest, timestamp, utc
from .store import CoreStore


class Action(str, Enum):
    PUBLICATION = "PUBLICATION"
    EXTERNAL_CHANGE = "EXTERNAL_CHANGE"
    PAYMENT = "PAYMENT"
    FINANCIAL_CHANGE = "FINANCIAL_CHANGE"
    DEPLOY = "DEPLOY"
    MARKET_OPERATION = "MARKET_OPERATION"
    MEMORY_DECISION = "MEMORY_DECISION"


class HumanApprovalAdapter(Protocol):
    def verify(self, *, context: Context, approval_id: str, subject_digest: str,
               action: str, decision: str, receipt: str) -> str | None:
        """Return authenticated human principal, or None. Never infer from intent.

        The host verifies its human session and binds the receipt to every
        supplied field. No permissive default adapter is provided here.
        """


class ApprovalGate:
    def __init__(self, store: CoreStore, human_adapter: HumanApprovalAdapter | None = None):
        self.store = store
        self.human_adapter = human_adapter

    def request(self, context: Context, action: Action, subject: dict,
                now: datetime, *, ttl_seconds: int = 3600) -> dict:
        if not isinstance(action, Action) or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 86400:
            raise ValueError("invalid approval request")
        row = {"approval_id": uuid4().hex, "version": 1, "action": action.value,
               "subject_digest": digest(subject), "scope_digest": digest(context.key),
               "state": "PENDING", "created_at": utc(now).isoformat(),
               "expires_at": (utc(now) + timedelta(seconds=ttl_seconds)).isoformat(),
               "human_principal": None, "decision_at": None, "consumed": False,
               "execution_authorized": False, "external_action_executed": False}
        self.store._save_approval(context, row, previous_version=None, now=now)
        return row

    def get(self, context: Context, approval_id: str, now: datetime) -> dict | None:
        row = self.store.approval(context, approval_id)
        if row and timestamp(row["expires_at"]) <= utc(now) and row["state"] in {"PENDING", "APPROVED"}:
            row["state"] = "EXPIRED"
        return row

    def decide(self, context: Context, approval_id: str, decision: str,
               receipt: str, now: datetime) -> dict:
        row = self.get(context, approval_id, now)
        if not row or row["state"] != "PENDING":
            raise ValueError("pending approval in this context required")
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("invalid human decision")
        if self.human_adapter is None:
            raise ValueError("HUMAN_APPROVAL_ADAPTER_UNAVAILABLE")
        principal = self.human_adapter.verify(context=context, approval_id=approval_id,
                    subject_digest=row["subject_digest"], action=row["action"],
                    decision=decision, receipt=receipt)
        if principal != context.actor_id:
            raise ValueError("authenticated human receipt required")
        previous = row["version"]
        row.update(state=decision, version=previous + 1,
                   human_principal=principal, decision_at=utc(now).isoformat())
        self.store._save_approval(context, row, previous_version=previous, now=now)
        return row
