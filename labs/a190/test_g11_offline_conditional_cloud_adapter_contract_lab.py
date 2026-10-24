"""A190 G11: offline vendor-wire contracts; does not call AWS or Google."""
import json
import unittest
from hashlib import sha256

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g8_independent_authority_protocol_lab import (
    EVENT_DOMAIN, pub_bytes, seal, synthetic_event,
)
from g11_offline_conditional_cloud_adapter_contract_lab import (
    ALWAYS_DENY, ContractDenied, check_dangerous_request,
    classify_wire_response, dynamodb_envelopes, firestore_envelopes,
    original_subject,
)


class G11OfflineConditionalRequestContracts(unittest.TestCase):
    def setUp(self):
        self.issuer = Ed25519PrivateKey.generate()
        self.pin = pub_bytes(self.issuer)
        self.event = synthetic_event(self.issuer)

    def ddb(self, request="req-1", event=None):
        return dynamodb_envelopes(
            event if event is not None else self.event, self.pin, request,
        )

    def fs(self, request="req-1", event=None):
        return firestore_envelopes(
            event if event is not None else self.event, self.pin, request,
        )

    def test_01_both_providers_share_signed_semantic_native_key(self):
        a, b = self.ddb(), self.fs()
        self.assertEqual(a["native_id"], b["native_id"])
        self.assertTrue(a["native_id"].startswith("aion-g11-"))
        self.assertEqual(73, len(a["native_id"]))
        print("A190_G11_SIGNED_NATIVE_KEY_CROSS_PROVIDER=STABLE")

    def test_02_alternative_request_id_still_one_semantic_key(self):
        a, b = self.ddb("req-alpha"), self.ddb("req-beta")
        self.assertEqual(a["native_id"], b["native_id"])
        self.assertNotEqual(a["put"]["args"]["Item"]["request_id"],
                            b["put"]["args"]["Item"]["request_id"])
        print("A190_G11_CALLER_REQUEST_ID_CANNOT_CHANGE_NATIVE_KEY")

    def test_03_different_signed_original_refs_same_intent_one_key(self):
        second = synthetic_event(self.issuer, ref="source-event-second")
        self.assertEqual(self.ddb()["native_id"],
                         self.ddb(event=second)["native_id"])
        print("A190_G11_SIGNED_EVENT_ALIASES_SAME_SEMANTIC=ONE_KEY")

    def test_04_self_signed_issuer_forgery_denied(self):
        bad = synthetic_event(Ed25519PrivateKey.generate())
        with self.assertRaisesRegex(ContractDenied, "BAD_ORIGINAL_ISSUER"):
            self.ddb(event=bad)
        with self.assertRaises(ContractDenied):
            self.fs(event=bad)
        print("A190_G11_ATTACKER_SELF_PINNED_EVENT=DENIED")

    def test_05_tamper_signed_payload_denied(self):
        altered = json.loads(json.dumps(self.event))
        altered["payload"]["semantic_digest"] = "0" * 64
        with self.assertRaises(ContractDenied):
            self.ddb(event=altered)
        print("A190_G11_TAMPERED_SEMANTIC_AFTER_SIGN=DENIED")

    def test_06_different_authentic_semantic_intents_different_keys(self):
        second = synthetic_event(
            self.issuer, digest=sha256(b"ANOTHER-SYNTHETIC-INTENT").hexdigest()
        )
        self.assertNotEqual(self.ddb()["native_id"],
                            self.ddb(event=second)["native_id"])
        print("A190_G11_DISTINCT_AUTHENTIC_INTENTS=SEPARATE_KEYS")

    def test_07_tenant_bound_under_signed_issuer_context(self):
        other_payload = json.loads(json.dumps(self.event["payload"]))
        other_payload["tenant"] = "synthetic_tenant_two"
        other = seal(self.issuer, EVENT_DOMAIN, other_payload)
        self.assertNotEqual(self.ddb()["native_id"],
                            self.ddb(event=other)["native_id"])
        print("A190_G11_TENANT_IN_SIGNED_NATIVE_KEY=TRUE")

    def test_08_dynamodb_put_requires_attribute_not_exists(self):
        req = self.ddb()
        args = req["put"]["args"]
        self.assertEqual("PutItem", req["put"]["action"])
        self.assertEqual("attribute_not_exists(#pk)",
                         args["ConditionExpression"])
        self.assertEqual({"#pk": "PK"}, args["ExpressionAttributeNames"])
        self.assertEqual("NONE", args["ReturnValues"])
        self.assertFalse(args["Item"]["real_effect"]["BOOL"])
        print("A190_G11_DDB_ATOMIC_CONDITIONAL_PUT_SHAPE=DOCUMENTARY")

    def test_09_dynamodb_get_strong_consistent_by_design(self):
        req = self.ddb()
        self.assertEqual("GetItem", req["lookup"]["action"])
        self.assertIs(req["lookup"]["args"]["ConsistentRead"], True)
        self.assertEqual(req["native_id"],
                         req["lookup"]["args"]["Key"]["PK"]["S"])
        print("A190_G11_DDB_STRONG_GET_SHAPE=DOCUMENTARY")

    def test_10_firestore_patch_exists_false_and_native_doc_id(self):
        req = self.fs()
        self.assertEqual("PATCH", req["put"]["method"])
        self.assertEqual("false",
                         req["put"]["query"]["currentDocument.exists"])
        self.assertTrue(req["put"]["body"]["name"].endswith(req["native_id"]))
        self.assertFalse(
            req["put"]["body"]["fields"]["real_effect"]["booleanValue"]
        )
        print("A190_G11_FIRESTORE_EXISTS_FALSE_PATCH_SHAPE=DOCUMENTARY")

    def test_11_firestore_lookup_without_stale_readtime(self):
        req = self.fs()
        self.assertEqual("GET", req["lookup"]["method"])
        self.assertEqual({}, req["lookup"]["query"])
        self.assertEqual(req["put"]["url_shape"], req["lookup"]["url_shape"])
        print("A190_G11_FIRESTORE_DEFAULT_STRONG_GET_SHAPE=DOCUMENTARY")

    def test_12_unsafe_mutations_not_whitelisted(self):
        for op in ("DeleteItem", "UpdateItem", "BatchWriteItem",
                   "RestoreTableFromBackup", "TransactWriteItems"):
            with self.subTest(operation=op):
                with self.assertRaises(ContractDenied):
                    check_dangerous_request("dynamodb", op)
        for op in ("DELETE", "POST", "BATCH_WRITE"):
            with self.subTest(operation=op):
                with self.assertRaises(ContractDenied):
                    check_dangerous_request("firestore", op)
        print("A190_G11_DELETE_UPDATE_RESTORE_NONCONDITIONAL_MUTATION=DENIED")

    def test_13_transport_timeout_after_send_is_uncertain(self):
        for provider in ("dynamodb", "firestore"):
            result = classify_wire_response(
                provider, stage="RESERVE", status_code=None,
            )
            self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND",
                             result["classification"])
            self.assertFalse(result["auto_resend"])
        print("A190_G11_UNKNOWN_STORAGE_ACK=UNCERTAIN_ZERO_AUTO_RESEND")

    def test_14_conditional_duplicate_requires_read_only_path(self):
        a = classify_wire_response(
            "dynamodb", stage="RESERVE", status_code=400,
            error_code="ConditionalCheckFailedException",
        )
        b = classify_wire_response(
            "firestore", stage="RESERVE", status_code=412,
            error_code="FAILED_PRECONDITION",
        )
        self.assertEqual(a["classification"], b["classification"])
        self.assertEqual("DUPLICATE_STORAGE_RESERVATION_READ_ONLY_ONLY",
                         b["classification"])
        print("A190_G11_PROVIDER_ALREADY_EXISTS=READ_ONLY_NO_RETRY")

    def test_15_successful_conditional_write_not_effect_proof(self):
        for provider in ("dynamodb", "firestore"):
            result = classify_wire_response(
                provider, stage="RESERVE", status_code=200,
            )
            self.assertEqual(
                "STORAGE_RESERVATION_ACK_NOT_EFFECT_PROOF",
                result["classification"],
            )
            self.assertFalse(result["real_effect_allowed"])
        print("A190_G11_CLOUD_DB_COMMIT_IS_NOT_VENDOR_EFFECT=ENFORCED")

    def test_16_forged_response_body_never_grants_effect(self):
        result = classify_wire_response(
            "firestore", stage="READ_ONLY_RECONCILE", status_code=200,
            response_body={
                "state": "REAL_EFFECT_CONFIRMED",
                "signature": "caller_self_signed",
            },
        )
        self.assertFalse(result["response_body_trusted_as_effect_proof"])
        self.assertEqual(ALWAYS_DENY, result["operational_verdict"])
        print("A190_G11_FORGED_DB_RESPONSE_EFFECT_FIELD=NO_GO")

    def test_17_expired_source_event_denied(self):
        expiration = self.event["payload"]["expires"]
        with self.assertRaisesRegex(ContractDenied, "SCOPE_OR_TIME"):
            original_subject(self.event, self.pin, now=expiration + 1)
        print("A190_G11_EXPIRED_ORIGINAL_ISSUER_EVENT=DENIED")

    def test_18_unsafe_project_and_request_identifiers_denied(self):
        with self.assertRaises(ContractDenied):
            self.fs(project="../../other-project")
        with self.assertRaises(ContractDenied):
            self.ddb("../../../different-intent")
        with self.assertRaises(ContractDenied):
            self.fs(request="../../evil")
        print("A190_G11_PATH_TRAVERSAL_AND_UNSAFE_IDS=DENIED")

    def test_19_provider_and_stage_not_open_ended(self):
        with self.assertRaises(ContractDenied):
            check_dangerous_request("random-api", "POST")
        with self.assertRaises(ContractDenied):
            classify_wire_response("random-api", stage="RESERVE")
        with self.assertRaises(ContractDenied):
            classify_wire_response("dynamodb", stage="SEND_REAL_EFFECT")
        print("A190_G11_NO_ARBITRARY_PROVIDER_OR_REAL_SEND_STAGE")

    def test_20_all_envelopes_prohibit_execution_even_if_valid(self):
        for req in (self.ddb(), self.fs()):
            self.assertFalse(req["execution_allowed"])
            self.assertFalse(req["external_root_verified"])
            self.assertFalse(req["vendor_effect_verified"])
            self.assertEqual(ALWAYS_DENY, req["security_decision"])
        print("A190_G11_OFFLINE_ENVELOPES_EXECUTION_ALLOWED=FALSE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
