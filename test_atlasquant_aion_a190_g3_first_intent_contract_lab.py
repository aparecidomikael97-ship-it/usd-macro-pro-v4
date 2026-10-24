"""A190 G3 LAB: exercise *existing* A183 verifier + A189 real SQLite witness.

Every key, original event, tenant and receipt here is synthetic, and every
actor belongs to the same test process. No send, provider API, customer data,
production AION runtime, external trust root, or automatic retry is involved.
PASS means the specified counterexamples were reproduced, NOT that P0 is green.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.external_authority_a183_lab import (
    DOMAIN, REQUIRED, ExternalAuthorityContractLab, root_fingerprint,
)
from aion_chat.signed_receipt_lab import canonical_bytes
from labs.a189.local_witness_failclosed_lab import LocalWitnessLab


FIXTURE_NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
ROLES = ("owner", "identity_authority", "witness", "provider")
FIXTURE_INTENT = "LAB:ONLY:ZERO_EXTERNAL_EFFECT:original-economic-intent-001"
ORIGINAL_HASH = sha256(FIXTURE_INTENT.encode("utf-8")).hexdigest()


def synthetic_keys_and_pins(seed: int):
    """Four deterministic same-process Ed25519 keys; not independent issuers."""
    private = {
        role: Ed25519PrivateKey.from_private_bytes(bytes([seed + i]) * 32)
        for i, role in enumerate(ROLES)
    }
    pins = {}
    from cryptography.hazmat.primitives import serialization
    for role, key in private.items():
        pins[role] = {
            "issuer": "lab-fixture-" + role,
            "key_id": "lab-key-" + role,
            "public_key": key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ),
            "revoked": False,
        }
    return private, pins


def event(event_id: str):
    return {
        "event_id": event_id, "original_sha256": ORIGINAL_HASH,
        "owner_id": "SYNTHETIC_HUMAN_OWNER",
        "tenant_id": "synthetic-tenant", "workspace_id": "lab-only",
    }


def verifier_for(pins, *, pinned_root=None):
    return ExternalAuthorityContractLab(
        pins=pins,
        expected_root_sha256=pinned_root or root_fingerprint(pins),
        authority_epoch=3,
        minimum_sequence=0,
        now=FIXTURE_NOW,
    )


def signed_query(private, pins, *, sequence: int, mutate=None):
    root = root_fingerprint(pins)

    def query(challenge, requested_event, kind):
        body = dict(
            requested_event, schema="A183_EXTERNAL_EVIDENCE_LAB_V1",
            kind=kind, status="ATTESTED", challenge=challenge,
            authority_epoch=3, sequence=sequence,
            root_snapshot_sha256=root,
            issued_at=(FIXTURE_NOW - timedelta(seconds=1)).isoformat(),
            expires_at=(FIXTURE_NOW + timedelta(seconds=30)).isoformat(),
        )
        if mutate is not None:
            mutate(body)
        signatures = {}
        for role in REQUIRED[kind]:
            signature = private[role].sign(DOMAIN + canonical_bytes(body))
            signatures[role] = {
                "issuer": pins[role]["issuer"],
                "key_id": pins[role]["key_id"],
                "signature": base64.b64encode(signature).decode("ascii"),
            }
        return {"payload": body, "signatures": signatures}

    return query


class A190G3FirstIntentContractLabTests(unittest.TestCase):
    def setUp(self):
        self.private, self.pins = synthetic_keys_and_pins(41)
        self.tmp = tempfile.TemporaryDirectory(prefix="a190-g3-intent-")
        self.addCleanup(self.tmp.cleanup)
        self.ledger = LocalWitnessLab(Path(self.tmp.name))
        self.ledger.bootstrap_synthetic()

    def test_valid_synthetic_signature_and_same_claimed_event_locally_guarded(self):
        first = event("claimed-original-event-001")
        authority = verifier_for(self.pins)
        admitted = authority.admit(
            "RESERVATION", first,
            signed_query(self.private, self.pins, sequence=1),
        )
        self.assertIsNotNone(admitted)
        self.assertFalse(admitted["permits_send"])
        self.assertFalse(admitted["permits_retry"])
        self.assertFalse(admitted["external_homologation"])
        self.assertIsNone(authority.admit(
            "RESERVATION", first,
            signed_query(self.private, self.pins, sequence=2),
        ))
        self.assertEqual(
            self.ledger.reserve("request-001", first["event_id"], FIXTURE_INTENT)["status"],
            "RESERVED_LOCAL_ONLY",
        )
        self.assertEqual(
            self.ledger.reserve("request-002", first["event_id"], FIXTURE_INTENT)["status"],
            "DENIED_EVENT_ALREADY_RESERVED",
        )
        self.assertEqual(self.ledger.admission()["seq"], 1)
        print("A190_G3_SAME_CLAIMED_EVENT=DENIED_LOCAL_AND_VERIFIER_INSTANCE")

    def test_distinct_signed_event_ids_allow_same_semantic_original_twice_red(self):
        """The caller controls event_id; signatures alone prove no external origin."""
        first = event("claimed-original-event-001")
        second = event("attacker-relabelled-original-event-002")
        self.assertEqual(first["original_sha256"], second["original_sha256"])
        authority = verifier_for(self.pins)
        signed_first = authority.admit(
            "RESERVATION", first,
            signed_query(self.private, self.pins, sequence=1),
        )
        signed_second = authority.admit(
            "RESERVATION", second,
            signed_query(self.private, self.pins, sequence=2),
        )
        self.assertIsNotNone(signed_first)
        self.assertIsNotNone(signed_second)
        self.assertFalse(signed_first["permits_send"])
        self.assertFalse(signed_second["permits_send"])
        for request_id, claimed in (("request-001", first), ("request-002", second)):
            result = self.ledger.reserve(request_id, claimed["event_id"], FIXTURE_INTENT)
            self.assertEqual(result["status"], "RESERVED_LOCAL_ONLY")
            self.assertFalse(result["auto_resend"])
        self.assertEqual(self.ledger.admission()["seq"], 2)
        print("A190_G3_SIGNED_DIFFERENT_IDS_SAME_ORIGINAL=DOUBLE_LOCAL_RESERVATION_RED")

    def test_self_pinned_forged_issuer_can_mint_lab_receipt_red(self):
        """A key verified against *itself* is no independent trust root."""
        requested = event("attacker-claimed-original-event")
        fake_private, fake_pins = synthetic_keys_and_pins(81)
        trusted_root = root_fingerprint(self.pins)
        self.assertNotEqual(trusted_root, root_fingerprint(fake_pins))

        response = signed_query(fake_private, fake_pins, sequence=1)
        # Retaining the honest root *does* refuse the forged fixture.
        self.assertIsNone(verifier_for(self.pins, pinned_root=trusted_root).admit(
            "RECEIPT", requested, response,
        ))
        # A caller allowed to replace BOTH keys and expected root accepts it.
        self_pinned = verifier_for(fake_pins, pinned_root=root_fingerprint(fake_pins))
        forged = self_pinned.admit("RECEIPT", requested, response)
        self.assertIsNotNone(forged)
        self.assertTrue(forged["lab_verified"])
        self.assertFalse(forged["external_homologation"])
        self.assertFalse(forged["permits_send"])
        self.assertFalse(forged["permits_retry"])
        print("A190_G3_SELF_PINNED_FAKE_RECEIPT=LAB_VERIFIED_BUT_EXTERNAL_AUTHORITY_RED")

    def test_lost_ack_remains_uncertain_and_new_claim_still_bypasses_red(self):
        """No actual provider effect; this tests reservation/ACK states only."""
        first = event("claimed-original-event-001")
        lost = self.ledger.reserve(
            "request-001", first["event_id"], FIXTURE_INTENT,
            lose_ack_after_witness=True,
        )
        self.assertEqual(lost, {"status": "UNCERTAIN", "auto_resend": False})
        self.assertEqual(self.ledger.admission()["seq"], 1)
        self.assertEqual(
            self.ledger.reserve("request-001", first["event_id"], FIXTURE_INTENT)["status"],
            "ALREADY_RESERVED_LOCAL",
        )
        self.assertEqual(
            self.ledger.reserve("request-002", first["event_id"], FIXTURE_INTENT)["status"],
            "DENIED_EVENT_ALREADY_RESERVED",
        )
        new_claim = event("attacker-relabelled-original-event-002")
        still_risky = self.ledger.reserve(
            "request-003", new_claim["event_id"], FIXTURE_INTENT,
        )
        self.assertEqual(still_risky["status"], "RESERVED_LOCAL_ONLY")
        self.assertFalse(still_risky["auto_resend"])
        self.assertEqual(self.ledger.admission()["seq"], 2)
        print("A190_G3_ACK_LOSS=UNCERTAIN_ZERO_AUTO_RESEND")
        print("A190_G3_POST_ACK_LOSS_NEW_UNAUTHENTICATED_ID=DOUBLE_RESERVATION_RED")

    def test_missing_receipt_and_untrusted_callback_cannot_authorize_effect(self):
        """A183 returns evidence only, never an external send/confirm privilege."""
        requested = event("claimed-original-event-001")
        authority = verifier_for(self.pins)

        def lost(*_args):
            raise TimeoutError("synthetic unknown provider outcome")

        self.assertIsNone(authority.admit("RECEIPT", requested, lost))
        accepted = authority.admit(
            "RECEIPT", requested,
            signed_query(self.private, self.pins, sequence=1),
        )
        self.assertIsNotNone(accepted)
        self.assertFalse(accepted["permits_send"])
        self.assertFalse(accepted["permits_retry"])
        self.assertFalse(accepted["external_homologation"])
        print("A190_G3_MISSING_PROVIDER_RECEIPT=DENIED_NOT_SUCCESS")
        print("A190_G3_FIXTURE_RECEIPT=NEVER_PERMITS_REAL_EFFECT")

    def test_evidence_callback_not_safe_effect_boundary_red(self):
        """Counterexample: a callback may do work BEFORE verification refuses."""
        count = []
        requested = event("claimed-original-event-001")

        def hostile_query(_challenge, _event, _kind):
            count.append("only-in-memory-synthetic-side-effect")
            return {"payload": {}, "signatures": {}}

        self.assertIsNone(verifier_for(self.pins).admit(
            "RESERVATION", requested, hostile_query,
        ))
        self.assertEqual(count, ["only-in-memory-synthetic-side-effect"])
        print("A190_G3_UNTRUSTED_EVIDENCE_CALLBACK=SIDE_EFFECT_PRECEDES_DENIAL_RED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
