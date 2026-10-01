"""Offline contracts only: synthetic keys, fake externally verified IdP/membership.

Tests do NOT constitute an OIDC login, a cryptographic human signature or
transactional persistence for the in-memory document catalog.
"""
import hashlib
from contextlib import closing
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from aion_core.library_authorization import (
    AttestationVerifier, AuthorizationDenied, SecuredLibraryBoundary,
)
from aion_core.library_foundation import LibraryCatalog
from aion_core.library_security_runtime import (
    AuthenticatedLibraryService, DurableLibraryApprovalGateway, ExternalIdentityBridge,
    SqliteApprovalBurnLedger, VerifiedSession,
)
from test_aion_core_library_authorization import (
    IDENTITY_KEY, APPROVAL_KEY, RIGHTS_KEY, NOW, SHA, sign,
)


class IdentityBridgeTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.session = VerifiedSession('https-idp', 'aion-service', 'reviewer', NOW - 10, NOW + 100)
        self.verify_calls = []
        self.role_calls = []
        self.roles = ('LIBRARY_REVIEWER',)

        def verify(token):
            self.verify_calls.append(token)
            return self.session

        def membership(subject, tenant, domain):
            self.role_calls.append((subject, tenant, domain))
            return self.roles

        self.bridge = ExternalIdentityBridge(
            verify_token=verify, lookup_roles=membership,
            trusted_issuer='https-idp', token_audience='aion-service',
            attestation_issuer='authz', signing_key=IDENTITY_KEY,
            clock=lambda: self.now)
        self.verifier = AttestationVerifier(identity_issuers={'authz': IDENTITY_KEY},
            approval_issuers={'human': APPROVAL_KEY}, rights_issuers={'license': RIGHTS_KEY},
            clock=lambda: self.now)

    def issue(self, **kwargs):
        params = dict(token='synthetic-OIDC-token-12345', tenant_id='T-A',
                      domain_id='TRADER', action='APPROVE_INDEX')
        params.update(kwargs)
        return self.bridge.identity_envelope(**params)

    def test_verified_identity_is_signed_for_existing_boundary(self):
        env = self.issue()
        got = self.verifier.verify('identity', env)
        self.assertEqual(got['subject'], 'reviewer')
        self.assertEqual(got['roles'], ['LIBRARY_REVIEWER'])
        self.assertEqual(got['expires_at'], NOW + 100)
        self.assertEqual(self.role_calls, [('reviewer', 'T-A', 'TRADER')])

    def test_roles_must_come_from_server_not_token(self):
        self.roles = ('LIBRARY_READER',)
        with self.assertRaises(AuthorizationDenied):
            self.issue()

    def test_reader_may_read_but_not_approve(self):
        self.roles = frozenset(['LIBRARY_READER'])
        env = self.issue(action='READ')
        self.assertEqual(self.verifier.verify('identity', env)['roles'], ['LIBRARY_READER'])
        with self.assertRaises(AuthorizationDenied):
            self.issue()

    def test_wrong_token_issuer(self):
        self.session = VerifiedSession('evil-idp', 'aion-service', 'reviewer', NOW-10, NOW+100)
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_wrong_token_audience(self):
        self.session = VerifiedSession('https-idp', 'other-service', 'reviewer', NOW-10, NOW+100)
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_expired_token(self):
        self.session = VerifiedSession('https-idp', 'aion-service', 'reviewer', NOW-100, NOW)
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_token_from_future(self):
        self.session = VerifiedSession('https-idp', 'aion-service', 'reviewer', NOW+1, NOW+100)
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_bool_timestamps_denied(self):
        self.session = VerifiedSession('https-idp', 'aion-service', 'reviewer', True, NOW+100)
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_unverified_dict_claims_denied(self):
        self.session = {'issuer':'https-idp','subject':'reviewer', 'roles':['LIBRARY_ADMIN']}
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_rejected_whitespace_token_does_not_call_verifier(self):
        with self.assertRaises(AuthorizationDenied): self.issue(token='bearer something-with-spaces')
        self.assertEqual(self.verify_calls, [])

    def test_invalid_scope_does_not_call_verifier(self):
        with self.assertRaises(AuthorizationDenied): self.issue(tenant_id='other/tenant')
        self.assertEqual(self.verify_calls, [])

    def test_revoked_membership_denied(self):
        self.roles = tuple()
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_role_lookup_unavailable_fail_closed(self):
        self.bridge = ExternalIdentityBridge(
            verify_token=lambda token:self.session,
            lookup_roles=lambda *args: (_ for _ in ()).throw(RuntimeError('db offline')),
            trusted_issuer='https-idp', token_audience='aion-service',
            attestation_issuer='authz', signing_key=IDENTITY_KEY,clock=lambda:self.now)
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_token_verifier_failure_fail_closed(self):
        self.bridge = ExternalIdentityBridge(
            verify_token=lambda token: (_ for _ in ()).throw(RuntimeError('bad signature')),
            lookup_roles=lambda *args:('LIBRARY_ADMIN',),
            trusted_issuer='https-idp', token_audience='aion-service',
            attestation_issuer='authz', signing_key=IDENTITY_KEY,clock=lambda:self.now)
        with self.assertRaises(AuthorizationDenied): self.issue()

    def test_bad_key_denied(self):
        with self.assertRaises(AuthorizationDenied):
            ExternalIdentityBridge(verify_token=lambda t:self.session,lookup_roles=lambda *x:self.roles,
                trusted_issuer='https-idp',token_audience='aion-service',
                attestation_issuer='authz',signing_key=b'short')

    def test_signing_key_must_match_trusted_verifier(self):
        env=self.issue()
        self.verifier.verify('identity',env)
        bad=AttestationVerifier(identity_issuers={'authz':b'j'*32},
            approval_issuers={'human':APPROVAL_KEY},rights_issuers={'license':RIGHTS_KEY},clock=lambda:self.now)
        with self.assertRaises(AuthorizationDenied): bad.verify('identity',env)

    def test_attestation_ttl_capped_to_5_min(self):
        self.session=VerifiedSession('https-idp','aion-service','reviewer',NOW-10,NOW+3500)
        env=self.issue()
        self.assertEqual(self.verifier.verify('identity',env)['expires_at'],NOW+300)


class DurableLedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='aion-lib-security-')
        self.path=os.path.join(self.directory.name,'library_approval_burn.db')
        self.ledger=SqliteApprovalBurnLedger(trusted_absolute_path=self.path)
        self.catalog=LibraryCatalog()
        self.entry=self.catalog.register_document(tenant_id='T-A',domain_id='TRADER',
            document_id='DOC-1',version=1,sha256=SHA,source_type='BOOK',
            source_reference='isbn:123',license_kind='CC_BY',rights_holder='publisher',
            usage_scope='INTERNAL',human_approved_by='reviewer')
        self.catalog.transition(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,
            to_state='METADATA_REVIEW',actor='reviewer')
        self.verifier=AttestationVerifier(identity_issuers={'authz':IDENTITY_KEY},
            approval_issuers={'human':APPROVAL_KEY},rights_issuers={'license':RIGHTS_KEY},clock=lambda:NOW)
        self.boundary=SecuredLibraryBoundary(self.catalog,self.verifier)
        self.gateway=DurableLibraryApprovalGateway(boundary=self.boundary,
            verifier=self.verifier,ledger=self.ledger)
        self.identity=sign('identity',dict(issuer='authz',subject='reviewer',tenant_id='T-A',
            domain_id='TRADER',roles=['LIBRARY_REVIEWER'],action='APPROVE_INDEX'),IDENTITY_KEY)
        common=dict(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',version=1,
            sha256=SHA,license_kind='CC_BY',usage_scope='INTERNAL')
        self.approval=sign('approval',dict(common,issuer='human',reviewer='reviewer',
            action='APPROVE_INDEX',approval_id='APR-1'),APPROVAL_KEY)
        self.rights=sign('rights',dict(common,issuer='license',rights_holder='publisher',
            rights_action='INDEX',grant_id='G-1'),RIGHTS_KEY)

    def tearDown(self): self.directory.cleanup()

    def approve(self, **kwargs):
        data=dict(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,
            identity_envelope=self.identity,approval_envelope=self.approval,rights_envelope=self.rights)
        data.update(kwargs)
        return self.gateway.approve_for_indexing(**data)

    def service(self, *, roles=('LIBRARY_REVIEWER',), subject='reviewer'):
        bridge = ExternalIdentityBridge(
            verify_token=lambda token: VerifiedSession('https-idp','aion-service',subject,NOW-10,NOW+100),
            lookup_roles=lambda person,tenant,domain: roles if (tenant,domain)==('T-A','TRADER') else tuple(),
            trusted_issuer='https-idp',token_audience='aion-service',attestation_issuer='authz',
            signing_key=IDENTITY_KEY,clock=lambda:NOW)
        return AuthenticatedLibraryService(identities=bridge,boundary=self.boundary,approvals=self.gateway)

    def test_service_uses_external_identity_integration_to_approve(self):
        service=self.service()
        entry,decision=service.approve_for_indexing(token='synthetic-valid-token-12345',tenant_id='T-A',
            domain_id='TRADER',entry_id=self.entry.entry_id,
            approval_envelope=self.approval,rights_envelope=self.rights)
        self.assertEqual(entry.state,'APPROVED_FOR_INDEXING')
        self.assertEqual(decision.principal,'reviewer')
        self.assertTrue(self.ledger.burned(issuer='human',approval_id='APR-1'))

    def test_service_denies_insufficient_role_without_nonce_burn(self):
        service=self.service(roles=('LIBRARY_READER',))
        with self.assertRaises(AuthorizationDenied):
            service.approve_for_indexing(token='synthetic-valid-token-12345',tenant_id='T-A',
                domain_id='TRADER',entry_id=self.entry.entry_id,
                approval_envelope=self.approval,rights_envelope=self.rights)
        self.assertFalse(self.ledger.burned(issuer='human',approval_id='APR-1'))

    def test_service_read_scoped_through_membership(self):
        service=self.service(roles=('LIBRARY_READER',))
        found=service.read(token='synthetic-valid-token-12345',tenant_id='T-A',
            domain_id='TRADER',entry_id=self.entry.entry_id)
        self.assertEqual(found.entry_id,self.entry.entry_id)
        with self.assertRaises(AuthorizationDenied):
            service.read(token='synthetic-valid-token-12345',tenant_id='T-B',
                domain_id='TRADER',entry_id=self.entry.entry_id)

    def test_service_rejects_identity_not_matching_human_proof(self):
        service=self.service(subject='outsider')
        with self.assertRaises(AuthorizationDenied):
            service.approve_for_indexing(token='synthetic-valid-token-12345',tenant_id='T-A',
                domain_id='TRADER',entry_id=self.entry.entry_id,
                approval_envelope=self.approval,rights_envelope=self.rights)
        self.assertFalse(self.ledger.burned(issuer='human',approval_id='APR-1'))


    def test_valid_decision_burns_before_catalog_transition(self):
        entry,decision=self.approve()
        self.assertEqual(entry.state,'APPROVED_FOR_INDEXING')
        self.assertTrue(self.ledger.burned(issuer='human',approval_id='APR-1'))
        self.assertEqual(decision.principal,'reviewer')

    def test_replay_denied_after_reopening_sqlite(self):
        self.approve()
        reopened=SqliteApprovalBurnLedger(trusted_absolute_path=self.path)
        with self.assertRaises(AuthorizationDenied):
            reopened.burn(issuer='human',approval_id='APR-1',binding_sha256='b'*64)

    def test_burn_is_global_even_with_new_catalog_and_gateway(self):
        self.approve()
        catalog2=LibraryCatalog()
        entry=catalog2.register_document(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',
            version=1,sha256=SHA,source_type='BOOK',source_reference='isbn:123',
            license_kind='CC_BY',rights_holder='publisher',usage_scope='INTERNAL',human_approved_by='reviewer')
        catalog2.transition(tenant_id='T-A',domain_id='TRADER',entry_id=entry.entry_id,
            to_state='METADATA_REVIEW',actor='reviewer')
        newer=DurableLibraryApprovalGateway(boundary=SecuredLibraryBoundary(catalog2,self.verifier),
            verifier=self.verifier,ledger=SqliteApprovalBurnLedger(trusted_absolute_path=self.path))
        with self.assertRaises(AuthorizationDenied):
            newer.approve_for_indexing(tenant_id='T-A',domain_id='TRADER',entry_id=entry.entry_id,
                identity_envelope=self.identity,approval_envelope=self.approval,rights_envelope=self.rights)
        self.assertEqual(catalog2.get(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',version=1).state,
                         'METADATA_REVIEW')

    def test_invalid_signature_does_not_burn(self):
        bad=dict(self.approval,signature='0'*64)
        with self.assertRaises(AuthorizationDenied): self.approve(approval_envelope=bad)
        self.assertFalse(self.ledger.burned(issuer='human',approval_id='APR-1'))

    def test_wrong_tenant_does_not_burn(self):
        with self.assertRaises(AuthorizationDenied): self.approve(tenant_id='T-B')
        self.assertFalse(self.ledger.burned(issuer='human',approval_id='APR-1'))

    def test_wrong_rights_does_not_burn(self):
        wrong=sign('rights',dict(self.rights['payload'],rights_action='PUBLISH'),RIGHTS_KEY)
        with self.assertRaises(AuthorizationDenied): self.approve(rights_envelope=wrong)
        self.assertFalse(self.ledger.burned(issuer='human',approval_id='APR-1'))

    def test_invalid_scoped_identity_does_not_burn(self):
        wrong=sign('identity',dict(self.identity['payload'],roles=['LIBRARY_READER']),IDENTITY_KEY)
        with self.assertRaises(AuthorizationDenied): self.approve(identity_envelope=wrong)
        self.assertFalse(self.ledger.burned(issuer='human',approval_id='APR-1'))

    def test_same_approval_id_across_different_binding_denied(self):
        self.ledger.burn(issuer='human',approval_id='APR-1',binding_sha256='a'*64)
        with self.assertRaises(AuthorizationDenied): self.approve()
        self.assertEqual(self.catalog.get(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',version=1).state,
                         'METADATA_REVIEW')

    def test_reservation_persists_if_process_crashes_before_transition(self):
        self.ledger.burn(issuer='human',approval_id='APR-1',binding_sha256='a'*64)
        self.assertTrue(SqliteApprovalBurnLedger(trusted_absolute_path=self.path).burned(
            issuer='human',approval_id='APR-1'))
        with self.assertRaises(AuthorizationDenied): self.approve()

    def test_concurrent_consumption_is_exactly_once(self):
        def worker(_):
            ledger=SqliteApprovalBurnLedger(trusted_absolute_path=self.path)
            try:
                ledger.burn(issuer='human',approval_id='RACE-1',binding_sha256='f'*64)
                return 'accepted'
            except AuthorizationDenied:
                return 'blocked'
        with ThreadPoolExecutor(max_workers=8) as ex:
            result=list(ex.map(worker,range(16)))
        self.assertEqual(result.count('accepted'),1)
        self.assertEqual(result.count('blocked'),15)

    def test_does_not_store_raw_claims_or_tokens(self):
        self.approve()
        with closing(sqlite3.connect(self.path)) as db:
            rows=db.execute('SELECT * FROM burned_approvals').fetchall()
        self.assertEqual(len(rows),1)
        self.assertNotIn('reviewer',str(rows))
        self.assertNotIn('APR-1',str(rows))
        self.assertNotIn('publisher',str(rows))
        self.assertEqual(len(rows[0][0]),64)

    def test_nonabsolute_ledger_path_denied(self):
        with self.assertRaises(AuthorizationDenied):
            SqliteApprovalBurnLedger(trusted_absolute_path='relative.sqlite')

    def test_missing_parent_directory_denied(self):
        with self.assertRaises(AuthorizationDenied):
            SqliteApprovalBurnLedger(trusted_absolute_path=os.path.join(self.directory.name,'missing','db.sqlite'))

    def test_symlink_path_denied(self):
        symlink=os.path.join(self.directory.name,'linked.sqlite')
        try: os.symlink(self.path,symlink)
        except (OSError, NotImplementedError): self.skipTest('symlink unavailable')
        with self.assertRaises(AuthorizationDenied):
            SqliteApprovalBurnLedger(trusted_absolute_path=symlink)

    def test_schema_version_mismatch_denied(self):
        with closing(sqlite3.connect(self.path)) as db: db.execute('PRAGMA user_version = 19')
        with self.assertRaises(AuthorizationDenied):
            SqliteApprovalBurnLedger(trusted_absolute_path=self.path)

    def test_corrupt_sqlite_file_fails_closed(self):
        corrupted=os.path.join(self.directory.name,'corrupt.sqlite')
        with open(corrupted,'wb') as f: f.write(b'not-a-sqlite-database')
        with self.assertRaises(AuthorizationDenied):
            SqliteApprovalBurnLedger(trusted_absolute_path=corrupted)

    def test_ledger_burn_validates_issuer_and_binding(self):
        for kwargs in [dict(issuer='bad/issuer',approval_id='ID',binding_sha256='a'*64),
                       dict(issuer='human',approval_id='ID',binding_sha256='short')]:
            with self.assertRaises(AuthorizationDenied): self.ledger.burn(**kwargs)

    def test_unavailable_ledger_blocks_gateway(self):
        # Repoint only within this isolated fixture to simulate an unavailable DB.
        self.ledger._path=os.path.join(self.directory.name,'nonexistent','file.sqlite')
        with self.assertRaises(AuthorizationDenied): self.approve()
        self.assertEqual(self.catalog.get(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',version=1).state,
                         'METADATA_REVIEW')


if __name__ == '__main__': unittest.main()
