"""Synthetic distinct host signing key and real persisted chat/journal fixtures.

Negative control: attacker may replace all public pins and host transcript,
valid Ed25519 math DOES NOT establish independent IdP or owner authority.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from unittest.mock import patch
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Reuse the exact earlier scoped real SQLite chat and prepared journal fixture;
# importing as a module prevents pytest from collecting its TestCase twice.
import test_atlasquant_aion_v2_persisted_chat_owner_one_shot_reference as fixture
from atlasquant_aion_v2_host_session_attested_preclaim_reference import (
    SCHEMA,ATTESTATION_SCHEMA,PURPOSE,ROLE,AUDIENCE,DOMAIN,
    MATCH,BURN,NO_GO,canonical_host_session_attestation,
    review_host_attested_persisted_preclaim_reference,
    consume_host_attested_persisted_local_reference_only,
)


class HostAttestedOneShotTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.PersistedSignedOneShotTests(
            methodName="test_stored_pending_session_signature_witness_match_math_only"
        )
        self.base.setUp()
        self.authority=Ed25519PrivateKey.generate()
        self.hostpin=fixture.pin(self.authority,"host-session-authority-fixture")
        self.challenge="9"*64
        self.now=1791565800
        self.issuer="aion-idp-fixture"
        self.host_payload=self.build_payload()
        self.host_envelope=self.sign()

    def tearDown(self):
        self.base.tearDown()

    def build_payload(self):
        b=self.base
        current=fixture.access()
        return {
            "schema":ATTESTATION_SCHEMA,"purpose":PURPOSE,"role":ROLE,
            "signer_key_id":self.hostpin["key_id"],
            "issuer_id":self.issuer,"audience":AUDIENCE,
            "owner_id":b.scope.owner_id,
            "tenant_id":b.scope.tenant_id,
            "workspace_id":b.scope.workspace_id,
            "username":current["session"]["username"],
            "host_role":"ADMIN",
            "credential_fingerprint_sha256":sha256(
                current["session"]["credential_fingerprint"].encode()
            ).hexdigest(),
            "permissions":["aion:admin","app:read"],
            "conversation_id":b.cid,
            "message_id":b.mid,
            "nonce_hex":b.intent["nonce_hex"],
            "signed_v2_intent_sha256":b.intent["signed_v2_intent_sha256"],
            "full_provider_request_sha256":b.intent["full_provider_request_sha256"],
            "session_epoch":3,
            "revocation_generation":5,
            "issued_at_unix":self.now-20,
            "auth_time_unix":self.now-50,
            "expires_at_unix":self.now+120,
            "challenge_nonce_hex":self.challenge,
        }

    def sign(self,payload=None,key=None):
        payload=deepcopy(self.host_payload if payload is None else payload)
        return {
            "payload":payload,
            "signature_hex":(key or self.authority).sign(
                canonical_host_session_attestation(payload)
            ).hex(),
        }

    def args(self,**kw):
        d=self.base.args()
        d.update({
            "host_envelope":self.host_envelope,
            "host_authority_pin":self.hostpin,
            "challenge_nonce_hex":self.challenge,
            "expected_issuer_id":self.issuer,
            "expected_session_epoch":3,
            "revocation_generation_floor":5,
            "now_unix":self.now,
        })
        d.update(kw)
        return d

    def check(self,result):
        self.assertEqual(result["schema"],SCHEMA)
        self.assertTrue(result["must_not_automatically_retry"])
        for name,val in NO_GO.items():
            self.assertIs(result[name],val,name)
        return result

    def review(self,**kw):
        return self.check(review_host_attested_persisted_preclaim_reference(
            **self.args(**kw)
        ))

    def consume(self,**kw):
        return self.check(consume_host_attested_persisted_local_reference_only(
            **self.args(**kw)
        ))

    def test_separate_ed25519_host_math_matches_real_scoped_pending_chat(self):
        self.assertEqual(self.review()["state"],MATCH)
        self.assertFalse(self.review()["real_idp_signature_verified"])
        self.assertFalse(self.review()["production_admission"])
        self.assertTrue(DOMAIN.endswith(b"\x00"))

    def test_signed_host_and_owner_witness_can_burn_one_local_nonce_only(self):
        self.assertEqual(self.consume()["state"],BURN)
        self.assertEqual(self.consume()["state"],"BLOCKED")
        self.assertEqual(self.review()["state"],"BLOCKED")
        self.assertFalse(self.review()["paid_dispatch_authorized"])

    def test_bad_host_signature_stops_before_local_nonce(self):
        v=deepcopy(self.host_envelope)
        v["signature_hex"]="0"*128
        self.assertEqual(self.consume(host_envelope=v)["reason"],
                         "HOST_SESSION_SIGNATURE_MATH_INVALID")
        self.assertEqual(self.review()["state"],MATCH)

    def test_attacker_substitutes_host_signer_and_pin_math_passes_not_idp(self):
        attacker=Ed25519PrivateKey.generate()
        fake=fixture.pin(attacker,self.hostpin["key_id"])
        result=self.review(
            host_envelope=self.sign(key=attacker),host_authority_pin=fake,
        )
        self.assertEqual(result["state"],MATCH)
        self.assertFalse(result["real_idp_signature_verified"])
        self.assertFalse(result["session_signing_root_enrolled"])

    def test_host_signer_cannot_reuse_owner_or_witness_pin(self):
        for bad in (
            self.base.pin_owner,
            self.base.pin_primary,
            self.base.pin_secondary,
        ):
            with self.subTest(pin=bad["key_id"]):
                self.assertEqual(self.consume(host_authority_pin=bad)["state"],
                                 "BLOCKED")
        self.assertEqual(self.review()["state"],MATCH)

    def test_signed_host_identity_session_and_scope_rebinding_is_blocked(self):
        changes={
            "owner_id":"other-owner",
            "tenant_id":"other-tenant",
            "workspace_id":"other-workspace",
            "username":"someone",
            "host_role":"VIEWER",
            "credential_fingerprint_sha256":"a"*64,
            "permissions":["app:read"],
            "conversation_id":"different-conversation",
            "message_id":"different-message",
            "nonce_hex":"b"*64,
            "signed_v2_intent_sha256":"c"*64,
            "full_provider_request_sha256":"d"*64,
            "issuer_id":"other-idp",
            "audience":"other-service",
            "purpose":"ALLOW_PAID_POST",
            "role":"HUMAN_OWNER_ED25519",
            "signer_key_id":"other-host",
            "challenge_nonce_hex":"e"*64,
        }
        for name,value in changes.items():
            with self.subTest(field=name):
                p=deepcopy(self.host_payload);p[name]=value
                self.assertEqual(self.consume(host_envelope=self.sign(p))[
                    "state"],"BLOCKED")
        self.assertEqual(self.review()["state"],MATCH)

    def test_host_session_cannot_override_actual_access(self):
        variants=(
            fixture.access(username="other"),
            fixture.access(role="VIEWER"),
            fixture.access(allowed=False),
            fixture.access(mode="ANONYMOUS"),
            {"allowed":True},
        )
        for v in variants:
            with self.subTest(access=repr(v)[:80]):
                self.assertEqual(self.consume(access=v)["state"],"BLOCKED")
        self.assertEqual(self.review()["state"],MATCH)

    def test_permissions_and_fingerprint_mutation_denied(self):
        altered=fixture.access()
        altered["session"]["permissions"]=["app:read","aion:admin","paid:dispatch"]
        self.assertEqual(self.consume(access=altered)["state"],"BLOCKED")
        altered=fixture.access()
        altered["session"]["credential_fingerprint"]="changed"
        self.assertEqual(self.consume(access=altered)["state"],"BLOCKED")
        self.assertEqual(self.review()["state"],MATCH)

    def test_expiry_not_yet_valid_and_auth_age_blocks(self):
        changes=(
            {"expires_at_unix":self.now},
            {"expires_at_unix":self.now-1},
            {"issued_at_unix":self.now+31},
            {"auth_time_unix":self.now+1},
            {"auth_time_unix":self.now-700},
            {"expires_at_unix":self.now+500},
            {"issued_at_unix":self.now-320},
            {"issued_at_unix":True},
            {"expires_at_unix":"later"},
        )
        for variant in changes:
            with self.subTest(variant=variant):
                p={**self.host_payload,**variant}
                self.assertEqual(self.consume(host_envelope=self.sign(p))[
                    "state"],"BLOCKED")

    def test_revocation_and_session_epoch_downgrade_blocks(self):
        self.assertEqual(self.consume(revocation_generation_floor=6)["state"],
                         "BLOCKED")
        self.assertEqual(self.consume(expected_session_epoch=4)["state"],
                         "BLOCKED")
        p=deepcopy(self.host_payload)
        p["revocation_generation"]=4
        self.assertEqual(self.consume(host_envelope=self.sign(p))["state"],
                         "BLOCKED")
        self.assertEqual(self.review()["state"],MATCH)

    def test_boolean_signed_epoch_is_rejected(self):
        p=deepcopy(self.host_payload)
        p['session_epoch']=True
        observed=self.consume(host_envelope=self.sign(p),expected_session_epoch=1)
        self.assertEqual(observed['state'],'BLOCKED')
        self.assertEqual(self.review()['state'],MATCH)

    def test_challenge_replay_with_changed_expected_nonce_blocks(self):
        self.assertEqual(self.consume(challenge_nonce_hex="8"*64)["state"],
                         "BLOCKED")
        self.assertEqual(self.consume(challenge_nonce_hex="0"*64)["state"],
                         "BLOCKED")
        # Deliberate limitation: same challenge accepted repeatedly by
        # mathematics until the local dispatch nonce is independently burned.
        self.assertEqual(self.review()["state"],MATCH)
        self.assertEqual(self.review()["state"],MATCH)
        self.assertFalse(self.review()["session_challenge_consumed"])

    def test_caller_controlled_clock_cannot_prove_actual_wall_time(self):
        self.assertEqual(self.review(now_unix=self.now)["state"],MATCH)
        self.assertFalse(self.review()["independent_clock_attested"])
        self.assertEqual(self.consume(now_unix=self.now+500)["state"],"BLOCKED")

    def test_session_host_signature_payload_extra_field_fails_closed(self):
        p={**self.host_payload,"paid_dispatch_authorized":True}
        with self.assertRaises(ValueError):
            canonical_host_session_attestation(p)
        forged=deepcopy(self.host_envelope)
        forged["payload"]=p
        self.assertEqual(self.consume(host_envelope=forged)["state"],"BLOCKED")

    def test_actual_pending_chat_altered_blocks_even_valid_session_signature(self):
        src=self.base.source
        self.base.store.db.execute(
            "UPDATE messages SET data=replace(data, ?, ?) WHERE id=?",
            (src,"conteúdo alterado",self.base.mid),
        )
        self.assertEqual(self.consume()["state"],"BLOCKED")
        self.assertEqual(
            self.base.journal.read_reference_only(
                nonce_hex=self.base.intent["nonce_hex"]
            )["stored_reference_state"],
            "PREPARED",
        )

    def test_owner_signature_or_secondary_witness_missing_blocks(self):
        corrupted=deepcopy(self.base.env)
        corrupted["signature_hex"]="0"*128
        self.assertEqual(self.consume(owner_envelope=corrupted)["state"],
                         "BLOCKED")
        heads=deepcopy(self.base.heads)
        heads["anchor_read"]=None
        self.assertEqual(self.consume(witness_heads=heads)["state"],"BLOCKED")

    def test_no_actual_network_even_when_all_math_and_local_burn_succeed(self):
        with patch("requests.sessions.Session.send",
                   side_effect=AssertionError("NO HTTP")), \
             patch("requests.post",side_effect=AssertionError("NO HTTP")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("NO MODEL")):
            self.assertEqual(self.consume()["state"],BURN)
        self.assertFalse(self.review()["provider_called"])

    def test_replay_old_signed_session_after_local_claim_rejected(self):
        self.assertEqual(self.consume()["state"],BURN)
        self.assertEqual(self.consume()["state"],"BLOCKED")
        self.assertFalse(self.review()["global_one_shot_guaranteed"])

    def test_fake_idp_host_session_is_a_negative_control_not_real_owner(self):
        self.assertEqual(self.review()["state"],MATCH)
        for flag in (
            "session_signature_is_independently_trusted",
            "session_revocation_list_checked",
            "session_crypto_key_isolation_verified",
            "real_owner_signature_enrollment_verified",
            "chat_store_is_remote_antirollback_protected",
            "cross_chat_journal_atomicity_verified",
            "external_dispatch_cas_performed","safe_to_resume"
        ):
            self.assertFalse(self.review()[flag],flag)


if __name__=="__main__":
    unittest.main()
