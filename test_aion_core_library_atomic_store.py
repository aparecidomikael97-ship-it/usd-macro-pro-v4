"""Adversarial, entirely synthetic SQLite DB-API simulator tests for atomic port.

These validate transaction contracts but NOT PostgreSQL locking semantics.
A separate ephemeral-PostgreSQL GitHub Actions job tests the actual dialect.
"""
import hashlib
import hmac
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from aion_core.library_foundation import LibraryCatalog
from aion_core.library_authorization import AUDIENCE, AttestationVerifier, AuthorizationDenied
from aion_core.library_atomic_store import AtomicLibraryStore, MIGRATION_POSTGRESQL

NOW = 2000000000
IK, AK, RK = b'i' * 32, b'a' * 32, b'r' * 32
S = 'a' * 64


def sign(kind, claims, key, now=NOW):
    claims = dict(claims, kind=kind, audience=AUDIENCE, issued_at=now-10, expires_at=now+100)
    sig = hmac.new(key, json.dumps(claims, sort_keys=True, ensure_ascii=True,
                    separators=(',', ':')).encode('ascii'), hashlib.sha256).hexdigest()
    return {'payload': claims, 'signature': sig}


def make_proofs(entry, nonce='APR-1', rights_action='INDEX'):
    common = dict(tenant_id=entry.tenant_id, domain_id=entry.domain_id,
                  document_id=entry.document_id, version=entry.version, sha256=entry.sha256,
                  license_kind=entry.license_kind, usage_scope=entry.usage_scope)
    ident = sign('identity', dict(issuer='authz', subject='reviewer', tenant_id=entry.tenant_id,
                 domain_id=entry.domain_id, roles=['LIBRARY_REVIEWER'], action='APPROVE_INDEX'), IK)
    approval = sign('approval', dict(common, issuer='human', reviewer='reviewer',
                    action='APPROVE_INDEX', approval_id=nonce), AK)
    rights = sign('rights', dict(common, issuer='license', rights_holder=entry.rights_holder,
                  rights_action=rights_action, grant_id='GRANT-1'), RK)
    return ident, approval, rights


class Cursor:
    def __init__(self, inner, fail_event=False):
        self.inner = inner
        self.fail_event = fail_event

    def execute(self, sql, params):
        if self.fail_event and 'INSERT INTO aion_library_atomic_audit' in sql and params[3] == 'APPROVE_INDEX':
            raise sqlite3.OperationalError('simulated audit failure')
        sql = sql.replace('%s', '?').replace(' FOR UPDATE', '')
        return self.inner.execute(sql, params)

    def fetchone(self):
        return self.inner.fetchone()

    @property
    def rowcount(self):
        return self.inner.rowcount

    def close(self):
        self.inner.close()


class Connection:
    autocommit = False

    def __init__(self, path, *, fail_event=False):
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('BEGIN IMMEDIATE')  # Serialize SQLite test doubles; PostgreSQL uses row locks.
        self.fail_event = fail_event

    def cursor(self):
        return Cursor(self.db.cursor(), self.fail_event)

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def close(self):
        self.db.close()


SCHEMA = '''
CREATE TABLE aion_library_documents (
  entry_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, domain_id TEXT NOT NULL,
  document_id TEXT NOT NULL, version INTEGER NOT NULL, content_sha256 TEXT NOT NULL,
  license_kind TEXT NOT NULL, usage_scope TEXT NOT NULL, rights_holder TEXT NOT NULL,
  human_approved_by TEXT NOT NULL, source_type TEXT NOT NULL, source_reference TEXT NOT NULL,
  state TEXT NOT NULL, UNIQUE(tenant_id,domain_id,document_id,version));
CREATE TABLE aion_library_atomic_approval_burns (
  approval_key TEXT PRIMARY KEY, binding_sha256 TEXT NOT NULL, burned_at_unix INTEGER NOT NULL);
CREATE TABLE aion_library_atomic_audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, entry_id TEXT NOT NULL,
  prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL, event_type TEXT NOT NULL,
  state_from TEXT NOT NULL, state_to TEXT NOT NULL, approval_key TEXT NOT NULL,
  recorded_at_unix INTEGER NOT NULL, FOREIGN KEY(entry_id) REFERENCES aion_library_documents(entry_id));
'''


class AtomicStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = str(Path(self.tmp.name) / 'synthetic.sqlite3')
        with closing(sqlite3.connect(self.db_path)) as db, db:
            db.executescript(SCHEMA)
        self.fail_event = False
        self.factory = lambda: Connection(self.db_path, fail_event=self.fail_event)
        self.verifier = AttestationVerifier(identity_issuers={'authz':IK}, approval_issuers={'human':AK},
                       rights_issuers={'license':RK}, clock=lambda: NOW)
        self.store = AtomicLibraryStore(connect=self.factory, verifier=self.verifier, clock=lambda: NOW)
        catalog = LibraryCatalog()
        self.entry = catalog.register_document(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',
                     version=1,sha256=S,source_type='BOOK',source_reference='isbn:123',
                     license_kind='CC_BY',rights_holder='publisher',usage_scope='INTERNAL',
                     human_approved_by='reviewer')
        self.entry = catalog.transition(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,
                                        to_state='METADATA_REVIEW',actor='reviewer')
        self.proofs = make_proofs(self.entry)

    def rows(self, table):
        assert table in {'aion_library_documents','aion_library_atomic_approval_burns','aion_library_atomic_audit'}
        with closing(sqlite3.connect(self.db_path)) as db, db:
            return db.execute('SELECT * FROM '+table).fetchall()

    def approve(self, *, store=None, proofs=None, tenant_id='T-A', domain_id='TRADER', entry_id=None):
        i, a, r = proofs if proofs is not None else self.proofs
        return (store or self.store).approve(tenant_id=tenant_id,domain_id=domain_id,
            entry_id=entry_id or self.entry.entry_id,identity_envelope=i,
            approval_envelope=a,rights_envelope=r)

    def imported(self):
        self.store.import_reviewed(trusted_entry=self.entry)

    def test_migration_is_declarative_postgres(self):
        self.assertIn('CREATE TABLE aion_library_atomic_audit', MIGRATION_POSTGRESQL)
        self.assertIn('PRIMARY KEY', MIGRATION_POSTGRESQL)
        self.assertNotIn('DROP TABLE', MIGRATION_POSTGRESQL)

    def test_import_document_and_genesis_one_tx(self):
        self.imported()
        self.assertEqual(len(self.rows('aion_library_documents')),1)
        self.assertEqual(len(self.rows('aion_library_atomic_audit')),1)
        self.assertEqual(self.rows('aion_library_atomic_audit')[0][4],'GENESIS')

    def test_approval_commits_all_three(self):
        self.imported()
        receipt=self.approve()
        self.assertEqual(receipt.state,'APPROVED_FOR_INDEXING')
        self.assertEqual(len(self.rows('aion_library_atomic_approval_burns')),1)
        self.assertEqual(len(self.rows('aion_library_atomic_audit')),2)
        self.assertEqual(self.rows('aion_library_documents')[0][-1],'APPROVED_FOR_INDEXING')
        self.assertEqual(receipt.audit_hash,self.rows('aion_library_atomic_audit')[-1][3])
        self.assertEqual(self.rows('aion_library_atomic_audit')[1][2],self.rows('aion_library_atomic_audit')[0][3])

    def test_duplicate_import_rolls_back(self):
        self.imported()
        with self.assertRaises(AuthorizationDenied): self.imported()
        self.assertEqual(len(self.rows('aion_library_atomic_audit')),1)

    def test_missing_document_denied_without_burn(self):
        with self.assertRaises(AuthorizationDenied): self.approve()
        self.assertEqual(len(self.rows('aion_library_atomic_approval_burns')),0)

    def test_cross_tenant_denied(self):
        self.imported()
        with self.assertRaises(AuthorizationDenied): self.approve(tenant_id='T-B')
        self.assertEqual(len(self.rows('aion_library_atomic_approval_burns')),0)

    def test_cross_domain_denied(self):
        self.imported()
        with self.assertRaises(AuthorizationDenied): self.approve(domain_id='BUSINESS')
        self.assertEqual(len(self.rows('aion_library_atomic_audit')),1)

    def test_wrong_entry_id_denied(self):
        self.imported()
        with self.assertRaises(AuthorizationDenied): self.approve(entry_id='LIB-OTHER')

    def test_unauthorized_role_denied(self):
        self.imported()
        i,a,r=self.proofs
        claims={k:v for k,v in i['payload'].items() if k not in {'kind','audience','issued_at','expires_at'}}
        bad=sign('identity',dict(claims,roles=['LIBRARY_READER']),IK)
        # No bypass via user-supplied lower role.
        with self.assertRaises(AuthorizationDenied):self.approve(proofs=(bad,a,r))
        self.assertEqual(self.rows('aion_library_atomic_approval_burns'),[])

    def test_approval_digest_tamper_denied(self):
        self.imported()
        i,a,r=self.proofs
        bad=dict(a,payload=dict(a['payload'],sha256='b'*64))
        with self.assertRaises(AuthorizationDenied):self.approve(proofs=(i,bad,r))
        self.assertEqual(self.rows('aion_library_atomic_approval_burns'),[])

    def test_wrong_signer_subject_denied(self):
        self.imported()
        i,a,r=self.proofs
        claims={k:v for k,v in i['payload'].items() if k not in {'kind','audience','issued_at','expires_at'}}
        with self.assertRaises(AuthorizationDenied): self.approve(proofs=(sign('identity',dict(claims,subject='outsider'),IK),a,r))

    def test_rights_scope_mismatch_denied(self):
        self.imported()
        i,a,r=self.proofs
        claims={k:v for k,v in r['payload'].items() if k not in {'kind','audience','issued_at','expires_at'}}
        bad=sign('rights',dict(claims,rights_action='PUBLISH'),RK)
        with self.assertRaises(AuthorizationDenied):self.approve(proofs=(i,a,bad))

    def test_read_only_license_denied(self):
        cat=LibraryCatalog()
        entry=cat.register_document(tenant_id='T-A',domain_id='TRADER',document_id='DOC-2',version=1,
               sha256='b'*64,source_type='BOOK',source_reference='isbn:456',license_kind='ALL_RIGHTS_RESERVED',
               rights_holder='publisher',usage_scope='INTERNAL',human_approved_by='reviewer')
        entry=cat.transition(tenant_id='T-A',domain_id='TRADER',entry_id=entry.entry_id,to_state='METADATA_REVIEW',actor='reviewer')
        self.store.import_reviewed(trusted_entry=entry)
        with self.assertRaises(AuthorizationDenied):self.approve(entry_id=entry.entry_id,proofs=make_proofs(entry))
        self.assertEqual(len(self.rows('aion_library_atomic_approval_burns')),0)

    def test_expiry_after_db_lock_denied_before_burn(self):
        self.imported()
        current=[NOW]
        verifier=AttestationVerifier(identity_issuers={'authz':IK},approval_issuers={'human':AK},
            rights_issuers={'license':RK},clock=lambda:current[0])
        def delayed_connection():
            current[0]=NOW+100  # proof expires as the DB lock is acquired
            return Connection(self.db_path)
        store=AtomicLibraryStore(connect=delayed_connection,verifier=verifier,clock=lambda:current[0])
        with self.assertRaises(AuthorizationDenied):self.approve(store=store)
        self.assertEqual(self.rows('aion_library_atomic_approval_burns'),[])
        self.assertEqual(self.rows('aion_library_documents')[0][-1],'METADATA_REVIEW')

    def test_expired_attestation_denied(self):
        self.imported()
        i,a,r=self.proofs
        claims={k:v for k,v in i['payload'].items() if k not in {'kind','audience','issued_at','expires_at'}}
        ident=sign('identity',claims,IK,now=NOW-1000)
        with self.assertRaises(AuthorizationDenied):self.approve(proofs=(ident,a,r))

    def test_missing_audit_genesis_denies_no_burn(self):
        self.imported()
        with closing(sqlite3.connect(self.db_path)) as db, db: db.execute('DELETE FROM aion_library_atomic_audit')
        with self.assertRaises(AuthorizationDenied):self.approve()
        self.assertEqual(len(self.rows('aion_library_atomic_approval_burns')),0)

    def test_tampered_genesis_denies(self):
        self.imported()
        with closing(sqlite3.connect(self.db_path)) as db, db: db.execute("UPDATE aion_library_atomic_audit SET event_hash=?",('b'*64,))
        with self.assertRaises(AuthorizationDenied):self.approve()

    def test_audit_insert_failure_rolls_back_all(self):
        self.imported()
        self.fail_event=True
        with self.assertRaises(AuthorizationDenied):self.approve()
        self.assertEqual(len(self.rows('aion_library_atomic_approval_burns')),0)
        self.assertEqual(self.rows('aion_library_documents')[0][-1],'METADATA_REVIEW')
        self.assertEqual(len(self.rows('aion_library_atomic_audit')),1)
        self.fail_event=False
        self.assertEqual(self.approve().state,'APPROVED_FOR_INDEXING')

    def test_burn_insert_failure_rolls_back_all(self):
        self.imported()
        with closing(sqlite3.connect(self.db_path)) as db, db: db.execute('DROP TABLE aion_library_atomic_approval_burns')
        with self.assertRaises(AuthorizationDenied):self.approve()
        self.assertEqual(self.rows('aion_library_documents')[0][-1],'METADATA_REVIEW')
        self.assertEqual(len(self.rows('aion_library_atomic_audit')),1)

    def test_db_unavailable_fail_closed(self):
        self.imported()
        s=AtomicLibraryStore(connect=lambda: (_ for _ in ()).throw(ConnectionError('secret-hostname')),
             verifier=self.verifier,clock=lambda:NOW)
        with self.assertRaises(AuthorizationDenied) as ctx:self.approve(store=s)
        self.assertNotIn('secret-hostname',str(ctx.exception))
        self.assertEqual(self.rows('aion_library_atomic_approval_burns'),[])

    def test_autocommit_connection_denied(self):
        self.imported()
        class Wrong(Connection):
            autocommit=True
        s=AtomicLibraryStore(connect=lambda:Wrong(self.db_path),verifier=self.verifier,clock=lambda:NOW)
        with self.assertRaises(AuthorizationDenied):self.approve(store=s)
        self.assertEqual(len(self.rows('aion_library_atomic_audit')),1)

    def test_duplicate_replay_after_restart_denied(self):
        self.imported()
        self.approve()
        s=AtomicLibraryStore(connect=self.factory,verifier=self.verifier,clock=lambda:NOW)
        with self.assertRaises(AuthorizationDenied):self.approve(store=s)
        self.assertEqual(len(self.rows('aion_library_atomic_approval_burns')),1)

    def test_concurrent_approvals_one_wins(self):
        self.imported()
        with ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(lambda _:self._safe_approve(),range(6)))
        self.assertEqual(results.count('success'),1,results)
        self.assertEqual(results.count('denied'),5,results)
        self.assertEqual(len(self.rows('aion_library_atomic_audit')),2)

    def _safe_approve(self):
        try:self.approve();return 'success'
        except AuthorizationDenied:return 'denied'

    def test_invalid_ids_denied(self):
        for scope in ({'tenant_id':'X Y'},{'domain_id':'X/Y'},{'entry_id':'EVIL\nID'}):
            with self.subTest(scope=scope), self.assertRaises(AuthorizationDenied):self.approve(**scope)

    def test_invalid_factory_denied(self):
        with self.assertRaises(AuthorizationDenied):AtomicLibraryStore(connect=None,verifier=self.verifier)

    def test_invalid_verifier_denied(self):
        with self.assertRaises(AuthorizationDenied):AtomicLibraryStore(connect=self.factory,verifier=None)

    def test_clock_boolean_denied(self):
        s=AtomicLibraryStore(connect=self.factory,verifier=self.verifier,clock=lambda:True)
        with self.assertRaises(AuthorizationDenied):self.approve(store=s)

    def test_no_raw_tokens_in_db(self):
        self.imported();self.approve()
        text=repr(self.rows('aion_library_atomic_approval_burns'))
        self.assertNotIn('APR-1',text)
        self.assertNotIn('GRANT-1',text)

    def test_import_rejects_unreviewed(self):
        c=LibraryCatalog()
        doc=c.register_document(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',version=1,
              sha256=S,source_type='BOOK',source_reference='isbn:123',license_kind='CC_BY',
              rights_holder='publisher',usage_scope='INTERNAL',human_approved_by='reviewer')
        with self.assertRaises(AuthorizationDenied):self.store.import_reviewed(trusted_entry=doc)

    def test_migration_not_run_by_app(self):
        self.assertEqual(self.rows('aion_library_documents'),[])
        with closing(sqlite3.connect(self.db_path)) as db, db:
            self.assertEqual(db.execute('SELECT count(*) FROM sqlite_master WHERE name="aion_library_approval_burns"').fetchone()[0],0)


if __name__=='__main__': unittest.main()
