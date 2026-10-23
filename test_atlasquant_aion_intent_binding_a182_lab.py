"""A182 synthetic adversarial LAB. No network/provider/real identity."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import unittest

from aion_chat.first_attempt_witness_lab import _effect_digest
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_execution_outbox import NOW, policy
from test_atlasquant_aion_first_attempt_witness_a180_lab import LabAdapter, fake_confirmed
import test_atlasquant_aion_separate_custody_a181_lab as a181
from test_atlasquant_aion_separate_custody_a181_lab import PRIVATE, ISSUER, KEY_ID, PAYLOAD
from test_atlasquant_aion_signed_receipt_a178_lab import public_bytes


class A182Fixture(unittest.TestCase):
    setUp = a181.A181SeparateCustodyRecoveryTests.setUp
    bootstrap = a181.A181SeparateCustodyRecoveryTests.bootstrap
    reopen_custody = a181.A181SeparateCustodyRecoveryTests.reopen_custody
    guard = a181.A181SeparateCustodyRecoveryTests.guard
    host = a181.A181SeparateCustodyRecoveryTests.host
    claim_and_send = a181.A181SeparateCustodyRecoveryTests.claim_and_send

    def original(self):
        store, out, row = self.host()
        store.close()
        return row

    def binding_guard(self, original, **kw):
        from aion_chat.intent_binding_a182_lab import BoundFirstAttemptWitnessLab, trust_fingerprint
        return BoundFirstAttemptWitnessLab(
            original_decision=original["decision"],
            issuer=ISSUER, key_id=KEY_ID, public_key=public_bytes(PRIVATE),
            reserve=kw.pop("reserve", self.custody.reserve),
            now=NOW+timedelta(seconds=2),
            expected_trust_sha256=kw.pop("expected_trust_sha256", trust_fingerprint(
                issuer=ISSUER,key_id=KEY_ID,public_key=public_bytes(PRIVATE))),
            minimum_sequence=kw.pop("minimum_sequence", 0),
            checkpoint=kw.pop("checkpoint", self.custody.snapshot), **kw)


class A182UnresolvedRiskTests(A182Fixture):
    """Passing assertions below demonstrate risk; they are NOT protections."""
    def test_altered_aggregate_same_adapter_effect_replayed_a181(self):
        store,out,row=self.host()
        self.assertEqual(self.claim_and_send(out,row)[1].send_calls,1)
        changed=out.enqueue(
            intent_ref="different-request", action="send_email", payload=PAYLOAD,
            aggregate_key="alias-for-same-account", policy_version="policy-v1",
            authorization_ref="approval-1", created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        self.assertNotEqual(_effect_digest(row["decision"]),_effect_digest(changed["decision"]))
        result,adapter=self.claim_and_send(out,changed)
        self.assertEqual(result["state"],"CONFIRMED")
        self.assertEqual(adapter.send_calls,1)
        store.close()
        print("A182_RISK_A181_CHANGED_AGGREGATE_SAME_ADAPTER_EFFECT=REPLAY")

    test_custody_rebootstrap_risk = a181.A181SeparateCustodyRecoveryTests.test_06_explicit_fresh_rebootstrap_after_wipe_is_bypass
    test_custody_rollback_risk = a181.A181SeparateCustodyRecoveryTests.test_07_restore_custody_snapshot_allows_duplicate_effect
    test_injected_guard_risk = a181.A181SeparateCustodyRecoveryTests.test_14_untrusted_true_callback_still_bypasses_witness


class A182ProtectionTests(A182Fixture):
    def test_valid_original_one_send_and_new_request_no_replay(self):
        original=self.original()
        store,out,row=self.host(guard=self.binding_guard(original))
        self.assertEqual(self.claim_and_send(out,row)[1].send_calls,1)
        store.close()
        self.host_db.unlink()
        store,out,row=self.host("new-request",guard=self.binding_guard(original))
        result,adapter=self.claim_and_send(out,row)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)
        self.assertIsNone(out.claim_next("later",now=NOW+timedelta(seconds=4)))
        store.close()
        print("A182_BOUND_ORIGINAL_NEW_REQUEST_HOST_LOSS=NO_REPLAY")

    def test_mutated_semantic_and_authority_fields_deny_before_reservation(self):
        original=self.original()
        fields={"owner_id":"fake-owner","tenant_id":"fake-tenant",
            "workspace_id":"fake-workspace","action":"other-action",
            "aggregate_key":"alias-same-account","policy_version":"policy-v2",
            "authorization_ref":"fake-approval","transaction_id":"fake-event",
            "authority_budget_ref":"fake-budget","risk_points":99,
            "capability_class":"fake-class","requires_reauth":True,
            "reauth_ref":"fake-reauth","grants_authority":True,
            "created_at":"2020-01-01T00:00:00+00:00",
            "valid_until":"2099-01-01T00:00:00+00:00","schema":"fake-schema"}
        guard=self.binding_guard(original)
        for field,value in fields.items():
            with self.subTest(field=field):
                altered=deepcopy(original)
                altered["decision"][field]=value
                self.assertIs(guard(altered),False)
        self.assertEqual(self.custody.snapshot()["count"],0)

    def test_payload_and_recomputed_digest_still_cannot_rebind(self):
        import json
        original=self.original()
        altered=deepcopy(original)
        altered["decision"]["payload"]["template"]="changed"
        altered["decision"]["payload_digest"]=sha256(json.dumps(
            altered["decision"]["payload"],sort_keys=True,ensure_ascii=False,
            separators=(",",":")).encode()).hexdigest()
        self.assertFalse(self.binding_guard(original)(altered))
        self.assertEqual(self.custody.snapshot()["count"],0)

    def test_dispatch_tampered_aggregate_stays_uncertain_zero_send(self):
        import json
        original=self.original()
        store,out,row=self.host(guard=self.binding_guard(original))
        decision=deepcopy(row["decision"])
        decision["aggregate_key"]="alias-for-same-effect"
        with out.db:
            out.db.execute("UPDATE action_decisions SET data=?",
                                     (json.dumps(decision),))
        result,adapter=self.claim_and_send(out,row)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)
        store.close()
        print("A182_ORIGINAL_BINDING_ALTERED_AGGREGATE=NO_SEND")

    def test_original_source_mutation_does_not_change_binding(self):
        original=self.original()
        guard=self.binding_guard(original)
        original["decision"]["aggregate_key"]="changed"
        self.assertFalse(guard(original))

    def test_json_key_order_is_canonical(self):
        original=self.original()
        altered=deepcopy(original)
        altered["decision"]["payload"]=dict(reversed(list(
            altered["decision"]["payload"].items())))
        self.assertTrue(self.binding_guard(original)(altered))

    def test_missing_original_and_inconsistent_payload_deny_enrollment(self):
        for field in ("payload","owner_id","authorization_ref"):
            original=self.original()
            del original["decision"][field]
            with self.assertRaises(ValueError):
                self.binding_guard(original)
        original=self.original()
        original["decision"]["payload_digest"]="0"*64
        with self.assertRaises(ValueError):
            self.binding_guard(original)

    def test_extra_candidate_field_is_not_ignored(self):
        original=self.original()
        altered=deepcopy(original)
        altered["decision"]["new_business_event_id"]="forged"
        self.assertFalse(self.binding_guard(original)(altered))

    def test_changed_root_fingerprint_denies_enrollment(self):
        with self.assertRaises(ValueError):
            self.binding_guard(self.original(),expected_trust_sha256="0"*64)

    def test_revoked_configuration_denies_even_if_fingerprint_matches(self):
        from aion_chat.intent_binding_a182_lab import trust_fingerprint
        original=self.original()
        guard=self.binding_guard(original,revoked=True,expected_trust_sha256=
            trust_fingerprint(issuer=ISSUER,key_id=KEY_ID,
                              public_key=public_bytes(PRIVATE),revoked=True))
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"],0)

    def test_missing_custody_and_ambiguous_checkpoint_deny(self):
        original=self.original()
        for value in (None, {}, {"high_water":True,"count":True},
                      {"high_water":1,"count":0}):
            self.assertFalse(self.binding_guard(original,checkpoint=lambda:value)(original))
        self.custody_db.unlink()
        self.assertFalse(self.binding_guard(original)(original))

    def test_retained_ordinal_rejects_restored_or_rebootstrapped_empty_custody(self):
        original=self.original()
        self.assertTrue(self.binding_guard(original)(original))
        self.custody_db.unlink()
        self.custody=self.bootstrap()
        self.assertFalse(self.binding_guard(original,minimum_sequence=1)(original))
        self.assertEqual(self.custody.snapshot()["count"],0)
        print("A182_RETAINED_ORDINAL_EMPTY_REBOOTSTRAP=DENIED_LOCAL_ONLY")

    def test_unverifiable_receipt_and_lost_reply_preserve_zero_send(self):
        original=self.original()
        def lost(challenge,request):
            self.custody.reserve(challenge,request)
            raise TimeoutError("synthetic lost response")
        store,out,row=self.host(guard=self.binding_guard(original,reserve=lost))
        result,adapter=self.claim_and_send(out,row)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)
        self.assertIsNone(out.claim_next("later",now=NOW+timedelta(seconds=4)))
        store.close()

    def test_malformed_signed_response_denied(self):
        original=self.original()
        self.assertFalse(self.binding_guard(original,reserve=lambda c,r:{"ok":True})(original))

    def test_same_guard_concurrency_one_reservation(self):
        from concurrent.futures import ThreadPoolExecutor
        original=self.original()
        guard=self.binding_guard(original)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:guard(deepcopy(original)),range(8)))
        self.assertEqual(sum(results),1)
        self.assertEqual(self.custody.snapshot()["count"],1)


class A182RemainingBoundaryTests(A182Fixture):
    """These PASS when the unresolved external guarantees are violated."""
    def test_restoring_both_custody_and_retained_ordinal_reopens(self):
        original=self.original()
        self.assertTrue(self.binding_guard(original)(original))
        self.custody_db.unlink()
        self.custody=self.bootstrap()
        self.assertTrue(self.binding_guard(original,minimum_sequence=0)(original))
        print("A182_RISK_ROLLBACK_CUSTODY_AND_CHECKPOINT=REPLAY")

    def test_replacing_original_binding_allows_redefined_effect(self):
        from aion_chat.intent_binding_a182_lab import semantic_bytes
        original=self.original()
        changed=deepcopy(original)
        changed["decision"]["aggregate_key"]="caller-redefined-account"
        self.assertNotEqual(semantic_bytes(original["decision"]),
                            semantic_bytes(changed["decision"]))
        self.assertTrue(self.binding_guard(changed)(changed))
        print("A182_RISK_REPLACE_ORIGINAL_ENROLLMENT=ACCEPTED")

    def test_replacing_root_and_expected_fingerprint_accepts_fake_authority(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from aion_chat.intent_binding_a182_lab import BoundFirstAttemptWitnessLab, trust_fingerprint
        original=self.original()
        private=Ed25519PrivateKey.from_private_bytes(b"\x21"*32)
        public=public_bytes(private)
        options=dict(original_decision=original["decision"],issuer=ISSUER,key_id=KEY_ID,
            public_key=public,reserve=self.custody.reserve,now=NOW+timedelta(seconds=2),
            minimum_sequence=0,checkpoint=lambda:{"high_water":0,"count":0})
        with self.assertRaises(ValueError):
            BoundFirstAttemptWitnessLab(**options,expected_trust_sha256=trust_fingerprint(
                issuer=ISSUER,key_id=KEY_ID,public_key=public_bytes(PRIVATE)))
        # Match signer envelope identities to the A181 fixture configuration.
        def forged(challenge,request):
            import base64
            from aion_chat.first_attempt_witness_lab import DOMAIN, SCHEMA
            from aion_chat.signed_receipt_lab import canonical_bytes
            payload=dict(request,schema=SCHEMA,status="RESERVED",issuer=ISSUER,
                key_id=KEY_ID,challenge=challenge,sequence=1,
                issued_at=NOW.isoformat(),expires_at=(NOW+timedelta(seconds=40)).isoformat())
            return {"payload":payload,"signature":base64.b64encode(
                private.sign(DOMAIN+canonical_bytes(payload))).decode("ascii")}
        options["reserve"]=forged
        guard=BoundFirstAttemptWitnessLab(**options,expected_trust_sha256=trust_fingerprint(
            issuer=ISSUER,key_id=KEY_ID,public_key=public))
        self.assertTrue(guard(original))
        print("A182_RISK_REPIN_ROOT_AND_FINGERPRINT=FAKE_AUTHORITY")


if __name__ == "__main__":
    unittest.main()

