"""50 offline negative tests for a caller-supplied evidence bundle. Never trust."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_p0_external_evidence_admission_lab import (
    REQUEST_FIELDS, BUNDLE_FIELDS, CLAIM_FIELDS, APPROVAL_GAPS,
    inspect_external_evidence_claims_lab as inspect,
)
from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS


class P0EvidenceAdmissionLAB(unittest.TestCase):
    def setUp(self):
        self.req = {
            "scope": "repo.tenant.alpha", "request_id": "request-001",
            "intent_id": "intent-001", "key_id": "key-001",
            "credential_epoch": 7, "epoch": 10, "sequence": 45,
            "head_digest": "a" * 64, "nonce": "nonce-001",
        }
        self.bundle = {
            "issuer": {
                "key_id": "key-001", "scope": "repo.tenant.alpha",
                "public_key_sha256": "b" * 64,
                "algorithm": "ED25519_SHA_512", "status": "ACTIVE",
            },
            "head": {
                "scope": "repo.tenant.alpha", "epoch": 10, "sequence": 45,
                "head_digest": "a" * 64, "version_id": "version-101",
                "observed_at_utc": "2026-10-20T12:00:30Z",
            },
            "challenge": {
                "scope": "repo.tenant.alpha", "request_id": "request-001",
                "nonce": "nonce-001", "issuer_id": "verifier-002",
                "issued_at_utc": "2026-10-20T12:00:00Z",
                "expires_at_utc": "2026-10-20T12:02:00Z",
            },
            "revocation": {
                "key_id": "key-001", "credential_epoch": 7,
                "status": "ACTIVE",
                "observed_at_utc": "2026-10-20T12:00:40Z",
            },
            "producer": {
                "request_id": "request-001", "intent_id": "intent-001",
                "outcome": "NO_EFFECT_FENCED", "provider_message_id": "msg-000",
                "receipt_digest": "c" * 64,
            },
            "administration": {
                "executor_root": "admin-executor", "issuer_root": "admin-issuer",
                "verifier_root": "admin-verifier", "recovery_root": "admin-recovery",
                "nonce_cache_root": "admin-replay", "producer_root": "admin-producer",
            },
        }

    def check(self, r=None, b=None, now="2026-10-20T12:01:00Z", seen=None):
        return inspect(self.req if r is None else r,
                       self.bundle if b is None else b, now_utc=now,
                       locally_seen_nonces=[] if seen is None else seen)

    def amended(self, section, field, value):
        obj = deepcopy(self.bundle)
        obj[section][field] = value
        return obj

    def denied(self, result):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIs(result["allowed"], False)
        self.assertTrue(result["simulation_only"])
        self.assertIs(result["externally_authenticated"], False)
        self.assertIs(result["off_host_nonce_guard_authenticated"], False)
        self.assertIs(result["latest_head_authenticated"], False)
        self.assertIs(result["no_effect_fence_authenticated"], False)
        self.assertEqual(result["blockers"], tuple(sorted(set(result["blockers"]))))
        self.assertEqual(result["structural_defects"],
                         tuple(sorted(set(result["structural_defects"]))))
        for flag in NO_GO_FLAGS:
            self.assertIs(result[flag], False, flag)
        for block in APPROVAL_GAPS:
            self.assertIn(block, result["blockers"])
        return result

    def defect(self, expected, r=None, b=None, now="2026-10-20T12:01:00Z", seen=None):
        got = self.denied(self.check(r=r, b=b, now=now, seen=seen))
        self.assertIn(expected, got["structural_defects"], got["structural_defects"])
        return got

    def test_01_coherent_claims_still_blocked(self):
        r = self.denied(self.check())
        self.assertTrue(r["claims_syntactically_coherent_lab"])
        self.assertEqual(r["structural_defects"], ())

    def test_02_caller_can_replace_all_claims_coherently(self):
        req = deepcopy(self.req)
        b = deepcopy(self.bundle)
        req["key_id"] = b["issuer"]["key_id"] = b["revocation"]["key_id"] = "attacker-key"
        req["head_digest"] = b["head"]["head_digest"] = "f" * 64
        req["nonce"] = b["challenge"]["nonce"] = "attacker-nonce"
        self.assertTrue(self.denied(self.check(req, b))["claims_syntactically_coherent_lab"])

    def test_03_repeat_is_not_durable_nonce_proof(self):
        self.assertEqual(self.denied(self.check()), self.denied(self.check()))

    def test_04_replayed_nonce_in_untrusted_local_cache_denied(self):
        self.defect("CLAIMED_NONCE_REPLAY_LOCAL", seen=["nonce-001"])

    def test_05_nonce_not_in_local_list_still_denied(self):
        self.denied(self.check(seen=["nonce-previous"]))

    def test_06_nonce_wrong_request_binding(self):
        self.defect("CHALLENGE_BINDING_MISMATCH", b=self.amended("challenge", "nonce", "nonce-002"))

    def test_07_challenge_request_mismatch(self):
        self.defect("CHALLENGE_BINDING_MISMATCH", b=self.amended("challenge", "request_id", "request-999"))

    def test_08_challenge_scope_mismatch(self):
        self.defect("CHALLENGE_BINDING_MISMATCH", b=self.amended("challenge", "scope", "tenant.other"))

    def test_09_expired_challenge(self):
        self.defect("CHALLENGE_EXPIRED_OR_NOT_YET_ISSUED", now="2026-10-20T12:02:00Z")

    def test_10_challenge_not_yet_valid(self):
        self.defect("CHALLENGE_EXPIRED_OR_NOT_YET_ISSUED", now="2026-10-20T11:59:59Z")

    def test_11_too_long_challenge_ttl(self):
        self.defect("CHALLENGE_TTL_INVALID", b=self.amended("challenge", "expires_at_utc", "2026-10-20T12:04:01Z"))

    def test_12_challenge_ttl_reversed(self):
        self.defect("CHALLENGE_TTL_INVALID", b=self.amended("challenge", "expires_at_utc", "2026-10-20T11:59:59Z"))

    def test_13_invalid_challenge_calendar(self):
        self.defect("CHALLENGE_FIELDS_INVALID", b=self.amended("challenge", "issued_at_utc", "2026-02-30T12:00:00Z"))

    def test_14_untrusted_now_rejected(self):
        self.defect("NOW_UTC_INVALID", now="2026-10-20")

    def test_15_stale_head(self):
        self.defect("HEAD_OBSERVATION_STALE_OR_FUTURE", b=self.amended("head", "observed_at_utc", "2026-10-20T11:58:00Z"))

    def test_16_future_head(self):
        self.defect("HEAD_OBSERVATION_STALE_OR_FUTURE", b=self.amended("head", "observed_at_utc", "2026-10-20T12:01:01Z"))

    def test_17_head_sequence_rollback(self):
        self.defect("HEAD_REQUEST_BINDING_MISMATCH", b=self.amended("head", "sequence", 44))

    def test_18_head_epoch_mismatch(self):
        self.defect("HEAD_REQUEST_BINDING_MISMATCH", b=self.amended("head", "epoch", 9))

    def test_19_head_digest_fork(self):
        self.defect("HEAD_REQUEST_BINDING_MISMATCH", b=self.amended("head", "head_digest", "d" * 64))

    def test_20_head_scope_mismatch(self):
        self.defect("HEAD_REQUEST_BINDING_MISMATCH", b=self.amended("head", "scope", "tenant.other"))

    def test_21_invalid_version_id(self):
        self.defect("HEAD_FIELDS_INVALID", b=self.amended("head", "version_id", True))

    def test_22_issuer_key_mismatch(self):
        self.defect("ISSUER_REQUEST_BINDING_MISMATCH", b=self.amended("issuer", "key_id", "key-999"))

    def test_23_issuer_scope_mismatch(self):
        self.defect("ISSUER_REQUEST_BINDING_MISMATCH", b=self.amended("issuer", "scope", "scope-other"))

    def test_24_issuer_revoked(self):
        self.defect("ISSUER_NOT_ACTIVE", b=self.amended("issuer", "status", "REVOKED"))

    def test_25_issuer_unknown(self):
        self.defect("ISSUER_NOT_ACTIVE", b=self.amended("issuer", "status", "UNKNOWN"))

    def test_26_algorithm_substitution(self):
        self.defect("ISSUER_FIELDS_INVALID", b=self.amended("issuer", "algorithm", "ED25519_PH_SHA_512"))

    def test_27_wrong_key_fingerprint(self):
        self.defect("ISSUER_FIELDS_INVALID", b=self.amended("issuer", "public_key_sha256", "X" * 64))

    def test_28_revocation_key_mismatch(self):
        self.defect("REVOCATION_REQUEST_BINDING_MISMATCH", b=self.amended("revocation", "key_id", "key-009"))

    def test_29_revocation_epoch_mismatch(self):
        self.defect("REVOCATION_REQUEST_BINDING_MISMATCH", b=self.amended("revocation", "credential_epoch", 6))

    def test_30_revocation_negative_status(self):
        self.defect("REVOCATION_STATUS_NOT_ACTIVE", b=self.amended("revocation", "status", "REVOKED"))

    def test_31_revocation_unknown(self):
        self.defect("REVOCATION_STATUS_NOT_ACTIVE", b=self.amended("revocation", "status", "UNKNOWN"))

    def test_32_revocation_stale(self):
        self.defect("REVOCATION_OBSERVATION_STALE_OR_FUTURE", b=self.amended("revocation", "observed_at_utc", "2026-10-20T11:58:00Z"))

    def test_33_revocation_future(self):
        self.defect("REVOCATION_OBSERVATION_STALE_OR_FUTURE", b=self.amended("revocation", "observed_at_utc", "2026-10-20T12:01:02Z"))

    def test_34_producer_intent_mismatch(self):
        self.defect("PRODUCER_BINDING_MISMATCH", b=self.amended("producer", "intent_id", "other-intent"))

    def test_35_producer_request_mismatch(self):
        self.defect("PRODUCER_BINDING_MISMATCH", b=self.amended("producer", "request_id", "other-request"))

    def test_36_uncertain_is_not_no_effect(self):
        self.defect("PRODUCER_UNCERTAIN_NO_TERMINAL_PROOF", b=self.amended("producer", "outcome", "UNCERTAIN"))

    def test_37_fake_committed_receipt_no_authority(self):
        b = self.amended("producer", "outcome", "COMMITTED_EFFECT")
        self.assertTrue(self.denied(self.check(b=b))["claims_syntactically_coherent_lab"])

    def test_38_unknown_provider_outcome(self):
        self.defect("PRODUCER_FIELDS_INVALID", b=self.amended("producer", "outcome", "SUCCESS"))

    def test_39_provider_digest_malformed(self):
        self.defect("PRODUCER_FIELDS_INVALID", b=self.amended("producer", "receipt_digest", "bad"))

    def test_40_admin_root_same_executor_and_issuer(self):
        self.defect("CLAIMED_ADMIN_ROOTS_OVERLAP", b=self.amended("administration", "issuer_root", "admin-executor"))

    def test_41_admin_root_recovery_and_nonce_cache_overlap(self):
        self.defect("CLAIMED_ADMIN_ROOTS_OVERLAP", b=self.amended("administration", "recovery_root", "admin-replay"))

    def test_42_unique_admin_labels_still_not_independence_proof(self):
        self.assertTrue(self.denied(self.check())["claims_syntactically_coherent_lab"])

    def test_43_missing_claim_all_claims_required(self):
        for name in BUNDLE_FIELDS:
            with self.subTest(name=name):
                b = deepcopy(self.bundle)
                del b[name]
                self.defect("BUNDLE_SHAPE_INVALID", b=b)

    def test_44_unknown_claim_optimistic_flag_rejected(self):
        b = deepcopy(self.bundle)
        b["verified"] = True
        self.defect("BUNDLE_SHAPE_INVALID", b=b)

    def test_45_invalid_request_types_boolean_not_int(self):
        for field in ("credential_epoch", "epoch", "sequence"):
            with self.subTest(field=field):
                r = deepcopy(self.req)
                r[field] = True
                self.defect("REQUEST_FIELD_INVALID:" + field, r=r)

    def test_46_invalid_req_digest(self):
        r = deepcopy(self.req)
        r["head_digest"] = "A" * 64
        self.defect("REQUEST_FIELD_INVALID:head_digest", r=r)

    def test_47_invalid_local_seen_nonces_types(self):
        for seen in (True, "nonce-001", [object()], [True], ["valid"] * 129):
            with self.subTest(kind=type(seen).__name__):
                self.defect("LOCAL_NONCE_SET_INVALID", seen=seen)

    def test_48_hostile_claim_type_not_invoked(self):
        class Evil:
            def __eq__(self, other): raise AssertionError("untrusted eq")
            def __str__(self): raise AssertionError("untrusted str")
        self.defect("ISSUER_FIELDS_INVALID", b=self.amended("issuer", "key_id", Evil()))
        self.defect("ADMIN_ROOT_FIELDS_INVALID", b=self.amended("administration", "recovery_root", Evil()))

    def test_49_hostile_dict_subclass_is_rejected(self):
        class EvilDict(dict):
            def __iter__(self): raise AssertionError("hostile iterator")
            def keys(self): raise AssertionError("hostile keys")
        b = deepcopy(self.bundle)
        b["head"] = EvilDict(b["head"])
        self.defect("CLAIM_SHAPE_INVALID:head", b=b)

    def test_50_missing_or_extra_nested_fields_rejected(self):
        for section in BUNDLE_FIELDS:
            with self.subTest(section=section):
                b = deepcopy(self.bundle)
                b[section]["verified"] = True
                self.defect("CLAIM_SHAPE_INVALID:" + section, b=b)

    def test_51_non_dict_inputs_denied(self):
        for raw in (None, False, 42, "signed", [], object()):
            with self.subTest(kind=type(raw).__name__):
                r = self.denied(inspect(raw, raw, now_utc="2026-10-20T12:01:00Z",
                                        locally_seen_nonces=[]))
                self.assertFalse(r["claims_syntactically_coherent_lab"])

    def test_52_canonical_field_sets_fixed(self):
        self.assertEqual(set(self.req), REQUEST_FIELDS)
        self.assertEqual(set(self.bundle), BUNDLE_FIELDS)
        for section in BUNDLE_FIELDS:
            self.assertEqual(set(self.bundle[section]), CLAIM_FIELDS[section])

    def test_53_invalid_request_subclass_not_trusted(self):
        class EvilDict(dict):
            def __iter__(self): raise AssertionError("malicious")
        raw = EvilDict(self.req)
        self.defect("REQUEST_SHAPE_INVALID", r=raw)

    def test_54_nonce_consumption_cannot_be_proven_from_claim_flags(self):
        b = deepcopy(self.bundle)
        b["challenge"]["external_replay_guard_verified"] = True
        self.defect("CLAIM_SHAPE_INVALID:challenge", b=b)

    def test_55_producer_fence_cannot_be_proven_from_claim_flags(self):
        b = deepcopy(self.bundle)
        b["producer"]["independent_receipt_verified"] = True
        self.defect("CLAIM_SHAPE_INVALID:producer", b=b)


if __name__ == "__main__":
    unittest.main()
