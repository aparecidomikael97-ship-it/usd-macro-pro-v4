"""External requirements deliberately RED. Run explicitly; never production acceptance.

No expectedFailure, skip or failure masking: each failed assertion is an unmet
external guarantee. These tests are excluded from the regression suite by name,
and run in their OWN failing CI job with logs retained.
"""
from copy import deepcopy
import unittest
import test_atlasquant_aion_intent_binding_a182_lab as a182


class ExternalRequirementsRed(a182.A182Fixture):
    def test_custody_plus_checkpoint_rollback_must_not_reauthorize(self):
        original=self.original()
        self.assertTrue(self.binding_guard(original)(original))
        self.custody_db.unlink()
        self.custody=self.bootstrap()
        self.assertFalse(self.binding_guard(original,minimum_sequence=0)(original),
                         "UNMET: independent monotonic custody and checkpoint")

    def test_replacement_original_enrollment_must_be_detected(self):
        original=self.original()
        changed=deepcopy(original)
        changed["decision"]["aggregate_key"]="forged-business-identity"
        self.assertFalse(self.binding_guard(changed)(changed),
                         "UNMET: authenticated immutable original business identity")

    def test_replacement_trust_root_and_fingerprint_must_be_detected(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from aion_chat.intent_binding_a182_lab import BoundFirstAttemptWitnessLab, trust_fingerprint
        from test_atlasquant_aion_signed_receipt_a178_lab import public_bytes
        from test_atlasquant_aion_separate_custody_a181_lab import ISSUER, KEY_ID
        from test_atlasquant_aion_execution_outbox import NOW
        from datetime import timedelta
        public=public_bytes(Ed25519PrivateKey.from_private_bytes(b"\x22"*32))
        with self.assertRaises(ValueError, msg="UNMET: externally pinned trust authority"):
            BoundFirstAttemptWitnessLab(
                original_decision=self.original()["decision"],
                issuer=ISSUER,key_id=KEY_ID,public_key=public,
                expected_trust_sha256=trust_fingerprint(
                    issuer=ISSUER,key_id=KEY_ID,public_key=public),
                minimum_sequence=0,checkpoint=self.custody.snapshot,
                reserve=self.custody.reserve,now=NOW+timedelta(seconds=2))


if __name__ == "__main__":
    unittest.main(verbosity=2)

