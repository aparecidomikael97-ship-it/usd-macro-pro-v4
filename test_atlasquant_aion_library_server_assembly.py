"""Adversarial unit tests for sandbox-only trusted host assembly.

The ACL and document DB interfaces are mocked here. Existing opt-in PG tests
cover the actual SQL and audit reader independently on ephemeral PostgreSQL.
"""
import unittest
from unittest.mock import Mock, patch

from atlasquant_access_control import AccessUser, authenticate, hash_password
from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_recovery_gate import IntegrityReport
from atlasquant_aion_library_postgres_preview import LibraryPanelPreview
from atlasquant_aion_library_server_assembly import SandboxLibraryServerReadAssembly

NOW = 2_000_000_000
IDENTITY = b'i' * 32
CHECKPOINT = b'c' * 32


class SandboxLibraryServerAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'OnlySyntheticTestPassword!'
        cls.pwhash = hash_password(cls.password, salt=b'assembly-salt-2026', iterations=200_000)

    def setUp(self):
        self.environment = ['SANDBOX']
        self.enabled = [True]
        self.users = {
            'reader.1': AccessUser('reader.1','USER',self.pwhash),
            'admin.1': AccessUser('admin.1','ADMIN',self.pwhash),
        }
        self.login('reader.1')
        self.membership = Mock()
        self.membership.roles_for = Mock(return_value=('LIBRARY_READER',))
        self.acl_connect = Mock(side_effect=AssertionError('constructor must not open ACL DB'))
        self.doc_connect = Mock(side_effect=AssertionError('only mock document inspection'))
        self.verifier = AttestationVerifier(
            identity_issuers={'aion-library-ci': IDENTITY},
            approval_issuers={'human-ci': b'h'*32},
            rights_issuers={'rights-ci': b'r'*32},
            clock=lambda:NOW,
        )
        self.report = IntegrityReport('TENANT-1','LIBRARY','ENTRY-1',1,
                                     'APPROVED_FOR_INDEXING','a'*64,2,'b'*64,2,'c'*64)

    def login(self, username):
        session = authenticate(username,self.password,self.users)
        self.assertIsNotNone(session)
        self.access = {'allowed':True,'mode':'AUTHENTICATED','role':session['role'],
                       'session':dict(session, authenticated_at=NOW-20,last_seen=NOW-1)}

    def new_service(self, **overrides):
        args=dict(
            environment_provider=lambda:self.environment[0],
            enabled_provider=lambda:self.enabled[0],
            access_provider=lambda:self.access,
            users_provider=lambda:self.users,
            acl_connect=self.acl_connect,
            document_connect=self.doc_connect,
            trusted_issuer='atlasquant.local',token_audience='library',
            attestation_issuer='aion-library-ci',identity_key=IDENTITY,
            verifier=self.verifier,checkpoint_key=CHECKPOINT,clock=lambda:NOW,
        )
        args.update(overrides)
        with patch('atlasquant_aion_library_server_assembly.PostgresLibraryMembership',
                   return_value=self.membership) as adapter:
            service=SandboxLibraryServerReadAssembly(**args)
        adapter.assert_called_once_with(connect=self.acl_connect)
        service._facade._gate.inspect = Mock(return_value=self.report)
        return service

    def read(self,service):
        return service.read_preview(tenant_id='TENANT-1',domain_id='LIBRARY',entry_id='ENTRY-1')

    def test_approved_metadata_with_explicit_scoped_reader(self):
        s=self.new_service()
        result=self.read(s)
        self.assertEqual(result,LibraryPanelPreview('ENTRY-1',1,'APPROVED_FOR_INDEXING',True))
        self.acl_connect.assert_not_called()
        self.doc_connect.assert_not_called()
        self.assertEqual(s._host._sessions,{})

    def test_no_implicit_constructor_network_or_document_access(self):
        s=self.new_service()
        self.assertIsNotNone(s)
        self.acl_connect.assert_not_called()
        self.doc_connect.assert_not_called()

    def test_environment_production_rejected_even_with_flag(self):
        self.environment[0]='PRODUCTION'
        with self.assertRaises(AuthorizationDenied):self.new_service()

    def test_environment_local_test_and_case_variant_denied(self):
        for value in ('LOCAL','TEST','sandbox','SANDBOX ',None,''):
            with self.subTest(value=value):
                self.environment[0]=value
                with self.assertRaises(AuthorizationDenied):self.new_service()

    def test_disabled_flag_rejected_before_assembly(self):
        self.enabled[0]=False
        with self.assertRaises(AuthorizationDenied):self.new_service()

    def test_truthy_nonboolean_flag_rejected(self):
        for value in (1,'true','yes',object()):
            with self.subTest(value=type(value).__name__):
                self.enabled[0]=value
                with self.assertRaises(AuthorizationDenied):self.new_service()

    def test_environment_switch_to_production_denied_before_read(self):
        s=self.new_service()
        self.environment[0]='PRODUCTION'
        with self.assertRaises(AuthorizationDenied):self.read(s)
        s._facade._gate.inspect.assert_not_called()

    def test_flag_switched_off_denied_before_read(self):
        s=self.new_service()
        self.enabled[0]=False
        with self.assertRaises(AuthorizationDenied):self.read(s)
        s._facade._gate.inspect.assert_not_called()

    def test_flag_switched_off_during_db_inspection_denied(self):
        s=self.new_service()
        def flip(**kwargs):
            self.enabled[0]=False
            return self.report
        s._facade._gate.inspect.side_effect=flip
        with self.assertRaises(AuthorizationDenied):self.read(s)
        self.assertEqual(s._host._sessions,{})

    def test_environment_switched_during_db_inspection_denied(self):
        s=self.new_service()
        def flip(**kwargs):
            self.environment[0]='PRODUCTION'
            return self.report
        s._facade._gate.inspect.side_effect=flip
        with self.assertRaises(AuthorizationDenied):self.read(s)

    def test_user_cannot_read_review_metadata(self):
        s=self.new_service()
        s._facade._gate.inspect.return_value=self.report.__class__(
            'TENANT-1','LIBRARY','ENTRY-1',1,'METADATA_REVIEW','a'*64,2,'b'*64,2,'c'*64)
        with self.assertRaises(AuthorizationDenied):self.read(s)

    def test_admin_without_explicit_membership_cannot_read(self):
        self.login('admin.1')
        s=self.new_service()
        self.membership.roles_for.return_value=()
        with self.assertRaises(AuthorizationDenied):self.read(s)
        s._facade._gate.inspect.assert_not_called()

    def test_revoked_membership_denied_on_second_request(self):
        s=self.new_service()
        self.read(s)
        self.membership.roles_for.return_value=()
        with self.assertRaises(AuthorizationDenied):self.read(s)

    def test_cross_tenant_denied_by_acl(self):
        s=self.new_service()
        def scoped(_user,tenant,domain):
            return ('LIBRARY_READER',) if (tenant,domain)==('TENANT-1','LIBRARY') else ()
        self.membership.roles_for.side_effect=scoped
        with self.assertRaises(AuthorizationDenied):
            s.read_preview(tenant_id='TENANT-2',domain_id='LIBRARY',entry_id='ENTRY-1')
        s._facade._gate.inspect.assert_not_called()

    def test_session_revoked_mid_read_denied(self):
        s=self.new_service()
        def revoke(**kwargs):
            self.users['reader.1']=AccessUser('reader.1','USER',self.pwhash,active=False)
            return self.report
        s._facade._gate.inspect.side_effect=revoke
        with self.assertRaises(AuthorizationDenied):self.read(s)

    def test_unavailable_db_denied_without_leaking_exception(self):
        s=self.new_service()
        s._facade._gate.inspect.side_effect=RuntimeError('synthetic-not-a-real-DSN')
        with self.assertRaises(AuthorizationDenied) as e:self.read(s)
        self.assertEqual(str(e.exception),'sandbox Library read unavailable')

    def test_missing_provider_denied(self):
        for key in ('environment_provider','enabled_provider','access_provider',
                    'users_provider','acl_connect','document_connect'):
            with self.subTest(key=key):
                with self.assertRaises(AuthorizationDenied):self.new_service(**{key:None})

    def test_missing_or_reused_signing_keys_denied(self):
        cases=({'identity_key':b'k'*15},{'checkpoint_key':b'x'*20},
               {'identity_key':CHECKPOINT},{'checkpoint_key':IDENTITY})
        for case in cases:
            with self.subTest(case=case.keys()):
                with self.assertRaises(AuthorizationDenied):self.new_service(**case)

    def test_wrong_attestation_verifier_denied_at_composition(self):
        bad=AttestationVerifier(identity_issuers={'aion-library-ci':b'x'*32},
                                approval_issuers={'human-ci':b'h'*32},
                                rights_issuers={'rights-ci':b'r'*32},clock=lambda:NOW)
        with self.assertRaises(AuthorizationDenied):self.new_service(verifier=bad)

    def test_no_document_routes_or_automatic_actions_exposed(self):
        s=self.new_service()
        for name in ('render','mount','publish','upload','approve','grant_role','migrate'):
            self.assertFalse(hasattr(s,name),name)


if __name__=='__main__':unittest.main()
