"""Offline tests for the unmounted app-facing PG preview security boundary."""
import unittest
from dataclasses import replace
from unittest.mock import Mock

from atlasquant_access_control import AccessUser, authenticate, hash_password
from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess
from atlasquant_aion_library_postgres_preview import (
    LibraryPanelPreview, LibraryPostgresReadFacade,
)
from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_recovery_gate import IntegrityReport

NOW = 2_000_000_000
KEY, HUMAN, RIGHTS, CHECKPOINT = b'i'*32, b'p'*32, b'r'*32, b'c'*32


class PostgresPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = 'SyntheticUnitPassword!'
        cls.pw_hash = hash_password(cls.pw, salt=b'x'*16, iterations=200_000)

    def setUp(self):
        self.now = NOW
        self.users = {
            'admin.1': AccessUser('admin.1', 'ADMIN', self.pw_hash),
            'reader.1': AccessUser('reader.1', 'USER', self.pw_hash),
            'sales.1': AccessUser('sales.1', 'SALES', self.pw_hash),
        }
        self.members = {
            ('admin.1', 'T-A', 'LIBRARY'): ('LIBRARY_ADMIN',),
            ('reader.1', 'T-A', 'LIBRARY'): ('LIBRARY_READER',),
            ('sales.1', 'T-A', 'LIBRARY'): ('LIBRARY_READER',),
        }
        self.sign_in('admin.1')
        self.host = AtlasQuantLibraryHostAccess(
            access_provider=lambda: self.access,
            users_provider=lambda: self.users,
            membership_provider=lambda s,t,d: self.members.get((s,t,d),()),
            trusted_issuer='atlasquant.local', token_audience='library',
            attestation_issuer='atlasquant-library', signing_key=KEY,
            clock=lambda: self.now,
        )
        self.verifier = AttestationVerifier(
            identity_issuers={'atlasquant-library': KEY},
            approval_issuers={'human': HUMAN},
            rights_issuers={'license': RIGHTS}, clock=lambda: self.now,
        )
        self.connect = Mock(side_effect=AssertionError('mock inspect must not connect'))
        self.svc = LibraryPostgresReadFacade(
            host=self.host, verifier=self.verifier, connect=self.connect,
            checkpoint_key=CHECKPOINT, clock=lambda: self.now,
        )
        self.report = IntegrityReport('T-A','LIBRARY','LIB-1',1,'APPROVED_FOR_INDEXING',
                        'a'*64,2,'b'*64,2,'c'*64)
        self.inspector = self.svc._gate.inspect = Mock(return_value=self.report)

    def sign_in(self, name):
        session = authenticate(name, self.pw, self.users)
        self.assertIsNotNone(session)
        self.session = dict(session, authenticated_at=self.now-20,last_seen=self.now-1)
        self.access = dict(allowed=True,mode='AUTHENTICATED',session=self.session,role=session['role'])

    def preview(self, **overrides):
        params = dict(tenant_id='T-A',domain_id='LIBRARY',entry_id='LIB-1')
        params.update(overrides)
        return self.svc.read_preview(**params)

    def denies(self, **kwargs):
        with self.assertRaises(AuthorizationDenied) as err:
            self.preview(**kwargs)
        self.assertEqual(str(err.exception), 'library read unavailable or access denied')

    def test_admin_can_view_verified_approved_metadata(self):
        val=self.preview()
        self.assertEqual(val,LibraryPanelPreview('LIB-1',1,'APPROVED_FOR_INDEXING',True))
        self.assertNotIn('content_sha256',val.__dict__)
        self.inspector.assert_called_once()
        self.connect.assert_not_called()

    def test_ordinary_reader_can_view_approved(self):
        self.sign_in('reader.1')
        self.assertEqual(self.preview().state,'APPROVED_FOR_INDEXING')

    def test_sales_can_view_approved_with_explicit_membership(self):
        self.sign_in('sales.1')
        self.assertTrue(self.preview().integrity_checked)

    def test_reader_denied_for_review_state(self):
        self.sign_in('reader.1')
        self.inspector.return_value=replace(self.report,state='METADATA_REVIEW')
        self.denies()

    def test_sales_denied_for_review_state(self):
        self.sign_in('sales.1')
        self.inspector.return_value=replace(self.report,state='METADATA_REVIEW')
        self.denies()

    def test_admin_with_explicit_membership_can_inspect_review(self):
        self.inspector.return_value=replace(self.report,state='METADATA_REVIEW')
        self.assertEqual(self.preview().state,'METADATA_REVIEW')

    def test_admin_without_acl_denied(self):
        self.members.clear()
        self.denies()
        self.inspector.assert_not_called()

    def test_admin_other_client_denied(self):
        self.denies(tenant_id='T-B')
        self.inspector.assert_not_called()

    def test_other_domain_denied(self):
        self.denies(domain_id='NEGOCIOS')
        self.inspector.assert_not_called()

    def test_open_mode_denied(self):
        self.access={'allowed':True,'mode':'OPEN'}
        self.denies()

    def test_bootstrap_preview_denied(self):
        self.access={'allowed':True,'mode':'PREVIEW'}
        self.denies()

    def test_user_switch_mid_read_denied(self):
        def switch(**kw):
            self.sign_in('reader.1')
            return self.report
        self.inspector.side_effect=switch
        self.denies()

    def test_registry_revoked_mid_read_denied(self):
        def revoke(**kw):
            self.users['admin.1']=AccessUser('admin.1','ADMIN',self.pw_hash,active=False)
            return self.report
        self.inspector.side_effect=revoke
        self.denies()

    def test_acl_revoked_mid_read_denied(self):
        def revoke(**kw):
            self.members.clear()
            return self.report
        self.inspector.side_effect=revoke
        self.denies()

    def test_acl_role_downgraded_mid_read_denied_for_review(self):
        self.inspector.return_value=replace(self.report,state='METADATA_REVIEW')
        def downgrade(**kw):
            self.members[('admin.1','T-A','LIBRARY')]=('LIBRARY_READER',)
            return self.inspector.return_value
        self.inspector.side_effect=downgrade
        self.denies()

    def test_wrong_scope_from_integrity_gate_is_denied(self):
        self.inspector.return_value=replace(self.report, tenant_id='T-B')
        self.denies()

    def test_wrong_entry_from_integrity_gate_is_denied(self):
        self.inspector.return_value=replace(self.report, entry_id='LIB-OTHER')
        self.denies()

    def test_wrong_state_from_integrity_gate_is_denied(self):
        self.inspector.return_value=replace(self.report, state='REVOKED')
        self.denies()

    def test_invalid_scope_is_denied_before_db(self):
        for bad in (None,'','T-A;DROP',42,'A'*129):
            with self.subTest(bad=bad):
                self.denies(tenant_id=bad)
                self.denies(domain_id=bad)
                self.denies(entry_id=bad)
        self.inspector.assert_not_called()

    def test_verifier_mismatch_rejected_at_construction(self):
        wrong=AttestationVerifier(identity_issuers={'atlasquant-library': b'x'*32},
            approval_issuers={'human': HUMAN},rights_issuers={'license': RIGHTS},
            clock=lambda:self.now)
        with self.assertRaises(AuthorizationDenied):
            LibraryPostgresReadFacade(host=self.host,verifier=wrong,connect=self.connect,
                                      checkpoint_key=CHECKPOINT,clock=lambda:self.now)

    def test_unknown_identity_issuer_rejected_at_construction(self):
        wrong=AttestationVerifier(identity_issuers={'other': b'x'*32},
            approval_issuers={'human': HUMAN},rights_issuers={'license': RIGHTS},
            clock=lambda:self.now)
        with self.assertRaises(AuthorizationDenied):
            LibraryPostgresReadFacade(host=self.host,verifier=wrong,connect=self.connect,
                                      checkpoint_key=CHECKPOINT,clock=lambda:self.now)

    def test_bad_host_rejected(self):
        with self.assertRaises(AuthorizationDenied):
            LibraryPostgresReadFacade(host=None,verifier=self.verifier,connect=self.connect,
                                      checkpoint_key=CHECKPOINT)

    def test_reused_signing_key_for_checkpoint_denied(self):
        with self.assertRaises(AuthorizationDenied):
            LibraryPostgresReadFacade(host=self.host,verifier=self.verifier,connect=self.connect,
                                      checkpoint_key=KEY)

    def test_invalid_connect_factory_rejected(self):
        with self.assertRaises(AuthorizationDenied):
            LibraryPostgresReadFacade(host=self.host,verifier=self.verifier,connect=None,
                                      checkpoint_key=CHECKPOINT)

    def test_db_error_denied_without_details(self):
        self.inspector.side_effect=ConnectionError('SECRET-db-connection-string')
        self.denies()

    def test_integrity_error_denied(self):
        self.inspector.side_effect=AuthorizationDenied('audit content corrupted')
        self.denies()

    def test_no_legacy_catalog_dependency(self):
        self.assertFalse(hasattr(self.svc,'_catalog'))
        self.assertIs(self.svc._gate._identities,self.host.identity_bridge)

    def test_untrusted_end_user_has_no_api_access(self):
        self.assertFalse(hasattr(self.svc,'render'))
        self.assertFalse(hasattr(self.svc,'mount'))
        self.assertFalse(hasattr(self.svc,'publish'))

    def test_handles_consumed_after_request(self):
        self.preview()
        self.assertEqual(self.host._sessions,{})

    def test_handles_consumed_on_failure(self):
        self.inspector.side_effect=ValueError('injected')
        self.denies()
        self.assertEqual(self.host._sessions,{})

    def test_unapproved_admin_absent_member_cannot_view(self):
        self.inspector.return_value=replace(self.report,state='METADATA_REVIEW')
        self.members.clear()
        self.denies()

    def test_forged_role_in_session_denied(self):
        self.session['role']='SUPERADMIN'
        self.access['role']='SUPERADMIN'
        self.denies()

    def test_password_rotation_denied_mid_read(self):
        def rotate(**kw):
            new_hash=hash_password('AnotherNewSecurePassword#', salt=b'y'*16,iterations=200_000)
            self.users['admin.1']=AccessUser('admin.1','ADMIN',new_hash)
            return self.report
        self.inspector.side_effect=rotate
        self.denies()


if __name__ == '__main__': unittest.main()
