"""Shared synthetic G37 test fixtures; never dispatch or enable real providers."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from g37_signed_semantic_witness_lab import DOMAIN, issue_for_lab, subprocess_witness
from g37_real_outbox_authority_gate_lab import inspect_semantic_recovery

SCOPE = Scope("g37-owner", "g37-tenant", "g37-workspace")
NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
EVENT = "synthetic-business-event-42"


class AdapterTrap:
    def __init__(self):
        self.reads = 0

    @property
    def send(self):
        self.reads += 1
        raise AssertionError("G37_NO_PROVIDER_ACCESS")


class G37Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g37-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.store_path = self.base / "outbox.sqlite3"
        self.witness_dir = self.base / "witness"
        self.issuer = Ed25519PrivateKey.generate()
        self.issuer_public = self.issuer.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.store = SQLiteChatStore(self.store_path)
        self.addCleanup(lambda: self.store.close())
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        init = subprocess_witness(
            self.witness_dir, "init", {"authority_pin": self.issuer_public.hex()})
        self.custody_public = bytes.fromhex(init["custody_public_key"])
        self.adapter = AdapterTrap()

    def permit(self, *, event_id=EVENT, amount_minor=1000, scope=None,
               action="synthetic_no_provider", expiry=None):
        now = int(datetime.now(timezone.utc).timestamp())
        return {"domain": DOMAIN, "event_id": event_id,
                "scope": list(scope or [SCOPE.owner_id,SCOPE.tenant_id,SCOPE.workspace_id]),
                "action": action, "aggregate_key": "synthetic-invoice-batch",
                "amount_minor": amount_minor, "currency": "BRL",
                "expires_unix": now+600 if expiry is None else expiry}

    def certificate(self, **kwargs):
        return issue_for_lab(self.issuer, self.permit(**kwargs))

    def stage(self, *, request_ref="request-1", amount_minor=1000, event_id=EVENT):
        return self.outbox.enqueue(
            intent_ref=request_ref, action="synthetic_no_provider",
            payload={"business_event_id": event_id, "amount_minor": amount_minor,
                     "currency": "BRL"},
            aggregate_key="synthetic-invoice-batch",
            policy_version="p1", authorization_ref="a1",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5))

    def reserve(self, cert):
        return subprocess_witness(self.witness_dir, "reserve", {"certified": cert})

    def attest(self, cert, nonce):
        from g37_signed_semantic_witness_lab import event_key
        return subprocess_witness(self.witness_dir, "attest", {
            "event_key": event_key(cert["permit"]), "nonce": nonce.hex()})

    def admit(self, row, cert, *, nonce=None, proof=None, issuer_key=None,
              custody_key=None):
        ch = os.urandom(32) if nonce is None else nonce
        signed = self.attest(cert,ch) if proof is None else proof
        return inspect_semantic_recovery(
            outbox=self.outbox, idempotency_key=row["idempotency_key"],
            certified=cert, proof=signed, verifier_challenge=ch,
            pinned_custody_key=(self.custody_public if custody_key is None
                                else custody_key),
            pinned_issuer_key=(self.issuer_public if issuer_key is None
                               else issuer_key))

    def reopen(self):
        self.store.close()
        self.store = SQLiteChatStore(self.store_path)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def make_uncertain(self, row):
        claim = self.outbox.claim_next("g37-worker", now=NOW, lease_seconds=60)
        self.assertEqual(claim["idempotency_key"], row["idempotency_key"])
        result = self.outbox.dispatch_claimed(
            row["idempotency_key"], worker_id="g37-worker",
            authorize=lambda _: {"allowed": True, "actor_id": SCOPE.owner_id,
                                 "policy_version": "p1",
                                 "authorization_ref": "a1"},
            adapter=self.adapter, now=NOW+timedelta(seconds=1))
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(self.adapter.reads, 0)
        self.assertEqual(self.outbox.effect_count(),0)
        return result
