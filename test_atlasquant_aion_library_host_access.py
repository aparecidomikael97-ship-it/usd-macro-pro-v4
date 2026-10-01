"""AtlasQuant real-login integration adapter sandbox negative contracts.

CI imports the ACTUAL default-branch atlasquant_access_control implementation.
LOCAL test fixture has an isolated compatible copy because the conversation
handoff contains the Library stack, not the entire AtlasQuant repository.
"""
from __future__ import annotations

import copy
import unittest

from atlasquant_access_control import (AccessUser, hash_password, authenticate,
    credential_fingerprint, ROLE_PERMISSIONS)
from atlasquant_aion_library_host_access import AtlasQuantLibraryHostAccess
from aion_core.library_authorization import (AuthorizationDenied, AttestationVerifier,
    SecuredLibraryBoundary)
from aion_core.library_foundation import LibraryCatalog

NOW = 2_000_000_000
PASSWORD = 'SyntheticSecurePass#2026'
HKEY = b'h' * 32
AKEY = b'a' * 32
RKEY = b'r' * 32


class ExistingAtlasQuantLibraryHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password(PASSWORD, salt=b'v'*16, iterations=200_000)

    def setUp(self):
        self.now = NOW
        self.users = {
            'mikael': AccessUser('mikael','ADMIN',self.password_hash),
            'client.1': AccessUser('client.1','USER',self.password_hash),
            'sales.1': AccessUser('sales.1','SALES',self.password_hash),
        }
        self.login('mikael')
        self.acl = {('mikael','TenantA','LIBRARY'):('LIBRARY_ADMIN',),
                    ('client.1','TenantA','LIBRARY'):('LIBRARY_READER',),
                    ('sales.1','TenantA','LIBRARY'):('LIBRARY_READER',)}
        self.host = self.make_host()

    def login(self, username, password=PASSWORD):
        session=authenticate(username,password,self.users)
        self.assertIsNotNone(session)
        self.session = dict(session, authenticated_at=self.now-30,last_seen=self.now-3)
        self.access={'allowed':True,'mode':'AUTHENTICATED','session':self.session,'role':session['role']}

    def make_host(self, **kwargs):
        params=dict(access_provider=lambda: self.access,users_provider=lambda: self.users,
              membership_provider=lambda username,tenant,domain:self.acl.get((username,tenant,domain),()),
              trusted_issuer='atlasquant.local',token_audience='aion-library-host',
              attestation_issuer='atlasquant-local-library',signing_key=HKEY,
              clock=lambda:self.now)
        params.update(kwargs)
        return AtlasQuantLibraryHostAccess(**params)

    def issue(self, **kwargs):
        args=dict(tenant_id='TenantA',domain_id='LIBRARY',action='READ')
        args.update(kwargs)
        return self.host.signed_identity_for_host(**args)

    def denies(self, **kwargs):
        with self.assertRaises(AuthorizationDenied):self.issue(**kwargs)

    def test_real_local_login_accepts_explicit_admin_membership(self):
        env=self.issue()
        self.assertEqual(env['payload']['subject'],'mikael')
        self.assertEqual(env['payload']['roles'],['LIBRARY_ADMIN'])
        self.assertEqual(env['payload']['tenant_id'],'TenantA')

    def test_proof_cryptographically_matches_downstream_verifier(self):
        env=self.issue()
        verifier=AttestationVerifier(identity_issuers={'atlasquant-local-library':HKEY},
                 approval_issuers={'human':AKEY},rights_issuers={'legal':RKEY},clock=lambda:self.now)
        payload=verifier.verify('identity',env)
        self.assertEqual(payload['action'],'READ')

    def test_signed_proof_reads_only_matching_catalog_scope(self):
        env=self.issue()
        c=LibraryCatalog()
        entry=c.register_document(tenant_id='TenantA',domain_id='LIBRARY',document_id='A',
                    version=1,sha256='a'*64,license_kind='CC0',source_type='BOOK',source_reference='isbn:xyz')
        other=c.register_document(tenant_id='TenantB',domain_id='LIBRARY',document_id='B',
                    version=1,sha256='b'*64,license_kind='CC0',source_type='BOOK',source_reference='isbn:other')
        v=AttestationVerifier(identity_issuers={'atlasquant-local-library':HKEY},
                 approval_issuers={'human':AKEY},rights_issuers={'legal':RKEY},clock=lambda:self.now)
        secured=SecuredLibraryBoundary(c,v)
        self.assertEqual(secured.read(tenant_id='TenantA',domain_id='LIBRARY',entry_id=entry.entry_id,identity_envelope=env).entry_id,entry.entry_id)
        with self.assertRaises(AuthorizationDenied):
            secured.read(tenant_id='TenantB',domain_id='LIBRARY',entry_id=other.entry_id,identity_envelope=env)

    def test_reader_cannot_read_unapproved_metadata(self):
        self.login('client.1')
        c=LibraryCatalog()
        entry=c.register_document(tenant_id='TenantA',domain_id='LIBRARY',document_id='A',
                    version=1,sha256='a'*64,license_kind='CC0',source_type='BOOK',source_reference='isbn:xyz')
        v=AttestationVerifier(identity_issuers={'atlasquant-local-library':HKEY},
                 approval_issuers={'human':AKEY},rights_issuers={'legal':RKEY},clock=lambda:self.now)
        secured=SecuredLibraryBoundary(c,v)
        self.assertIsNone(self.host.read_catalog_for_host(boundary=secured,tenant_id='TenantA',domain_id='LIBRARY',entry_id=entry.entry_id))
        self.login('mikael')
        self.assertEqual(self.host.read_catalog_for_host(boundary=secured,tenant_id='TenantA',domain_id='LIBRARY',entry_id=entry.entry_id).entry_id,entry.entry_id)

    def test_real_host_read_revalidates_membership_each_call(self):
        c=LibraryCatalog()
        entry=c.register_document(tenant_id='TenantA',domain_id='LIBRARY',document_id='A',
                    version=1,sha256='a'*64,license_kind='CC0',source_type='BOOK',source_reference='isbn:xyz')
        v=AttestationVerifier(identity_issuers={'atlasquant-local-library':HKEY},
                 approval_issuers={'human':AKEY},rights_issuers={'legal':RKEY},clock=lambda:self.now)
        secured=SecuredLibraryBoundary(c,v)
        self.assertIsNotNone(self.host.read_catalog_for_host(boundary=secured,tenant_id='TenantA',domain_id='LIBRARY',entry_id=entry.entry_id))
        self.acl.clear()
        with self.assertRaises(AuthorizationDenied):
            self.host.read_catalog_for_host(boundary=secured,tenant_id='TenantA',domain_id='LIBRARY',entry_id=entry.entry_id)

    def test_host_denies_untrusted_boundary(self):
        with self.assertRaises(AuthorizationDenied):
            self.host.read_catalog_for_host(boundary=None,tenant_id='TenantA',domain_id='LIBRARY',entry_id='any')

    def test_non_string_permissions_denied(self):
        self.session['permissions'].append(['admin'])
        self.denies()

    def test_nan_session_times_fail_closed(self):
        self.session['authenticated_at']=float('nan')
        self.denies()

    def test_open_mode_never_inherits_app_read_preview(self):
        self.access={'allowed':True,'mode':'OPEN','reason':'AUTH_DISABLED'}
        self.denies()

    def test_bootstrap_preview_never_inherits_permission(self):
        self.access={'allowed':True,'mode':'PREVIEW','read_only':True}
        self.denies()

    def test_login_locked_or_denied(self):
        self.access={'allowed':False,'mode':'LOGIN'}
        self.denies()

    def test_claim_only_session_no_registry(self):
        self.users={}
        self.denies()

    def test_registry_revocation_invalidates_live_handle(self):
        handle=self.host._new_handle()
        self.users['mikael']=AccessUser('mikael','ADMIN',self.password_hash,active=False)
        self.denies()
        with self.assertRaises(AuthorizationDenied):self.host._verify_handle(handle)

    def test_registry_password_rotation_revokes_existing_session(self):
        self.users['mikael']=AccessUser('mikael','ADMIN',hash_password('DifferentSecurePass#2026',salt=b'z'*16,iterations=200000))
        self.denies()

    def test_role_change_revokes_existing_session(self):
        self.users['mikael']=AccessUser('mikael','USER',self.password_hash)
        self.denies()

    def test_access_role_mismatch_denied(self):
        self.access['role']='USER'
        self.denies()

    def test_session_perm_injection_denied(self):
        self.session['permissions'] += ['aion:secret']
        self.denies()

    def test_session_permission_missing_denied(self):
        self.session['permissions']=[]
        self.denies()

    def test_session_fingerprint_mismatch_denied(self):
        self.session['credential_fingerprint']='a'*24
        self.denies()

    def test_missing_session_timestamps_denied(self):
        self.session.pop('authenticated_at')
        self.denies()

    def test_idle_session_denied(self):
        self.session['last_seen']=self.now-7201
        self.denies()

    def test_absolute_session_age_denied(self):
        self.session['authenticated_at']=self.now-43201
        self.session['last_seen']=self.now-1
        self.denies()

    def test_future_session_denied(self):
        self.session['last_seen']=self.now+10
        self.denies()

    def test_no_implicit_admin_cross_tenant(self):
        self.denies(tenant_id='TenantB')

    def test_domain_specific_acl(self):
        self.denies(domain_id='BUSINESS')

    def test_user_reader_only_with_explicit_membership(self):
        self.login('client.1')
        r=self.issue()
        self.assertEqual(r['payload']['roles'],['LIBRARY_READER'])
        self.denies(action='APPROVE_INDEX')
        self.denies(tenant_id='TenantB')

    def test_sales_reader_only_with_explicit_membership(self):
        self.login('sales.1')
        self.assertEqual(self.issue()['payload']['roles'],['LIBRARY_READER'])
        self.denies(action='APPROVE_INDEX')

    def test_client_acl_cannot_self_elevate(self):
        self.login('client.1')
        self.acl[('client.1','TenantA','LIBRARY')]=('LIBRARY_ADMIN',)
        self.denies()

    def test_admin_approval_requires_explicit_acl(self):
        self.acl[('mikael','TenantA','LIBRARY')]=('LIBRARY_READER',)
        self.denies(action='APPROVE_INDEX')
        self.acl[('mikael','TenantA','LIBRARY')]=('LIBRARY_REVIEWER',)
        self.assertEqual(self.issue(action='APPROVE_INDEX')['payload']['roles'],['LIBRARY_REVIEWER'])

    def test_acl_revocation_between_operations(self):
        handle=self.host._new_handle()
        self.acl.clear()
        with self.assertRaises(AuthorizationDenied):
            self.host.identity_bridge.identity_envelope(token=handle,tenant_id='TenantA',domain_id='LIBRARY',action='READ')

    def test_acl_callback_failure_is_fail_closed(self):
        def fail(*args):raise ConnectionError('PRIVATE ACL DB CONNECTION')
        self.host=self.make_host(membership_provider=fail)
        with self.assertRaises(AuthorizationDenied) as err:self.issue()
        self.assertNotIn('PRIVATE',str(err.exception))

    def test_access_provider_failure_is_fail_closed(self):
        self.host=self.make_host(access_provider=lambda:1/0)
        self.denies()

    def test_expired_ephemeral_handle_denied(self):
        handle=self.host._new_handle()
        self.now+=121
        with self.assertRaises(AuthorizationDenied):self.host._verify_handle(handle)

    def test_identity_handle_rejected_after_user_switch(self):
        handle=self.host._new_handle()
        self.login('client.1')
        with self.assertRaises(AuthorizationDenied):self.host._verify_handle(handle)

    def test_handle_never_exposed_in_signed_identity(self):
        env=self.issue()
        self.assertEqual(set(env),{'payload','signature'})
        self.assertNotIn('token',repr(env).lower())

    def test_role_acl_revalidated_on_each_identity_claim(self):
        env=self.issue()
        self.acl.clear()
        self.denies()
        self.assertEqual(env['payload']['roles'],['LIBRARY_ADMIN'])
        # IMPORTANT: previously signed claims remain valid until TTL. Production
        # must additionally revoke via verifier/ACL at each protected DB request.

    def test_unknown_action_denied(self):
        self.denies(action='UPDATE')

    def test_invalid_trusted_config_denied(self):
        with self.assertRaises(AuthorizationDenied):
            self.make_host(signing_key=b'too-short')

    def test_invalid_clock_denied(self):
        self.host=self.make_host(clock=lambda:True)
        self.denies()

    def test_login_session_revalidation_not_auth_from_user_body(self):
        self.login('client.1')
        self.access['session']=dict(self.session,username='mikael',role='ADMIN')
        self.access['role']='ADMIN'
        self.denies()

    def test_access_mapping_missing_denied(self):
        self.access=None
        self.denies()


if __name__=='__main__':unittest.main()
