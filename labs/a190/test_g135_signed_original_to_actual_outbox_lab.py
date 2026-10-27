"""G135 — signed LAB original versus relabel, re-pin, and real AION Outbox.

No provider, external authority, trusted original enrollment, genuine customer,
Worker or SEND. All private keys generated fresh inside test processes.
"""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import base64
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from aion_chat.external_authority_a183_lab import (
    DOMAIN, ExternalAuthorityContractLab, root_fingerprint,
)
from aion_chat.models import Scope
from aion_chat.signed_receipt_lab import canonical_bytes
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a190.g134_process_custody_lab import ADMITTED, UNCERTAIN
from labs.a190.g135_pinned_original_claim_lab import PinnedOriginalClaimLab


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
EFFECT = {
    "action": "synthetic-no-real-send",
    "kind": "lab-economic-intent",
    "target": "synthetic-account-001",
    "amount_minor": "10000",
    "currency": "USD",
}
ORIGINAL = {
    "event_id": "original-economic-event-A",
    "original_sha256": sha256(canonical_bytes(EFFECT)).hexdigest(),
    "owner_id": "synthetic-owner",
    "tenant_id": "synthetic-tenant",
    "workspace_id": "synthetic-workspace",
}


def lab_keys():
    private = {role: Ed25519PrivateKey.generate() for role in
               ("owner", "identity_authority", "witness", "provider")}
    public = {}
    for role, sk in private.items():
        public[role] = {
            "issuer": "synthetic-" + role,
            "key_id": "lab-" + role + "-1",
            "public_key": sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
            "revoked": False,
        }
    return private, public


def verifier_for(pins):
    return ExternalAuthorityContractLab(
        pins=pins, expected_root_sha256=root_fingerprint(pins),
        authority_epoch=1, minimum_sequence=0, now=NOW,
    )


def signer(private, pins, *, missing_role=None, bad_challenge=False,
           expired=False, altered_role=None, altered_keys=None):
    """Fake laboratory issuer; caller controls every private key in this fixture."""
    def query(challenge, event, kind):
        assert kind == "IDENTITY"
        payload = {
            "schema": "A183_EXTERNAL_EVIDENCE_LAB_V1", "kind": kind,
            "challenge": "wrong-challenge" if bad_challenge else challenge,
            "authority_epoch": 1, "sequence": 1,
            "issued_at": (NOW - timedelta(minutes=5) if expired else NOW - timedelta(seconds=1)).isoformat(),
            "expires_at": (NOW - timedelta(minutes=4) if expired else NOW + timedelta(seconds=20)).isoformat(),
            "root_snapshot_sha256": root_fingerprint(pins),
            "status": "ATTESTED", **deepcopy(event),
        }
        message = DOMAIN + canonical_bytes(payload)
        signatures = {}
        for role in ("owner", "identity_authority"):
            if missing_role == role:
                continue
            key = altered_keys[role] if altered_role == role else private[role]
            signatures[role] = {
                "issuer": pins[role]["issuer"],
                "key_id": pins[role]["key_id"],
                "signature": base64.b64encode(key.sign(message)).decode("ascii"),
            }
        return {"payload": payload, "signatures": signatures}
    return query


class G135OriginalEconomicBindingTests(unittest.TestCase):
    def setUp(self):
        self.private, self.pins = lab_keys()
        self.manifest = deepcopy(ORIGINAL)
        self.economic = deepcopy(EFFECT)

    def bridge(self, *, manifest=None, effect=None, pins=None):
        return PinnedOriginalClaimLab(
            original_event=deepcopy(manifest if manifest is not None else self.manifest),
            economic_effect=deepcopy(effect if effect is not None else self.economic),
            identity_verifier=verifier_for(pins if pins is not None else self.pins),
        )

    def check(self, bridge, *, event=None, effect=None, query=None):
        return bridge.inspect(
            claimed_event=deepcopy(event if event is not None else self.manifest),
            proposed_economic_effect=deepcopy(effect if effect is not None else self.economic),
            evidence_query=query if query is not None else signer(self.private, self.pins),
        )

    def test_01_two_lab_signatures_match_retained_original_and_economic_digest(self):
        bridge = self.bridge()
        approved = self.check(bridge)
        self.assertEqual(approved, self.manifest)
        self.assertIsNot(approved, self.manifest)
        print("G135_PINNED_ORIGINAL_PLUS_TWO_SIGNATURES=LAB_STAGE_ONLY_NOT_SEND")

    def test_02_relabel_original_id_denied_even_with_valid_signed_document(self):
        forged = {**self.manifest, "event_id": "attacker-relabel-B"}
        self.assertIsNone(self.check(self.bridge(), event=forged))
        print("G135_RELABELED_EVENT_AGAINST_RETAINED_ORIGINAL=DENIED_LOCAL_LAB")

    def test_03_mutated_economic_beneficiary_or_amount_is_denied(self):
        for key, altered in (("target", "other-synthetic-account"),
                             ("amount_minor", "90000"),
                             ("currency", "EUR")):
            changed = {**self.economic, key: altered}
            with self.subTest(field=key):
                self.assertIsNone(self.check(self.bridge(), effect=changed))

    def test_04_replaced_signing_key_under_original_pins_fails(self):
        attacker_private, _ = lab_keys()
        query = signer(
            self.private, self.pins,
            altered_role="owner", altered_keys=attacker_private,
        )
        self.assertIsNone(self.check(self.bridge(), query=query))
        print("G135_ATTACKER_OWNER_SIGNATURE_WITH_OLD_PIN=DENIED")

    def test_05_missing_identity_authority_signature_fails(self):
        self.assertIsNone(self.check(
            self.bridge(), query=signer(self.private, self.pins,
                                        missing_role="identity_authority")
        ))

    def test_06_bad_challenge_or_expired_receipt_fails_closed(self):
        for kwargs in ({"bad_challenge": True}, {"expired": True}):
            with self.subTest(kwargs=kwargs):
                self.assertIsNone(self.check(
                    self.bridge(), query=signer(self.private, self.pins, **kwargs)))

    def test_07_callback_failure_and_duplicate_identity_attempt_deny(self):
        bridge = self.bridge()

        def raise_error(_challenge, _event, _kind):
            raise ValueError("synthetic issuer gone")

        self.assertIsNone(self.check(bridge, query=raise_error))
        self.assertEqual(self.check(bridge), self.manifest)
        self.assertIsNone(self.check(bridge))

    def test_08_retain_manifest_requires_exact_digest_and_valid_amount(self):
        with self.assertRaises(ValueError):
            self.bridge(manifest={**self.manifest, "original_sha256": "0" * 64})
        with self.assertRaises(ValueError):
            self.bridge(effect={**self.economic, "amount_minor": "000100"})
        with self.assertRaises(ValueError):
            self.bridge(effect={**self.economic, "amount_minor": "-100"})
        self.assertIsNone(self.check(
            self.bridge(), effect={**self.economic, "amount_minor": "9" * 5000}))

    def test_09_both_manifest_and_keys_replaced_still_self_enroll_red_not_p0(self):
        alternate_private, alternate_pins = lab_keys()
        same_effect_alternate_original = {**self.manifest, "event_id": "attacker-relabel-B"}
        # A fake attacker can substitute the local "retained" original AND local
        # key root. Both become apparently valid. This MUST remain an open P0.
        substituted = self.bridge(
            manifest=same_effect_alternate_original, pins=alternate_pins)
        evidence = signer(alternate_private, alternate_pins)
        admitted = self.check(
            substituted, event=same_effect_alternate_original, query=evidence)
        self.assertEqual(admitted, same_effect_alternate_original)
        print("G135_JOINT_ORIGINAL_AND_TRUST_ROOT_REPLACEMENT=SELF_REPIN_RED_NOT_P0")

    def test_10_retained_manifest_not_changed_by_caller_mutation(self):
        original = deepcopy(self.manifest)
        effect = deepcopy(self.economic)
        bridge = self.bridge(manifest=original, effect=effect)
        original["event_id"] = "replaced-after-construction"
        effect["amount_minor"] = "1"
        self.assertEqual(self.check(bridge), self.manifest)


class G135RealAionCustodyBindingLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a190-g135-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.chat_path = root / "aion" / "store.sqlite3"
        self.chat_path.parent.mkdir()
        self.custody_path = root / "other-local-process" / "witness.sqlite3"
        self.custody_path.parent.mkdir()
        self.baseline = root / "aion-before.sqlite3"
        self.scope = Scope("synthetic-owner", "synthetic-tenant", "synthetic-workspace")
        self.private, self.pins = lab_keys()
        self.stores = []
        self.addCleanup(self._close_all)
        self.assertEqual(self._process("bootstrap", self.custody_path),
                         "G134_EXPLICIT_LOCAL_FIXTURE_BOOTSTRAP")
        store, _ = self._open()
        self._close(store)
        with closing(sqlite3.connect(self.chat_path)) as src, closing(sqlite3.connect(self.baseline)) as dst:
            src.backup(dst)

    @staticmethod
    def _process(*args):
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "labs.a190.g134_process_custody_lab",
             *map(str, args)],
            capture_output=True, text=True, check=True, timeout=12)
        return completed.stdout.strip()

    def _open(self):
        store = SQLiteChatStore(self.chat_path)
        self.stores.append(store)
        outbox = ExecutionOutbox(store, self.scope)
        return store, outbox

    def _close(self, store):
        if store in self.stores:
            self.stores.remove(store)
            store.close()

    def _close_all(self):
        while self.stores:
            self.stores.pop().close()

    def _bridge(self, *, original=None, pins=None):
        return PinnedOriginalClaimLab(
            original_event=original if original is not None else ORIGINAL,
            economic_effect=EFFECT,
            identity_verifier=verifier_for(pins if pins is not None else self.pins),
        )

    def _stage(self, bridge, outbox, *, original=None, query=None, ref="request-A"):
        approved = bridge.inspect(
            claimed_event=original if original is not None else ORIGINAL,
            proposed_economic_effect=EFFECT,
            evidence_query=query if query is not None else signer(self.private, self.pins),
        )
        if approved is None:
            return "DENY_UNVERIFIED_ORIGINAL_NO_STAGE", None
        status = self._process(
            "reserve", self.custody_path, approved["tenant_id"],
            approved["event_id"], approved["original_sha256"], ref,
        )
        if status != ADMITTED:
            return status, None
        item = outbox.enqueue(
            intent_ref=ref, action=EFFECT["action"],
            payload={"business_event_id": approved["event_id"], **EFFECT},
            semantic_event_id_lab=approved["event_id"],
            aggregate_key="g135-no-real-effect",
            policy_version="LAB-ONLY",
            authorization_ref="SYNTHETIC_OWNER_AND_IDENTITY_LAB_NOT_AUTH",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )
        return status, item

    def _rollback_host(self):
        self.assertFalse(self.stores)
        for p in (self.chat_path, Path(str(self.chat_path) + "-wal"),
                  Path(str(self.chat_path) + "-shm")):
            p.unlink(missing_ok=True)
        shutil.copy2(self.baseline, self.chat_path)

    def test_11_real_outbox_stage_once_and_reject_technical_relabel_after_host_rollback(self):
        store, outbox = self._open()
        status, item = self._stage(self._bridge(), outbox)
        self.assertEqual(status, ADMITTED)
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self._close(store)
        self._rollback_host()
        store, outbox = self._open()
        status, second = self._stage(self._bridge(), outbox, ref="request-A-renamed")
        self.assertEqual(status, UNCERTAIN)
        self.assertIsNone(second)
        self.assertEqual(outbox.list(), [])
        self._close(store)
        print("G135_REAL_OUTBOX_HOST_ROLLBACK_WITH_PINNED_ORIGINAL=NO_RESTAGE_LOCAL_ONLY")

    def test_12_real_outbox_relabel_event_is_denied_before_local_reservation(self):
        store, outbox = self._open()
        forged = {**ORIGINAL, "event_id": "attacker-original-B"}
        status, item = self._stage(self._bridge(), outbox, original=forged)
        self.assertEqual(status, "DENY_UNVERIFIED_ORIGINAL_NO_STAGE")
        self.assertIsNone(item)
        self.assertEqual(outbox.list(), [])
        self._close(store)
        print("G135_FAKE_EVENT_RELABEL_BEFORE_CUSTODY=NO_AION_STAGE")

    def test_13_joint_local_repin_and_manifest_swap_allows_same_economic_effect_red(self):
        store, outbox = self._open()
        status, first = self._stage(self._bridge(), outbox)
        self.assertEqual(status, ADMITTED)
        altered_private, altered_pins = lab_keys()
        attacker_original = {**ORIGINAL, "event_id": "attacker-original-B"}
        status, second = self._stage(
            self._bridge(original=attacker_original, pins=altered_pins),
            outbox, original=attacker_original,
            query=signer(altered_private, altered_pins), ref="request-B",
        )
        self.assertEqual(status, ADMITTED)
        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(len(outbox.list()), 2)
        self._close(store)
        print("G135_JOINT_SELF_REPIN_AND_RELABEL=SECOND_SEMANTIC_STAGE_RED_NO_P0")

    def test_14_direct_real_outbox_enqueue_can_still_bypass_voluntary_bridge(self):
        store, outbox = self._open()
        item = outbox.enqueue(
            intent_ref="caller-direct-bypass",
            action=EFFECT["action"],
            payload={"business_event_id": "attacker-unverified-C", **EFFECT},
            semantic_event_id_lab="attacker-unverified-C",
            aggregate_key="g135-direct-local-stage-only",
            policy_version="LAB-ONLY",
            authorization_ref="NOT_AUTHENTICATED",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self.assertEqual(len(outbox.list()), 1)
        self._close(store)
        print("G135_VOLUNTARY_BRIDGE_CAN_BE_BYPASSED_BY_DIRECT_ENQUEUE_RED_NO_SEND")


if __name__ == "__main__":
    unittest.main()
