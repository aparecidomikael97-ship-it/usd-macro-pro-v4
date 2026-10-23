"""Synthetic LAB callbacks and keys; real Ed25519 verification, no authority claim."""
from copy import deepcopy
import base64
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aion_chat import external_authority_a183_lab as contract
from aion_chat.signed_receipt_lab import canonical_bytes
import test_atlasquant_aion_authority_a183_lab as authority_fixtures


class AuthorityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = authority_fixtures.AuthorityContractTests()
        self.fixture.setUp()

    def test_query_cannot_replace_original_binding_through_retained_input(self):
        fixture = self.fixture
        def changed_original(challenge, event, kind):
            fixture.event["original_sha256"] = "b" * 64
            fixture.event["event_id"] = "replacement-original"
            return fixture.query(challenge, fixture.event, kind)
        self.assertIsNone(fixture.verifier().admit(
            "RESERVATION", fixture.event, changed_original))

    def test_distinct_roles_must_sign_one_identical_message(self):
        fixture = self.fixture
        retained = {}
        roles = list(contract.REQUIRED["RESERVATION"])
        messages = []
        def mixed_response(*args):
            response = fixture.query(*args)
            replacement = deepcopy(response["payload"])
            replacement["original_sha256"] = "b" * 64
            response["signatures"][roles[1]]["signature"] = base64.b64encode(
                fixture.private[roles[1]].sign(
                    contract.DOMAIN + canonical_bytes(replacement))).decode("ascii")
            retained.update(response=response, replacement=replacement)
            return response
        class RealVerificationWithCallerMutation:
            @staticmethod
            def from_public_bytes(value):
                key = Ed25519PublicKey.from_public_bytes(value)
                class Verifier:
                    def verify(self, signature, message):
                        key.verify(signature, message)
                        messages.append(message)
                        if len(messages) == 1:
                            retained["response"]["payload"].update(retained["replacement"])
                return Verifier()
        with patch.object(contract, "Ed25519PublicKey", RealVerificationWithCallerMutation):
            result = fixture.verifier().admit("RESERVATION", fixture.event, mixed_response)
        self.assertIsNone(result, "two valid signatures over DIFFERENT bodies are not a quorum")

    def test_retained_response_mutation_cannot_invalidate_captured_signed_bytes(self):
        fixture = self.fixture
        retained = {}
        messages = []
        def response(*args):
            retained["response"] = fixture.query(*args)
            return retained["response"]
        class RealVerificationWithCallerMutation:
            @staticmethod
            def from_public_bytes(value):
                key = Ed25519PublicKey.from_public_bytes(value)
                class Verifier:
                    def verify(self, signature, message):
                        key.verify(signature, message)
                        messages.append(message)
                        retained["response"]["payload"]["status"] = "caller-mutated-after-capture"
                return Verifier()
        with patch.object(contract, "Ed25519PublicKey", RealVerificationWithCallerMutation):
            result = fixture.verifier().admit("RESERVATION", fixture.event, response)
        self.assertIsNotNone(result)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], messages[1])
        self.assertFalse(result["permits_send"])
        self.assertFalse(result["permits_retry"])
        self.assertFalse(result["external_homologation"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
