"""G138 test an off-host-ready *wire shape* using fake SAME-HOST signer.

14 cases run on real Python subprocesses with ephemeral keys generated in
test-only temporary directories. Signed data are CALLER-CONTROLLED. Green
tests do not establish provider truth, genuine owner identity, off-host
custody, root permanence, rollback-proof monotonic sequence or P0 closure.
"""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption,
)

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from labs.a190.g134_process_custody_lab import ADMITTED
from labs.a190.g135_pinned_original_claim_lab import PinnedOriginalClaimLab
from labs.a190.g137_native_stage_trigger_lab import (
    install_local_tripwire_lab, _record_local_permit,
)
from labs.a190.g138_signed_custody_wire_lab import (
    G138SignedCustodySessionLab, SCHEMA, STATUS, root_fingerprint_lab,
)
from labs.a190.test_g135_signed_original_to_actual_outbox_lab import (
    NOW, ORIGINAL, EFFECT, lab_keys, verifier_for, signer,
)


AUTHORITY = "synthetic-independent-custodian-NOT-REAL"
EPOCH = 1


class G138SignedCustodyWireAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g138-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.secret = self.root / "synthetic-private-key-lab-only"
        self.payload_path = self.root / "fixture-payload.json"
        self.signer_key = Ed25519PrivateKey.generate()
        self.seed = self.signer_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        self.secret.write_bytes(self.seed)
        self.public = self.signer_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.root_sha = root_fingerprint_lab(AUTHORITY, EPOCH, self.public)
        self.aion = self.root / "aion" / "actual-store.sqlite3"
        self.aion.parent.mkdir()
        self.custody = self.root / "same-host-separate-process" / "custody.sqlite3"
        self.custody.parent.mkdir()
        self.handles = []
        self.addCleanup(self._close_all)

    def _open_real_outbox(self):
        store = SQLiteChatStore(self.aion)
        self.handles.append(store)
        outbox = ExecutionOutbox(store, Scope(
            "synthetic-owner", "synthetic-tenant", "synthetic-workspace"))
        install_local_tripwire_lab(outbox)
        return store, outbox

    def _close_all(self):
        while self.handles:
            self.handles.pop().close()

    def _close(self, store):
        if store in self.handles:
            self.handles.remove(store)
            store.close()

    def _session(self, *, original=None, public=None, high=0, root=None):
        key = public if public is not None else self.public
        return G138SignedCustodySessionLab(
            original=deepcopy(original if original is not None else ORIGINAL),
            authority_id=AUTHORITY, authority_epoch=EPOCH,
            pinned_public_key=key,
            expected_root_sha256=(
                root if root is not None else root_fingerprint_lab(AUTHORITY, EPOCH, key)
            ),
            trusted_high_water=high, now=NOW,
        )

    def _body(self, session, *, original=None, **changes):
        body = {
            "schema": SCHEMA, "status": STATUS,
            "authority_id": AUTHORITY, "authority_epoch": EPOCH,
            "sequence": 1, "challenge": session.challenge(),
            "root_sha256": session._root,
            "issued_at": (NOW - timedelta(seconds=1)).isoformat(),
            "expires_at": (NOW + timedelta(seconds=20)).isoformat(),
            **deepcopy(original if original is not None else ORIGINAL),
        }
        return {**body, **changes}

    def _receipt(self, payload, *, seed_path=None):
        self.payload_path.write_text(json.dumps(
            payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
        process = subprocess.run(
            [sys.executable, "-B", "-m",
             "labs.a190.g138_fake_custodian_process_lab",
             str(seed_path if seed_path is not None else self.secret),
             str(self.payload_path)],
            check=True, capture_output=True, text=True, timeout=12)
        self.assertEqual(process.stderr, "")
        return json.loads(process.stdout)

    def _verify(self, session, *, original=None, **changes):
        return session.verify_once(self._receipt(
            self._body(session, original=original, **changes)))

    def test_01_valid_signed_same_host_process_receipt_grants_only_lab_staging(self):
        session = self._session()
        result = self._verify(session)
        self.assertEqual(result["original"], ORIGINAL)
        self.assertEqual(result["sequence"], 1)
        self.assertIs(result["permits_send"], False)
        self.assertIs(result["permits_retry"], False)
        self.assertIs(result["external_homologation"], False)
        print("G138_SEPARATE_PROCESS_ED25519_WIRE=VALID_SYNTHETIC_NOT_EXTERNAL")

    def test_02_altered_signature_denied(self):
        session = self._session()
        receipt = self._receipt(self._body(session))
        raw = bytearray(base64.b64decode(receipt["signature"]))
        raw[0] ^= 1
        receipt["signature"] = base64.b64encode(bytes(raw)).decode("ascii")
        self.assertIsNone(session.verify_once(receipt))

    def test_03_changed_original_economic_digest_denied(self):
        session = self._session()
        self.assertIsNone(self._verify(session, original_sha256="f" * 64))

    def test_04_changed_event_owner_or_tenant_denied(self):
        for changes in (
            {"event_id": "a-different-event"},
            {"owner_id": "fake-owner"},
            {"tenant_id": "other-tenant"},
            {"workspace_id": "other-workspace"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(self._verify(self._session(), **changes))

    def test_05_wrong_nonce_never_binds_challenge(self):
        session = self._session()
        self.assertIsNone(self._verify(session, challenge="f" * 64))

    def test_06_expired_or_future_time_denied(self):
        for changes in (
            {"issued_at": (NOW - timedelta(minutes=3)).isoformat(),
             "expires_at": (NOW - timedelta(minutes=2)).isoformat()},
            {"issued_at": (NOW + timedelta(minutes=2)).isoformat(),
             "expires_at": (NOW + timedelta(minutes=3)).isoformat()},
            {"issued_at": (NOW - timedelta(seconds=1)).isoformat(),
             "expires_at": (NOW + timedelta(minutes=2)).isoformat()},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(self._verify(self._session(), **changes))

    def test_07_forged_root_or_authority_epoch_denied(self):
        for changes in (
            {"root_sha256": "0" * 64},
            {"authority_epoch": EPOCH + 1},
            {"authority_id": "fake-authority"},
            {"status": "PROVIDER_DELIVERED_REAL_EFFECT"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(self._verify(self._session(), **changes))

    def test_08_one_shot_receipt_and_high_water_cannot_replay_within_intact_session(self):
        session = self._session()
        signed = self._receipt(self._body(session))
        self.assertIsNotNone(session.verify_once(signed))
        self.assertIsNone(session.verify_once(signed))
        with self.assertRaises(RuntimeError):
            session.challenge()
        self.assertIsNone(self._verify(self._session(high=1), sequence=1))

    def test_09_missing_receipt_consume_attempt_fail_closed(self):
        session = self._session()
        self._body(session)
        self.assertIsNone(session.verify_once(None))
        self.assertIsNone(session.verify_once({"fake": "later-ack"}))
        print("G138_ACK_LOST_OR_MISSING=UNCERTAIN_ZERO_AUTO_RESEND_LAB")

    def test_10_extra_fields_and_bad_base64_denied(self):
        session = self._session()
        receipt = self._receipt(self._body(session))
        receipt["payload"]["injected_authority_key"] = "evil"
        self.assertIsNone(session.verify_once(receipt))
        session2 = self._session()
        receipt2 = self._receipt(self._body(session2))
        receipt2["signature"] = "not@base64"
        self.assertIsNone(session2.verify_once(receipt2))

    def _prepare_g134_local_custody(self):
        p = subprocess.run([
            sys.executable, "-B", "-m",
            "labs.a190.g134_process_custody_lab",
            "bootstrap", str(self.custody),
        ], capture_output=True, text=True, timeout=12, check=True)
        self.assertEqual(p.stdout.strip(), "G134_EXPLICIT_LOCAL_FIXTURE_BOOTSTRAP")

    def _reserve_local(self, original):
        p = subprocess.run([
            sys.executable, "-B", "-m",
            "labs.a190.g134_process_custody_lab",
            "reserve", str(self.custody), original["tenant_id"],
            original["event_id"], original["original_sha256"], "g138-technical-request",
        ], capture_output=True, text=True, timeout=12, check=True)
        return p.stdout.strip()

    def _synthetic_stage_chain(self, outbox):
        self._prepare_g134_local_custody()
        keys, pins = lab_keys()
        owner_claim = PinnedOriginalClaimLab(
            original_event=deepcopy(ORIGINAL), economic_effect=deepcopy(EFFECT),
            identity_verifier=verifier_for(pins))
        retained = owner_claim.inspect(
            claimed_event=deepcopy(ORIGINAL),
            proposed_economic_effect=deepcopy(EFFECT),
            evidence_query=signer(keys, pins),
        )
        self.assertEqual(retained, ORIGINAL)
        session = self._session()
        proof = self._verify(session)
        self.assertEqual(proof["original"], retained)
        self.assertIs(proof["permits_send"], False)
        self.assertEqual(self._reserve_local(retained), ADMITTED)
        # This test-only permit can be SELF-MINTED by same-host caller.
        # The G137 trigger does not itself cryptographically verify wire proof.
        payload = {"business_event_id": retained["event_id"], **EFFECT}
        _record_local_permit(outbox.db, outbox.scope,
                             "g138-technical-request", EFFECT["action"],
                             retained["event_id"], payload)
        return outbox.enqueue(
            intent_ref="g138-technical-request",
            action=EFFECT["action"], payload=payload,
            semantic_event_id_lab=retained["event_id"],
            aggregate_key="g138-synthetic-no-real-effect",
            policy_version="G138-LAB-ONLY",
            authorization_ref="SYNTHETIC-CUSTODIAN-NOT-AUTHORITY",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5))

    def test_11_full_synthetic_chain_g135_g138_g134_g137_actual_outbox(self):
        store, outbox = self._open_real_outbox()
        item = self._synthetic_stage_chain(outbox)
        self.assertEqual(item["enqueue_state"], "ENQUEUED")
        self.assertEqual(len(outbox.list()), 1)
        with closing(sqlite3.connect(self.aion)) as db:
            rows = db.execute(
                "SELECT consumed FROM g137_local_stage_permits_lab"
            ).fetchall()
        self.assertEqual(rows, [(1,)])
        self._close(store)
        print("G138_SYNTHETIC_OWNER_CUSTODY_WIRE_LOCAL_SQLITE_TRIGGER_REAL_OUTBOX=STAGE_ONLY")

    def test_12_local_high_water_restore_allows_resigned_same_event_red(self):
        # Same caller can reset the "trusted" high-water to zero on restart.
        first = self._session(high=0)
        self.assertIsNotNone(self._verify(first))
        replay_after_local_restore = self._session(high=0)
        self.assertIsNotNone(self._verify(replay_after_local_restore))
        print("G138_LOCAL_MONOTONIC_FLOOR_RESTORE=REISSUED_FIRST_CLAIM_ACCEPTED_RED_NOT_P0")

    def test_13_attacker_replaces_original_and_root_can_self_repin_red(self):
        first = self._session()
        self.assertIsNotNone(self._verify(first))
        fake_original = {**ORIGINAL, "event_id": "fake-reenrolled-original-B"}
        attacker = Ed25519PrivateKey.generate()
        attacker_seed = attacker.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        attacker_path = self.root / "attacker-synthetic-seed"
        attacker_path.write_bytes(attacker_seed)
        attacker_public = attacker.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        another = self._session(original=fake_original, public=attacker_public)
        fake_signed = self._receipt(self._body(
            another, original=fake_original), seed_path=attacker_path)
        result = another.verify_once(fake_signed)
        self.assertEqual(result["original"], fake_original)
        print("G138_CALLER_REPLACES_ROOT_AND_ORIGINAL=FAKE_FIRST_PROOF_GREEN_RED_NOT_P0")

    def test_14_default_execution_outbox_adapter_never_sends(self):
        store, outbox = self._open_real_outbox()
        item = self._synthetic_stage_chain(outbox)
        self.assertIsNotNone(
            outbox.claim_next("synthetic-worker", now=NOW, lease_seconds=30))
        class NoSendAdapter:
            count = 0
            def send(self, *_args):
                self.count += 1
                raise AssertionError("G138_EXTERNAL_SEND_MUST_NOT_HAPPEN")
            def reconcile(self, *_args):
                raise AssertionError("G138_NO_RECONCILIATION")
        adapter = NoSendAdapter()
        def fake_policy(d):
            return {
                "allowed": True, "actor_id": outbox.scope.owner_id,
                "tenant_id": outbox.scope.tenant_id,
                "workspace_id": outbox.scope.workspace_id,
                "policy_version": d["policy_version"],
                "authorization_ref": d["authorization_ref"],
                "reauthenticated": True,
            }
        result = outbox.dispatch_claimed(
            item["idempotency_key"], worker_id="synthetic-worker",
            authorize=fake_policy, adapter=adapter,
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(adapter.count, 0)
        self._close(store)
        print("G138_DEFAULT_REAL_EXECUTION_OUTBOX=ZERO_PROVIDER_SEND")


if __name__ == "__main__":
    unittest.main()
