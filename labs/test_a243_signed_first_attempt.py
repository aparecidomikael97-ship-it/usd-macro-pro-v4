"""A243: synthetic Ed25519 first-attempt witness and known counterexamples."""
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a243_signed_first_attempt import (
    DOMAIN, SCHEMA, PinnedFirstAttemptWitnessLab, canonical_bytes,
)


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
SCOPE = Scope("owner-a243", "tenant-a243", "workspace-a243")
GOOD = Ed25519PrivateKey.from_private_bytes(b"\x13" * 32)
ATTACKER = Ed25519PrivateKey.from_private_bytes(b"\x14" * 32)
ISSUER = "synthetic-a243-issuer"
KEY_ID = "synthetic-a243-key"


def _public(private):
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


class SyntheticServer:
    """In-memory, rollbackable witness. Never an independent root."""
    def __init__(self, signer=GOOD):
        self.signer = signer
        self.reserved = set()
        self.seq = 0
        self.offline = False
        self.lost = False
        self.replay = False
        self.last = None
        self.tamper = {}
        self.bad_signature = None
        self.calls = 0

    def __call__(self, challenge, request):
        self.calls += 1
        if self.offline:
            raise OSError("synthetic witness offline")
        if self.replay and self.last is not None:
            return self.last
        effect = request["effect_digest"]
        if effect in self.reserved:
            return {"status": "ALREADY_RESERVED"}
        self.reserved.add(effect)
        self.seq += 1
        if self.lost:
            raise TimeoutError("reservation persisted; ACK lost")
        payload = {
            "schema": SCHEMA, "status": "RESERVED",
            "issuer": ISSUER, "key_id": KEY_ID,
            "challenge": challenge, "sequence": self.seq,
            "issued_at": NOW.isoformat(),
            "expires_at": (NOW + timedelta(seconds=40)).isoformat(),
            **request,
        }
        payload.update(self.tamper)
        signature = base64.b64encode(
            self.signer.sign(DOMAIN + canonical_bytes(payload))
        ).decode("ascii")
        if self.bad_signature is not None:
            signature = self.bad_signature
        self.last = {"payload": payload, "signature": signature}
        return self.last


class Adapter:
    def __init__(self):
        self.calls = 0

    def send(self, decision, key):
        self.calls += 1
        return {"accepted": True, "confirmed": False, "effect_ref": "lab-only"}


def _authorize(decision):
    return {
        "allowed": True, "actor_id": SCOPE.owner_id,
        "tenant_id": SCOPE.tenant_id, "workspace_id": SCOPE.workspace_id,
        "policy_version": decision["policy_version"],
        "authorization_ref": decision["authorization_ref"],
    }


def _guard(server, public=None, **options):
    return PinnedFirstAttemptWitnessLab(
        issuer=ISSUER, key_id=KEY_ID, public_key=public or _public(GOOD),
        reserve=server, now=NOW, **options,
    )


def _attempt(guard, *, intent_ref="request-a", payload=None):
    with TemporaryDirectory(prefix="a243-") as raw:
        store = SQLiteChatStore(Path(raw) / "outbox.db")
        outbox = ExecutionOutbox(store, SCOPE, first_attempt_guard=guard)
        adapter = Adapter()
        try:
            item = outbox.enqueue(
                intent_ref=intent_ref, action="synthetic-effect",
                payload=payload or {"same_business_event": "A"},
                aggregate_key="client-a", policy_version="policy-a243",
                authorization_ref="synthetic-approval",
                created_at=NOW, valid_until=NOW + timedelta(minutes=5),
            )
            key = item["idempotency_key"]
            outbox.claim_next("worker-a243", now=NOW, lease_seconds=60)
            result = outbox.dispatch_claimed(
                key, worker_id="worker-a243", authorize=_authorize,
                adapter=adapter, now=NOW,
            )
            return result, adapter.calls, outbox.effect_count()
        finally:
            store.close()


class A243SyntheticSignedFirstAttemptTests(unittest.TestCase):
    def test_01_correct_signed_reservation_allows_one_synthetic_send(self):
        result, sends, effects = _attempt(_guard(SyntheticServer()))
        self.assertEqual(result["state"], "SENT")
        self.assertEqual(sends, 1)
        self.assertEqual(effects, 0)

    def test_02_wrong_signer_denied(self):
        result, sends, effects = _attempt(_guard(SyntheticServer(signer=ATTACKER)))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_03_wrong_issuer_denied(self):
        server = SyntheticServer()
        server.tamper["issuer"] = "untrusted"
        result, sends, _ = _attempt(_guard(server))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_04_wrong_scope_denied(self):
        server = SyntheticServer()
        server.tamper["tenant_id"] = "wrong-tenant"
        result, sends, _ = _attempt(_guard(server))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_05_altered_decision_digest_denied(self):
        server = SyntheticServer()
        server.tamper["decision_sha256"] = "0" * 64
        result, sends, _ = _attempt(_guard(server))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_06_challenge_replaced_denied(self):
        server = SyntheticServer()
        server.tamper["challenge"] = "f" * 64
        result, sends, _ = _attempt(_guard(server))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_07_expired_signature_denied(self):
        server = SyntheticServer()
        server.tamper["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
        result, sends, _ = _attempt(_guard(server))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_08_bool_sequence_denied(self):
        server = SyntheticServer()
        server.tamper["sequence"] = True
        result, sends, _ = _attempt(_guard(server))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_09_revoked_root_denied(self):
        result, sends, _ = _attempt(_guard(SyntheticServer(), revoked=True))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_10_lost_reservation_ack_never_calls_adapter(self):
        server = SyntheticServer()
        server.lost = True
        result, sends, _ = _attempt(_guard(server))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))
        self.assertEqual(len(server.reserved), 1)

    def test_11_stale_signed_envelope_replay_denied(self):
        server = SyntheticServer()
        first, sends, _ = _attempt(_guard(server), intent_ref="request-a")
        self.assertEqual((first["state"], sends), ("SENT", 1))
        server.replay = True
        second, sends, _ = _attempt(_guard(server), intent_ref="request-b")
        self.assertEqual((second["state"], sends), ("UNCERTAIN", 0))

    def test_12_malformed_base64_denied(self):
        server = SyntheticServer()
        server.bad_signature = "***not-base64***"
        result, sends, _ = _attempt(_guard(server))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    def test_13_high_water_rejects_stale_signed_sequence(self):
        server = SyntheticServer()
        result, sends, _ = _attempt(_guard(server, high_water=1))
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    @unittest.expectedFailure
    def test_14_restored_witness_state_repermits_same_semantic_effect_red_property(self):
        server = SyntheticServer()
        first, sends1, _ = _attempt(_guard(server), intent_ref="request-a")
        self.assertEqual((first["state"], sends1), ("SENT", 1))
        # Roll back both witness's remembered effects and sequence to old state.
        server.reserved.clear()
        server.seq = 0
        second, sends2, _ = _attempt(_guard(server, high_water=0), intent_ref="request-b")
        # Desired security invariant: rollback must NOT allow a second send.
        # Current code violates this; unittest reports an expected failure.
        self.assertEqual((second["state"], sends2), ("UNCERTAIN", 0))

    @unittest.expectedFailure
    def test_15_caller_repins_attacker_root_fake_proof_still_passes(self):
        attacker_server = SyntheticServer(signer=ATTACKER)
        result, sends, _ = _attempt(_guard(attacker_server, public=_public(ATTACKER)))
        # Desired security invariant: a host-pinned attacker key cannot authorize send.
        # Current code violates this; external root provenance remains missing.
        self.assertEqual((result["state"], sends), ("UNCERTAIN", 0))

    @unittest.expectedFailure
    def test_16_same_semantic_payload_blocks_distinct_legitimate_event(self):
        server = SyntheticServer()
        first, sends1, _ = _attempt(_guard(server), intent_ref="legitimate-a")
        second, sends2, _ = _attempt(_guard(server), intent_ref="legitimate-b")
        self.assertEqual((first["state"], sends1), ("SENT", 1))
        # Desired semantic invariant: distinct authentic events should not collide.
        # Current heuristic wrongly blocks event B; an authoritative event ID is absent.
        self.assertEqual((second["state"], sends2), ("SENT", 1))
