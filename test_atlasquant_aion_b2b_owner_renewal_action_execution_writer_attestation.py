from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_b2b_owner_renewal_action_execution_persistence_attestation import RECEIPT_SCHEMA
from atlasquant_aion_b2b_owner_renewal_action_execution_persistence_plan import NAMESPACE
from atlasquant_aion_b2b_owner_renewal_action_execution_writer_attestation import (
    build_owner_execution_writer_attestation_request,
    canonical_owner_execution_writer_bytes,
    verify_owner_execution_writer_attestation,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW="2026-10-05T22:50:30Z"
ISSUED="2026-10-05T22:50:00Z"
EXPIRES="2026-10-05T22:52:00Z"


def h(c): return "sha256:"+c*64
def b64url(raw): return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
def digest(v):
    raw=json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
    return "sha256:"+hashlib.sha256(raw).hexdigest()


def trust(status="ACTIVE"):
    private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    registry=TrustRootRegistry.from_mapping({
        "schema":"ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots":[{
            "key_id":"execution-intent-writer-key","key_version":1,
            "algorithm":"Ed25519","public_key_b64":b64url(public),
            "status":status,"not_before":"2026-10-05T20:00:00Z",
            "not_after":"2027-10-05T00:00:00Z",
        }],
        "revoked_key_ids":[],
    })
    return private,registry


def receipt(decision="AUTHORIZE_BUSINESS_ACTION_EXECUTION",**overrides):
    body={
        "schema":RECEIPT_SCHEMA,"status":"CONFIRMED",
        "storage_target":"CHECKPOINT_MASTER","write_mode":"EXPLICIT_AUTHORIZED_APPEND",
        "namespace":NAMESPACE,
        "event_id":"aion-b2b-owner-renewal-action-execution-0123456789abcdef0123456789abcdef",
        "base_revision":4,"revision":5,"patch_digest":h("1"),
        "before_checkpoint_digest":h("2"),"after_checkpoint_digest":h("3"),
        "execution_record_digest":h("4"),"customer_id":"customer-a",
        "pilot_id":"pilot-a","requested_choice":"RENEW_AS_IS_REVIEW",
        "action_family":"RENEWAL","execution_decision":decision,
        "persisted_at":"2026-10-05T22:49:30Z",
        "writer_ref":"checkpoint-writer:execution-intent",
        "writer_identity_verified":False,
        "execution_command_generated":False,"execution_command_executed":False,
        "business_action_authorized":False,"external_action_executed":False,
    }
    body.update(overrides)
    body["receipt_digest"]=digest({k:v for k,v in body.items() if k!="receipt_digest"})
    return body


def built(raw=None,**overrides):
    private,registry=trust(); raw=raw or receipt()
    args={
        "checkpoint_write_receipt":raw,"writer_trust_roots":registry,
        "now_ts":NOW,"ceremony_id":"execution-intent-writer-ceremony-001",
        "nonce":"execution-intent-writer-nonce-0001","issued_at":ISSUED,
        "expires_at":EXPIRES,"key_id":"execution-intent-writer-key","key_version":1,
    }
    args.update(overrides)
    out=build_owner_execution_writer_attestation_request(**args)
    return private,registry,out,raw


class OwnerExecutionWriterAttestationTests(unittest.TestCase):
    def test_receipt_builds_signature_request(self):
        _,_,out,raw=built()
        self.assertEqual(out["state"],"READY_FOR_EXTERNAL_EXECUTION_INTENT_WRITER_SIGNATURE")
        self.assertEqual(out["request"]["receipt_digest"],raw["receipt_digest"])
        self.assertFalse(out["execution_command_generated"])
        self.assertFalse(out["business_action_authorized"])

    def test_valid_signature_attests_writer_only(self):
        private,registry,out,raw=built()
        signature=b64url(private.sign(canonical_owner_execution_writer_bytes(out["request"])))
        with tempfile.TemporaryDirectory() as td:
            result=verify_owner_execution_writer_attestation(
                out["request"],writer_signature_b64=signature,
                checkpoint_write_receipt=raw,writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(Path(td)/"writer.sqlite3"),
                now_ts=NOW,
            )
        self.assertEqual(result["state"],"EXECUTION_INTENT_CHECKPOINT_WRITER_AUTHORITY_ATTESTED")
        self.assertTrue(result["writer_identity_verified"])
        self.assertTrue(result["writer_authority_verified"])
        self.assertTrue(result["receipt_binding_verified"])
        self.assertTrue(result["eligible_for_command_planning"])
        self.assertFalse(result["checkpoint_write_performed"])
        self.assertFalse(result["execution_command_generated"])
        self.assertFalse(result["business_action_authorized"])
        self.assertFalse(result["executes_action"])

    def test_deny_is_not_command_planning_eligible(self):
        raw=receipt("DENY_BUSINESS_ACTION_EXECUTION")
        private,registry,out,raw=built(raw)
        sig=b64url(private.sign(canonical_owner_execution_writer_bytes(out["request"])))
        with tempfile.TemporaryDirectory() as td:
            result=verify_owner_execution_writer_attestation(
                out["request"],writer_signature_b64=sig,checkpoint_write_receipt=raw,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(Path(td)/"writer.sqlite3"),now_ts=NOW,
            )
        self.assertFalse(result["eligible_for_command_planning"])

    def test_invalid_signature_blocks(self):
        _,registry,out,raw=built()
        other=Ed25519PrivateKey.generate()
        sig=b64url(other.sign(canonical_owner_execution_writer_bytes(out["request"])))
        with tempfile.TemporaryDirectory() as td:
            result=verify_owner_execution_writer_attestation(
                out["request"],writer_signature_b64=sig,checkpoint_write_receipt=raw,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(Path(td)/"writer.sqlite3"),now_ts=NOW,
            )
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("EXECUTION_WRITER_SIGNATURE_INVALID",result["blockers"])

    def test_receipt_mutation_blocks_rebuild(self):
        private,registry,out,raw=built()
        sig=b64url(private.sign(canonical_owner_execution_writer_bytes(out["request"])))
        changed=receipt(requested_choice="REPRICE_REVIEW")
        with tempfile.TemporaryDirectory() as td:
            result=verify_owner_execution_writer_attestation(
                out["request"],writer_signature_b64=sig,checkpoint_write_receipt=changed,
                writer_trust_roots=registry,
                nonce_registry=PersistentNonceRegistry(Path(td)/"writer.sqlite3"),now_ts=NOW,
            )
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("EXECUTION_WRITER_REQUEST_REBUILD_MISMATCH",result["blockers"])

    def test_replay_blocks(self):
        private,registry,out,raw=built()
        sig=b64url(private.sign(canonical_owner_execution_writer_bytes(out["request"])))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"writer.sqlite3"
            first=verify_owner_execution_writer_attestation(
                out["request"],writer_signature_b64=sig,checkpoint_write_receipt=raw,
                writer_trust_roots=registry,nonce_registry=PersistentNonceRegistry(path),now_ts=NOW,
            )
            second=verify_owner_execution_writer_attestation(
                out["request"],writer_signature_b64=sig,checkpoint_write_receipt=raw,
                writer_trust_roots=registry,nonce_registry=PersistentNonceRegistry(path),now_ts=NOW,
            )
        self.assertTrue(first["writer_authority_verified"])
        self.assertEqual(second["state"],"BLOCKED")
        self.assertIn("EXECUTION_WRITER_NONCE_REPLAYED",second["blockers"])

    def test_revoked_writer_key_blocks_request(self):
        _,registry=trust("REVOKED")
        out=build_owner_execution_writer_attestation_request(
            checkpoint_write_receipt=receipt(),writer_trust_roots=registry,now_ts=NOW,
            ceremony_id="execution-intent-writer-ceremony-001",
            nonce="execution-intent-writer-nonce-0001",issued_at=ISSUED,
            expires_at=EXPIRES,key_id="execution-intent-writer-key",key_version=1,
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertIn("WRITER_TRUST_KEY_REVOKED",out["blockers"])


if __name__=="__main__":
    unittest.main()
