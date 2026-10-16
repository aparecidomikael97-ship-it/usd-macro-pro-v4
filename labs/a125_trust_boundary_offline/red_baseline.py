"""INTENTIONAL RED: post-send attestation is too late to protect any effect.

Run separately. Expected 1 FAIL, not part of green regression suite.
"""
import unittest
from test_contract import fixture
from contract import MockCustodian, Denied


class ExpectedRed(unittest.TestCase):
    def test_post_send_identity_check_cannot_undo_fake_effect(self):
        enrollment,intent,provider,custodian,client=fixture()
        impersonator=MockCustodian(enrollment,signature_key=b'ATTACKER-UNPINNED-SIGNER',provider=provider)
        receipt=impersonator.reserve_and_issue(intent,nonce='red-post-check-000001')
        with self.assertRaisesRegex(Denied,'SIGNATURE_INVALID'):
            client.verify_receipt(intent,'red-post-check-000001',receipt)
        # Correct preflight would ensure no provider invocation.
        self.assertEqual(len(provider.sent),0)


if __name__=='__main__':unittest.main()
