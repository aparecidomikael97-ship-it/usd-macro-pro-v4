"""A125 OFFLINE tests: positives prove only toy assumptions; OPEN exploits explicit."""
import unittest
from copy import deepcopy
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

from contract import Enrollment, Intent, MockProvider, MockCustodian, PinnedClient, Denied, Unknown, production_eligible


def fixture():
    e=Enrollment(owner_id='owner-demo',tenant_id='tenant-a',workspace_id='ws-a',
        provider_account='mock-provider-1',endpoint='custody://A125-fixture',
        witness_id='WITNESS-A125-FIXTURE',issuer='fixture-issuer',key_id='fixture-k1',epoch=7)
    i=Intent(intent_id='logical-intent-1',owner_id=e.owner_id,tenant_id=e.tenant_id,
        workspace_id=e.workspace_id,provider_account=e.provider_account,
        action='FAKE_MESSAGE',payload_digest='a'*64,recipient_digest='b'*64,epoch=e.epoch)
    provider=MockProvider()
    custodian=MockCustodian(e,signature_key=b'FAKE-SHARED-KEY',provider=provider)
    client=PinnedClient(e,verifier_key=b'FAKE-SHARED-KEY')
    return e,i,provider,custodian,client


class ContractTests(unittest.TestCase):
    def test_01_valid_mock_issue_is_unknown_not_effect(self):
        e,i,p,c,v=fixture(); out=v.issue_once(i,c,nonce='unique-issue-000001')
        self.assertEqual(out['status'],'UNKNOWN'); self.assertFalse(out['provider_effect_proven'])
        self.assertFalse(out['no_effect_fenced']); self.assertEqual(len(p.sent),1)

    def test_02_duplicate_never_auto_resends(self):
        e,i,p,c,v=fixture();v.issue_once(i,c,nonce='unique-issue-000002')
        with self.assertRaises(Denied):v.issue_once(i,c,nonce='unique-issue-000003')
        self.assertEqual(len(p.sent),1)

    def test_03_tenant_change_denied_before_provider(self):
        e,i,p,c,v=fixture()
        with self.assertRaisesRegex(Denied,'SCOPE'):v.issue_once(replace(i,tenant_id='tenant-b'),c,nonce='unique-issue-000004')
        self.assertEqual(p.sent,[])

    def test_04_workspace_change_denied_before_provider(self):
        e,i,p,c,v=fixture()
        with self.assertRaises(Denied):v.issue_once(replace(i,workspace_id='ws-b'),c,nonce='unique-issue-000005')
        self.assertEqual(p.sent,[])

    def test_05_owner_change_denied_before_provider(self):
        e,i,p,c,v=fixture()
        with self.assertRaises(Denied):v.issue_once(replace(i,owner_id='other-owner'),c,nonce='unique-issue-000006')
        self.assertEqual(p.sent,[])

    def test_06_provider_account_change_denied_before_provider(self):
        e,i,p,c,v=fixture()
        with self.assertRaises(Denied):v.issue_once(replace(i,provider_account='other-provider'),c,nonce='unique-issue-000007')
        self.assertEqual(p.sent,[])

    def test_07_epoch_change_denied_before_provider(self):
        e,i,p,c,v=fixture()
        with self.assertRaises(Denied):v.issue_once(replace(i,epoch=8),c,nonce='unique-issue-000008')
        self.assertEqual(p.sent,[])

    def test_08_issuer_change_denied_before_provider(self):
        e,i,p,c,v=fixture()
        foreign=MockCustodian(replace(e,issuer='forged'),signature_key=b'FAKE-SHARED-KEY',provider=p)
        with self.assertRaises(Denied):v.issue_once(i,foreign,nonce='unique-issue-000009')
        self.assertEqual(p.sent,[])

    def test_09_endpoint_change_denied_before_provider(self):
        e,i,p,c,v=fixture()
        foreign=MockCustodian(replace(e,endpoint='custody://attacker'),signature_key=b'FAKE-SHARED-KEY',provider=p)
        with self.assertRaises(Denied):v.issue_once(i,foreign,nonce='unique-issue-000010')
        self.assertEqual(p.sent,[])

    def test_10_identical_metadata_new_signer_without_key_denied_pre_send(self):
        e,i,p,c,v=fixture()
        impostor=MockCustodian(e,signature_key=b'WRONG-KEY',provider=p)
        with self.assertRaisesRegex(Denied,'ATTESTATION_INVALID'):
            v.issue_once(i,impostor,nonce='unique-issue-000011')
        self.assertEqual(p.sent,[])

    def test_11_identity_challenge_is_bound_to_nonce(self):
        e,i,p,c,v=fixture();proof=c.attest_identity('unique-issue-000012');proof['body']['challenge']='unique-issue-000013'
        self.assertNotEqual(proof['signature'],sha256(b'anything').hexdigest())
        # Mutated proof cannot validate against its now-altered challenge.
        from contract import canonical
        import hmac
        new=hmac.new(b'FAKE-SHARED-KEY',canonical(proof['body']),'sha256').hexdigest()
        self.assertNotEqual(proof['signature'],new)

    def test_12_wrong_receipt_signature_denied(self):
        e,i,p,c,v=fixture();receipt=c.reserve_and_issue(i,nonce='unique-issue-000014')
        bad=deepcopy(receipt);bad['signature']='0'*64
        with self.assertRaisesRegex(Denied,'SIGNATURE_INVALID'):v.verify_receipt(i,'unique-issue-000014',bad)

    def test_13_receipt_rebound_to_other_payload_denied(self):
        e,i,p,c,v=fixture();receipt=c.reserve_and_issue(i,nonce='unique-issue-000015')
        other=replace(i,payload_digest='c'*64)
        with self.assertRaises(Denied):v.verify_receipt(other,'unique-issue-000015',receipt)

    def test_14_receipt_wrong_nonce_denied(self):
        e,i,p,c,v=fixture();receipt=c.reserve_and_issue(i,nonce='unique-issue-000016')
        with self.assertRaises(Denied):v.verify_receipt(i,'unique-issue-000017',receipt)

    def test_15_receipt_false_delivery_claim_denied(self):
        e,i,p,c,v=fixture();receipt=c.reserve_and_issue(i,nonce='unique-issue-000018')
        mutated=deepcopy(receipt);mutated['body']['provider_effect_proven']=True
        with self.assertRaises(Denied):v.verify_receipt(i,'unique-issue-000018',mutated)

    def test_16_receipt_false_noeffect_claim_denied(self):
        e,i,p,c,v=fixture();receipt=c.reserve_and_issue(i,nonce='unique-issue-000019')
        mutated=deepcopy(receipt);mutated['body']['no_effect_fenced']=True
        with self.assertRaises(Denied):v.verify_receipt(i,'unique-issue-000019',mutated)

    def test_17_reservation_crash_consumes_no_send(self):
        e,i,p,c,v=fixture()
        with self.assertRaises(Unknown):v.issue_once(i,c,nonce='unique-issue-000020',cut='after_reservation')
        with self.assertRaises(Denied):v.issue_once(i,c,nonce='unique-issue-000021')
        self.assertEqual(p.sent,[])

    def test_18_response_lost_after_fake_send_no_retry(self):
        e,i,p,c,v=fixture()
        with self.assertRaises(Unknown):v.issue_once(i,c,nonce='unique-issue-000022',cut='after_fake_send')
        with self.assertRaises(Denied):v.issue_once(i,c,nonce='unique-issue-000023')
        self.assertEqual(len(p.sent),1)

    def test_19_provider_direct_call_without_secret_denied(self):
        e,i,p,c,v=fixture()
        with self.assertRaises(Denied):p.send(credential='AION-DOES-NOT-HAVE',intention=i.identity())
        self.assertEqual(p.sent,[])

    def test_20_custodian_outage_denies(self):
        e,i,p,c,v=fixture();c.available=False
        with self.assertRaises(Unknown):v.issue_once(i,c,nonce='unique-issue-000024')
        self.assertEqual(p.sent,[])

    def test_21_same_intent_different_payload_denied(self):
        e,i,p,c,v=fixture();v.issue_once(i,c,nonce='unique-issue-000025')
        with self.assertRaises(Denied):c.reserve_and_issue(replace(i,payload_digest='e'*64),nonce='unique-issue-000026')
        self.assertEqual(len(p.sent),1)

    def test_22_global_nonce_replay_denied(self):
        e,i,p,c,v=fixture();v.issue_once(i,c,nonce='unique-issue-000027')
        other=replace(i,intent_id='another-intent')
        with self.assertRaises(Denied):v.issue_once(other,c,nonce='unique-issue-000027')
        self.assertEqual(len(p.sent),1)

    def test_23_32_threads_at_most_one_fake_send(self):
        e,i,p,c,v=fixture()
        def race(n):
            try:v.issue_once(i,c,nonce=f'unique-thread-{n:06d}');return 'ISSUED'
            except Denied:return 'DENIED'
        with ThreadPoolExecutor(max_workers=32) as ex:
            results=list(ex.map(race,range(32)))
        self.assertEqual(results.count('ISSUED'),1)
        self.assertEqual(results.count('DENIED'),31)
        self.assertEqual(len(p.sent),1)

    def test_24_malformed_digest_denied(self):
        e,i,p,c,v=fixture()
        with self.assertRaises(Denied):v.issue_once(replace(i,recipient_digest='garbage'),c,nonce='unique-issue-000028')
        self.assertEqual(p.sent,[])

    def test_25_revocation_not_automatic_ready(self):
        self.assertIs(production_eligible(),False)


class OpenCounterexampleTests(unittest.TestCase):
    """PASS means attack WORKS: explicitly OPEN, NOT a secure positive test."""
    def test_26_OPEN_stolen_provider_credential_bypasses_all_guards(self):
        e,i,p,c,v=fixture()
        # In-process access to _provider_token simulates absent IAM isolation.
        stolen=p._provider_token
        p.send(credential=stolen,intention=i.identity())
        self.assertEqual(len(p.sent),1)  # vulnerability REPRODUCED

    def test_27_OPEN_restoring_the_custodian_reenables_same_intent(self):
        e,i,p,c,v=fixture();v.issue_once(i,c,nonce='unique-issue-000029')
        c.attack_restore_as_same_admin()
        v.issue_once(i,c,nonce='unique-issue-000030')
        self.assertEqual(len(p.sent),2)  # vulnerability REPRODUCED

    def test_28_OPEN_stolen_signing_key_permits_impostor_with_same_pins(self):
        e,i,p,c,v=fixture()
        compromised_key=c._signature_key
        impostor=MockCustodian(e,signature_key=compromised_key,provider=p)
        v.issue_once(i,impostor,nonce='unique-issue-000031')
        self.assertEqual(len(p.sent),1)  # forged custody accepted: OPEN

    def test_29_OPEN_direct_custodian_call_bypasses_client_scope_pinning(self):
        e,i,p,c,v=fixture()
        alien=replace(i,tenant_id='tenant-b')
        # A compromised caller with access to the custodian object bypasses PinnedClient
        c.reserve_and_issue(alien,nonce='unique-issue-000032')
        self.assertEqual(len(p.sent),1)  # origin trust NOT proven


if __name__=='__main__':unittest.main()
