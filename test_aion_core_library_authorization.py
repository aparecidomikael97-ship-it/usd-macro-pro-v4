"""Adversarial offline boundary tests. Synthetic keys only, never deploy these fixtures."""
import hashlib
import hmac
import json
import unittest
from copy import deepcopy

from aion_core.library_authorization import (AUDIENCE, AttestationVerifier,
                                             SecuredLibraryBoundary, AuthorizationDenied)
from aion_core.library_foundation import LibraryCatalog

IDENTITY_KEY = b'i'*32
APPROVAL_KEY = b'a'*32
RIGHTS_KEY = b'r'*32
NOW = 2000000000
SHA = 'a'*64


def sign(kind, claims, key):
    data = dict(claims, kind=kind, audience=AUDIENCE, issued_at=NOW-10, expires_at=NOW+100)
    digest = hmac.new(key, json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('ascii'), hashlib.sha256).hexdigest()
    return {'payload': data, 'signature': digest}


class AuthorizationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.catalog = LibraryCatalog()
        self.entry = self.catalog.register_document(tenant_id='T-A', domain_id='TRADER',
                    document_id='DOC-1', version=1, sha256=SHA, source_type='BOOK',
                    source_reference='isbn:123', license_kind='CC_BY', rights_holder='publisher',
                    usage_scope='INTERNAL', human_approved_by='reviewer')
        self.catalog.transition(tenant_id='T-A', domain_id='TRADER', entry_id=self.entry.entry_id,
                                to_state='METADATA_REVIEW', actor='reviewer')
        self.now = NOW
        self.verifier = AttestationVerifier(identity_issuers={'authz': IDENTITY_KEY},
                     approval_issuers={'human': APPROVAL_KEY}, rights_issuers={'license': RIGHTS_KEY}, clock=lambda: self.now)
        self.boundary = SecuredLibraryBoundary(self.catalog, self.verifier)
        self.identity = sign('identity', {'issuer':'authz', 'subject':'reviewer','tenant_id':'T-A',
                        'domain_id':'TRADER','roles':['LIBRARY_REVIEWER'],'action':'APPROVE_INDEX'},IDENTITY_KEY)
        common = dict(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',version=1,
                      sha256=SHA,license_kind='CC_BY',usage_scope='INTERNAL')
        self.approval = sign('approval', dict(common, issuer='human', reviewer='reviewer',
                             action='APPROVE_INDEX',approval_id='APR-1'), APPROVAL_KEY)
        self.rights = sign('rights',dict(common,issuer='license',rights_holder='publisher',
                          rights_action='INDEX',grant_id='GRANT-1'),RIGHTS_KEY)

    def approve(self, **overrides):
        inputs={'tenant_id':'T-A','domain_id':'TRADER','entry_id':self.entry.entry_id,
                'identity_envelope':self.identity,'approval_envelope':self.approval,
                'rights_envelope':self.rights}
        inputs.update(overrides)
        return self.boundary.approve_for_indexing(**inputs)

    def denies(self, **overrides):
        with self.assertRaises(AuthorizationDenied):
            self.approve(**overrides)
        self.assertEqual('METADATA_REVIEW',self.catalog.get(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',version=1).state)

    def edit(self, envelope, key, **updates):
        claims=deepcopy(envelope['payload'])
        claims.update(updates)
        clean={k:v for k,v in claims.items() if k not in ('kind','audience','issued_at','expires_at')}
        new=sign(claims['kind'],clean,key)
        new['payload'].update({k:claims[k] for k in ('issued_at','expires_at','audience')})
        new['signature']=hmac.new(key,json.dumps(new['payload'],sort_keys=True,ensure_ascii=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
        return new

    def test_valid_signed_scoped_decision(self):
        entry, decision=self.approve()
        self.assertEqual(entry.state,'APPROVED_FOR_INDEXING')
        self.assertEqual(decision.principal,'reviewer')
        self.assertRegex(decision.decision_sha256,r'^[0-9a-f]{64}$')

    def test_unsigned_identity_denied(self): self.denies(identity_envelope={})
    def test_no_approval_denied(self): self.denies(approval_envelope={})
    def test_no_rights_grant_denied(self): self.denies(rights_envelope={})
    def test_tampered_identity_rejected(self):
        envelope=deepcopy(self.identity);envelope['payload']['roles']=['LIBRARY_ADMIN']
        self.denies(identity_envelope=envelope)
    def test_tampered_sha_rejected(self):
        envelope=deepcopy(self.approval);envelope['payload']['sha256']='b'*64
        self.denies(approval_envelope=envelope)
    def test_wrong_audience(self): self.denies(identity_envelope=self.edit(self.identity,IDENTITY_KEY,audience='other'))
    def test_unknown_identity_issuer(self): self.denies(identity_envelope=self.edit(self.identity,IDENTITY_KEY,issuer='unknown'))
    def test_cross_tenant_input(self): self.denies(tenant_id='T-B')
    def test_cross_domain_input(self): self.denies(domain_id='BUSINESS')
    def test_cross_tenant_signed_proof(self):
        self.denies(approval_envelope=self.edit(self.approval,APPROVAL_KEY,tenant_id='T-B'))
    def test_cross_domain_signed_proof(self):
        self.denies(rights_envelope=self.edit(self.rights,RIGHTS_KEY,domain_id='BUSINESS'))
    def test_wrong_content_sha(self): self.denies(rights_envelope=self.edit(self.rights,RIGHTS_KEY,sha256='b'*64))
    def test_wrong_version(self): self.denies(approval_envelope=self.edit(self.approval,APPROVAL_KEY,version=2))
    def test_wrong_usage_scope(self): self.denies(rights_envelope=self.edit(self.rights,RIGHTS_KEY,usage_scope='RESEARCH'))
    def test_wrong_reviewer(self): self.denies(approval_envelope=self.edit(self.approval,APPROVAL_KEY,reviewer='attacker'))
    def test_reader_role_cannot_approve(self):
        self.denies(identity_envelope=self.edit(self.identity,IDENTITY_KEY,roles=['LIBRARY_READER']))
    def test_wrong_identity_action(self):
        self.denies(identity_envelope=self.edit(self.identity,IDENTITY_KEY,action='READ'))
    def test_wrong_identity_subject(self):
        self.denies(identity_envelope=self.edit(self.identity,IDENTITY_KEY,subject='outsider'))
    def test_missing_rights_holder(self):
        self.denies(rights_envelope=self.edit(self.rights,RIGHTS_KEY,rights_holder='other'))
    def test_published_needs_publish_grant(self):
        entry=self.catalog.register_document(tenant_id='T-A',domain_id='TRADER',document_id='DOC-2',version=1,sha256='b'*64,
          source_type='BOOK',source_reference='isbn:456',license_kind='CC_BY',rights_holder='publisher',
          usage_scope='PUBLISHED',human_approved_by='reviewer')
        self.catalog.transition(tenant_id='T-A',domain_id='TRADER',entry_id=entry.entry_id,to_state='METADATA_REVIEW',actor='reviewer')
        app=self.edit(self.approval,APPROVAL_KEY,document_id='DOC-2',sha256='b'*64,usage_scope='PUBLISHED')
        rights=self.edit(self.rights,RIGHTS_KEY,document_id='DOC-2',sha256='b'*64,usage_scope='PUBLISHED')
        with self.assertRaises(AuthorizationDenied):
            self.approve(entry_id=entry.entry_id,approval_envelope=app,rights_envelope=rights)
        rights=self.edit(rights,RIGHTS_KEY,rights_action='PUBLISH')
        approved, _ = self.approve(entry_id=entry.entry_id,approval_envelope=app,rights_envelope=rights)
        self.assertEqual('APPROVED_FOR_INDEXING',approved.state)
    def test_expired_identity(self):
        self.denies(identity_envelope=self.edit(self.identity,IDENTITY_KEY,expires_at=NOW))
    def test_future_dated_approval(self):
        self.denies(approval_envelope=self.edit(self.approval,APPROVAL_KEY,issued_at=NOW+1,expires_at=NOW+100))
    def test_expired_rights(self):
        self.denies(rights_envelope=self.edit(self.rights,RIGHTS_KEY,expires_at=NOW))
    def test_reject_boolean_version(self):
        self.denies(approval_envelope=self.edit(self.approval,APPROVAL_KEY,version=True))
    def test_reject_boolean_timestamp(self):
        self.denies(identity_envelope=self.edit(self.identity,IDENTITY_KEY,issued_at=True))
    def test_bad_approval_action(self):
        self.denies(approval_envelope=self.edit(self.approval,APPROVAL_KEY,action='REVOKE'))
    def test_duplicate_replay(self):
        first, _=self.approve()
        # Second use of same signed decision for another matching doc/version is blocked by ID.
        self.assertEqual(first.state,'APPROVED_FOR_INDEXING')
        with self.assertRaises(AuthorizationDenied): self.approve()
    def test_read_role_scoped(self):
        ident=self.edit(self.identity,IDENTITY_KEY,roles=['LIBRARY_READER'],action='READ')
        self.assertEqual(self.entry.entry_id,self.boundary.read(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,identity_envelope=ident).entry_id)
        with self.assertRaises(AuthorizationDenied):
            self.boundary.read(tenant_id='T-B',domain_id='TRADER',entry_id=self.entry.entry_id,identity_envelope=ident)
        self.assertIsNone(self.boundary.read(tenant_id='T-A',domain_id='TRADER',entry_id='OTHER',identity_envelope=ident))
    def test_untrusted_key_configuration(self):
        with self.assertRaises(AuthorizationDenied):
            AttestationVerifier(identity_issuers={'i':IDENTITY_KEY},approval_issuers={'a':IDENTITY_KEY},rights_issuers={'r':RIGHTS_KEY})
    def test_unknown_extra_claim_rejected(self):
        invalid=deepcopy(self.identity);invalid['payload']['is_admin']=True
        self.denies(identity_envelope=invalid)
    def test_rights_grant_expiring_cannot_be_persisted(self):
        before=NOW+100
        grant=self.edit(self.rights,RIGHTS_KEY,expires_at=before)
        self.now=before
        self.denies(rights_envelope=grant)

if __name__=='__main__': unittest.main()
