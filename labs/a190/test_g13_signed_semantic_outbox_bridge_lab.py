"""A190 G13: adversarial bridge tests exercising the REAL SQLite Outbox.

All signatures, events, storage and adapter objects are synthetic laboratory
fixtures. Passing controls are evidence of local mechanics, NEVER P0 approval.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from g8_independent_authority_protocol_lab import (
    EVENT_DOMAIN, pub_bytes, seal, synthetic_event,
)
from g11_offline_conditional_cloud_adapter_contract_lab import (
    ContractDenied, dynamodb_envelopes, firestore_envelopes,
)
from g13_signed_semantic_outbox_bridge_lab import (
    semantic_operation_digest, stage_signed_semantic_lab,
)


NOW = datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc)


class TrapAdapter:
    def __init__(self):
        self.lookups = 0

    @property
    def send(self):
        self.lookups += 1
        raise AssertionError("LAB bridge must never access a send adapter")


class G13SignedSemanticRealOutboxBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="a190-g13-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "real-outbox.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.scope = Scope("synthetic-owner", "synthetic_tenant", "synthetic_workspace")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.issuer = Ed25519PrivateKey.generate()
        self.pin = pub_bytes(self.issuer)
        self.payload = {"synthetic": "effect-zero", "units": [1, 2]}
        self.action = "lab_no_real_effect"
        self.aggregate = "synthetic-account-1"

    def event(self, *, business_id="invoice-0001", ref="issuer-001",
              issuer=None, scope=None, action=None, payload=None, aggregate=None):
        issuer = self.issuer if issuer is None else issuer
        scope = self.scope if scope is None else scope
        digest = semantic_operation_digest(
            scope, business_event_id=business_id,
            action=self.action if action is None else action,
            payload=self.payload if payload is None else payload,
            aggregate_key=self.aggregate if aggregate is None else aggregate,
        )
        return synthetic_event(issuer, ref=ref, digest=digest)

    def stage(self, event, *, outbox=None, pin=None, request="caller-001",
              business_id="invoice-0001", action=None, payload=None, aggregate=None):
        return stage_signed_semantic_lab(
            self.outbox if outbox is None else outbox,
            signed_event=event,
            caller_pin=self.pin if pin is None else pin,
            claimed_request_ref=request, business_event_id=business_id,
            action=self.action if action is None else action,
            payload=self.payload if payload is None else payload,
            aggregate_key=self.aggregate if aggregate is None else aggregate,
            policy_version="synthetic-policy-1",
            authorization_ref="synthetic-approval-1",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def test_01_same_signed_event_different_request_ref_one_real_outbox_row(self):
        event = self.event()
        a = self.stage(event, request="first-request")
        b = self.stage(event, request="attacker-relabelled")
        self.assertEqual(a["enqueue_state"], "ENQUEUED")
        self.assertEqual(b["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(len(self.outbox.list()), 1)
        self.assertEqual(a["semantic_event_key"], b["semantic_event_key"])
        self.assertFalse(b["execution_allowed"])
        self.assertFalse(b["permits_send"])
        print("G13_G11_SIGNED_SEMANTIC_ALIASES=ONE_REAL_SQLITE_OUTBOX_INTENT")

    def test_02_original_event_ref_relabelled_with_same_signed_semantics(self):
        a = self.stage(self.event(ref="original-issuer"), request="first-request")
        b = self.stage(self.event(ref="another-issuer-label"), request="second-request")
        self.assertEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(a["native_semantic_reservation_id"], b["native_semantic_reservation_id"])
        self.assertEqual(len(self.outbox.list()), 1)
        print("G13_ORIGIN_REF_RELABEL=STABLE_OUTBOX_AND_CLOUD_NATIVE_ID")

    def test_03_signed_digest_cannot_be_reused_for_different_local_payload(self):
        event = self.event()
        self.stage(event)
        with self.assertRaisesRegex(ContractDenied, "NOT_BOUND_TO_ORIGIN"):
            self.stage(event, payload={"synthetic": "changed", "units": [1, 2]})
        self.assertEqual(len(self.outbox.list()), 1)
        print("G13_SAME_SIGNED_EVENT_DIFFERENT_PAYLOAD=DENIED")

    def test_04_signed_digest_cannot_be_reused_for_different_action(self):
        event = self.event()
        with self.assertRaisesRegex(ContractDenied, "NOT_BOUND_TO_ORIGIN"):
            self.stage(event, action="different_lab_action")
        self.assertEqual(len(self.outbox.list()), 0)

    def test_05_valid_but_foreign_signed_tenant_denied(self):
        event = self.event()
        tampered = deepcopy(event["payload"])
        tampered["tenant"] = "not_my_tenant"
        foreign = seal(self.issuer, EVENT_DOMAIN, tampered)
        with self.assertRaisesRegex(ContractDenied, "TENANT_SCOPE_MISMATCH"):
            self.stage(foreign)
        self.assertEqual(len(self.outbox.list()), 0)
        print("G13_AUTHENTIC_BUT_FOREIGN_TENANT=DENIED")

    def test_06_wrong_pinned_issuer_and_tampered_digest_denied(self):
        event = self.event()
        other = Ed25519PrivateKey.generate()
        with self.assertRaises(ContractDenied):
            self.stage(event, pin=pub_bytes(other))
        corrupted = deepcopy(event)
        corrupted["payload"]["semantic_digest"] = "0" * 64
        with self.assertRaises(ContractDenied):
            self.stage(corrupted)
        self.assertEqual(len(self.outbox.list()), 0)
        print("G13_WRONG_PIN_OR_MUTATED_SIGNATURE=NO_INTENT")

    def test_07_distinct_synthetic_business_events_can_stage_separately(self):
        first = self.stage(self.event(business_id="invoice-0001"))
        second = self.stage(
            self.event(business_id="invoice-0002"),
            business_id="invoice-0002", request="second-real-business-event",
        )
        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(len(self.outbox.list()), 2)
        self.assertEqual(self.outbox.effect_count(), 0)
        print("G13_DISTINCT_SIGNED_BUSINESS_EVENTS=SEPARATE_STAGED_INTENTS")

    def test_08_signed_event_expiration_denies_stage(self):
        digest = semantic_operation_digest(
            self.scope, business_event_id="invoice-0001", action=self.action,
            aggregate_key=self.aggregate, payload=self.payload,
        )
        old = synthetic_event(self.issuer, digest=digest, now=1)
        with self.assertRaises(ContractDenied):
            self.stage(old)
        self.assertEqual(len(self.outbox.list()), 0)

    def test_09_invalid_caller_alias_denied_before_insert(self):
        with self.assertRaisesRegex(ContractDenied, "INVALID_CLAIMED_REQUEST_REF"):
            self.stage(self.event(), request="../unsafe path")
        self.assertEqual(len(self.outbox.list()), 0)

    def test_10_g12_default_outbox_quarantine_survives_signed_stage(self):
        safe_outbox = ExecutionOutbox(
            self.store, self.scope,
            first_attempt_guard=lambda _: True,
            evidence_verifier=lambda *_: True,
        )
        item = self.stage(self.event(), outbox=safe_outbox)
        claim = safe_outbox.claim_next("synthetic-worker", now=NOW, lease_seconds=60)
        self.assertEqual(claim["idempotency_key"], item["idempotency_key"])
        adapter = TrapAdapter()
        decision = item["decision"]
        result = safe_outbox.dispatch_claimed(
            item["idempotency_key"],
            worker_id="synthetic-worker",
            authorize=lambda _: {
                "allowed": True,
                "actor_id": self.scope.owner_id,
                "tenant_id": self.scope.tenant_id,
                "workspace_id": self.scope.workspace_id,
                "policy_version": decision["policy_version"],
                "authorization_ref": decision["authorization_ref"],
            },
            adapter=adapter,
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(adapter.lookups, 0)
        self.assertEqual(safe_outbox.effect_count(), 0)
        print("G13_SIGNED_LOCAL_STAGING=NO_SEND_NO_CONFIRM_UNCERTAIN")

    def test_11_unsafe_callback_opt_in_is_not_allowed_by_bridge(self):
        unsafe = ExecutionOutbox(
            self.store, self.scope,
            first_attempt_guard=lambda _: True,
            unsafe_allow_synthetic_lab_callbacks=True,
        )
        with self.assertRaisesRegex(ContractDenied, "UNSAFE_LAB_OUTBOX"):
            self.stage(self.event(), outbox=unsafe)
        self.assertEqual(len(self.outbox.list()), 0)

    def test_12_signed_native_cloud_envelopes_same_key_but_zero_authority(self):
        event = self.event()
        staged = self.stage(event)
        ddb = dynamodb_envelopes(event, self.pin, "cloud-req-1")
        fs = firestore_envelopes(event, self.pin, "cloud-req-2")
        self.assertEqual(staged["native_semantic_reservation_id"], ddb["native_id"])
        self.assertEqual(ddb["native_id"], fs["native_id"])
        self.assertFalse(ddb["execution_allowed"])
        self.assertFalse(fs["execution_allowed"])
        self.assertFalse(staged["execution_allowed"])
        print("G13_REAL_OUTBOX_AND_OFFLINE_NATIVE_DB_SHARE_KEY=NO_AUTHORITY")

    def test_13_same_signed_tenant_different_workspace_replays_locally_red(self):
        event = self.event()
        first = self.stage(event)
        other_scope = Scope(
            "synthetic-owner", "synthetic_tenant", "different-workspace",
        )
        other_outbox = ExecutionOutbox(self.store, other_scope)
        second = self.stage(event, outbox=other_outbox, request="workspace-relabelled")
        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(first["native_semantic_reservation_id"],
                         second["native_semantic_reservation_id"])
        self.assertEqual(len(self.outbox.list()), 1)
        self.assertEqual(len(other_outbox.list()), 1)
        print("G13_CROSS_WORKSPACE_SAME_EVENT=LOCAL_DOUBLE_STAGE_RED_EXTERNAL_ROOT_NEEDED")

    def test_14_caller_self_pins_new_semantics_can_duplicate_meaning_red(self):
        first = self.stage(self.event())
        hostile = Ed25519PrivateKey.generate()
        hostile_pin = pub_bytes(hostile)
        alternate = self.event(
            business_id="attacker-invented-alias",
            issuer=hostile, ref="hostile-signature-ref",
        )
        second = self.stage(
            alternate, pin=hostile_pin, business_id="attacker-invented-alias",
            request="self-pinned-alias",
        )
        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(len(self.outbox.list()), 2)
        self.assertFalse(second["external_root_verified"])
        print("G13_CALLER_CONTROLS_PIN_AND_BUSINESS_EVENT=DOUBLE_STAGE_RED")

    def test_15_deleted_local_outbox_allows_same_event_rebootstrap_red(self):
        event = self.event()
        first = self.stage(event)
        self.store.close()
        self.path.unlink()  # disposable tempfile fixture ONLY
        reopened = SQLiteChatStore(self.path)
        self.addCleanup(reopened.close)
        empty_outbox = ExecutionOutbox(reopened, self.scope)
        again = self.stage(event, outbox=empty_outbox, request="after-local-erase")
        self.assertEqual(first["idempotency_key"], again["idempotency_key"])
        self.assertEqual(again["enqueue_state"], "ENQUEUED")
        self.assertEqual(empty_outbox.effect_count(), 0)
        print("G13_LOCAL_SQLITE_ERASE=REOPEN_SAME_EVENT_RED_EXTERNAL_CUSTODY_MISSING")


if __name__ == "__main__":
    unittest.main()
