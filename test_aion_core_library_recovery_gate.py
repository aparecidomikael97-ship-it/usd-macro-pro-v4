"""Synthetic read-only recovery preflight: no customer data or production keys."""
import sqlite3
import unittest
from copy import deepcopy
from dataclasses import replace
from dataclasses import asdict
from contextlib import closing

from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_security_runtime import ExternalIdentityBridge, VerifiedSession
from aion_core.library_recovery_gate import LibraryRecoveryGate, SignedCheckpoint
import test_aion_core_library_atomic_store as atomic_helpers
IK, AK, RK, NOW = atomic_helpers.IK, atomic_helpers.AK, atomic_helpers.RK, atomic_helpers.NOW

TOKEN = 'synthetic-token-not-for-deployment'
CK = b'c' * 32


class ReadCursor:
    def __init__(self, cur): self.cur = cur
    def execute(self, sql, params=()):
        if sql.startswith('SET TRANSACTION'):
            self.cur.execute('BEGIN')
        else:
            self.cur.execute(sql.replace('%s','?'),params)
        return self
    def fetchone(self): return self.cur.fetchone()
    def fetchall(self): return self.cur.fetchall()
    def close(self): self.cur.close()


class ReadDB:
    autocommit = False
    def __init__(self,path):
        self.db=sqlite3.connect(path,isolation_level=None,timeout=5)
        self.db.execute('PRAGMA query_only = ON')
    def cursor(self): return ReadCursor(self.db.cursor())
    def rollback(self): self.db.rollback()
    def close(self): self.db.close()


class RecoveryGateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=atomic_helpers.AtomicStoreTests('test_migration_is_declarative_postgres')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.imported()
        self.now=NOW
        self.allowed={('reviewer','T-A','TRADER'):('LIBRARY_ADMIN',)}
        self.sessions={TOKEN: VerifiedSession('idp','app','reviewer',NOW-10,NOW+100)}
        def lookup(subject,tenant,domain): return self.allowed.get((subject,tenant,domain),())
        def verify(token): return self.sessions[token]
        self.bridge=ExternalIdentityBridge(verify_token=verify,lookup_roles=lookup,
                     trusted_issuer='idp',token_audience='app',attestation_issuer='authz',
                     signing_key=IK,clock=lambda:self.now)
        self.verifier=AttestationVerifier(identity_issuers={'authz':IK},approval_issuers={'human':AK},
                     rights_issuers={'license':RK},clock=lambda:self.now)
        self.conn=lambda:ReadDB(self.fixture.db_path)
        self.gate=LibraryRecoveryGate(identities=self.bridge,verifier=self.verifier,
                     connect=self.conn,checkpoint_key=CK,clock=lambda:self.now)

    def inspect(self, **kw):
        d=dict(token=TOKEN,tenant_id='T-A',domain_id='TRADER',entry_id=self.fixture.entry.entry_id)
        d.update(kw)
        return self.gate.inspect(**d)

    def checkpoint(self, **kw):
        d=dict(token=TOKEN,tenant_id='T-A',domain_id='TRADER',entry_id=self.fixture.entry.entry_id)
        d.update(kw)
        return self.gate.admin_checkpoint(**d)

    def compare(self,checkpoint,**kw):
        d=dict(token=TOKEN,tenant_id='T-A',domain_id='TRADER',entry_id=self.fixture.entry.entry_id,
               archived=checkpoint)
        d.update(kw)
        return self.gate.compare_archived_checkpoint(**d)

    def sql(self,cmd,args=()):
        with closing(sqlite3.connect(self.fixture.db_path)) as db,db:
            db.execute(cmd,args)

    def test_reviewed_genesis_valid(self):
        r=self.inspect()
        self.assertEqual((r.state,r.event_count),('METADATA_REVIEW',1))
        self.assertEqual(len(r.integrity_digest),64)
    def test_approved_document_burn_and_chain(self):
        self.fixture.approve()
        r=self.inspect()
        self.assertEqual((r.state,r.event_count),('APPROVED_FOR_INDEXING',2))
    def test_cross_tenant_denied(self):
        with self.assertRaises(AuthorizationDenied):self.inspect(tenant_id='T-B')
    def test_cross_domain_denied(self):
        with self.assertRaises(AuthorizationDenied):self.inspect(domain_id='BUSINESS')
    def test_unknown_document_denied(self):
        with self.assertRaises(AuthorizationDenied):self.inspect(entry_id='LIB-OTHER')
    def test_invalid_id_denied(self):
        with self.assertRaises(AuthorizationDenied):self.inspect(entry_id='ID /?')
    def test_invalid_token_denied(self):
        with self.assertRaises(AuthorizationDenied):self.inspect(token='bad-token-not-authorized')
    def test_role_revoked_denied(self):
        self.allowed.clear()
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_role_revoked_mid_read_denied(self):
        original=self.bridge._roles
        count=[0]
        def revoke_on_second(*args):
            count[0]+=1
            return ('LIBRARY_ADMIN',) if count[0]==1 else ()
        self.bridge._roles=revoke_on_second
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_identity_expired_denied(self):
        self.now=NOW+100
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_reader_can_inspect_but_not_mint_checkpoint(self):
        self.allowed[('reviewer','T-A','TRADER')]=('LIBRARY_READER',)
        self.assertEqual(self.inspect().event_count,1)
        with self.assertRaises(AuthorizationDenied):self.checkpoint()
    def test_admin_checkpoint_and_recompare(self):
        cp=self.checkpoint()
        self.assertEqual(self.compare(cp),self.inspect())
        self.assertEqual(cp.payload['schema'],'AION_LIBRARY_RECOVERY_PREFLIGHT_V1')
    def test_checkpoint_cannot_cross_scope(self):
        cp=self.checkpoint()
        with self.assertRaises(AuthorizationDenied):self.compare(cp,tenant_id='T-B')
    def test_checkpoint_tamper_denied(self):
        cp=self.checkpoint()
        payload=deepcopy(cp.payload)
        payload['report']['content_sha256']='b'*64
        with self.assertRaises(AuthorizationDenied):self.compare(SignedCheckpoint(payload,cp.mac_sha256))
    def test_checkpoint_mac_tamper_denied(self):
        cp=self.checkpoint()
        with self.assertRaises(AuthorizationDenied):self.compare(replace(cp,mac_sha256='f'*64))
    def test_checkpoint_missing_denied(self):
        with self.assertRaises(AuthorizationDenied):self.compare(None)
    def test_checkpoint_stale_after_legitimate_approval(self):
        cp=self.checkpoint()
        self.fixture.approve()
        with self.assertRaises(AuthorizationDenied):self.compare(cp)
        self.assertEqual(self.compare(self.checkpoint()).state,'APPROVED_FOR_INDEXING')
    def test_checkpoint_non_admin_cannot_compare(self):
        cp=self.checkpoint()
        self.allowed[('reviewer','T-A','TRADER')]=('LIBRARY_READER',)
        with self.assertRaises(AuthorizationDenied):self.compare(cp)
    def test_bad_genesis_hash_denied(self):
        self.sql('UPDATE aion_library_atomic_audit SET event_hash=?',('f'*64,))
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_missing_genesis_denied(self):
        self.sql('DELETE FROM aion_library_atomic_audit')
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_wrong_genesis_transition_denied(self):
        self.sql('UPDATE aion_library_atomic_audit SET state_from=?',('APPROVED_FOR_INDEXING',))
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_mismatched_state_denied(self):
        self.sql('UPDATE aion_library_documents SET state=?',('APPROVED_FOR_INDEXING',))
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_revoked_state_fail_closed(self):
        self.sql('UPDATE aion_library_documents SET state=?',('REVOKED',))
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_missing_approval_burn_denied(self):
        self.fixture.approve()
        self.sql('DELETE FROM aion_library_atomic_approval_burns')
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_wrong_burn_timestamp_denied(self):
        self.fixture.approve()
        self.sql('UPDATE aion_library_atomic_approval_burns SET burned_at_unix=burned_at_unix+1')
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_tampered_audit_link_denied(self):
        self.fixture.approve()
        self.sql("UPDATE aion_library_atomic_audit SET prev_hash=? WHERE event_type='APPROVE_INDEX'",('f'*64,))
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_unknown_audit_event_denied(self):
        self.fixture.approve()
        self.sql("UPDATE aion_library_atomic_audit SET event_type='REPLACE' WHERE event_type='APPROVE_INDEX'")
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_extra_audit_event_denied(self):
        self.sql("INSERT INTO aion_library_atomic_audit (entry_id,prev_hash,event_hash,event_type,state_from,state_to,approval_key,recorded_at_unix) SELECT entry_id,prev_hash,event_hash,event_type,state_from,state_to,approval_key,recorded_at_unix FROM aion_library_atomic_audit")
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_bad_digest_in_document_denied(self):
        self.sql('UPDATE aion_library_documents SET content_sha256=?',('bad-hash',))
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_damaged_schema_fail_closed_no_leak(self):
        self.sql('DROP TABLE aion_library_atomic_audit')
        with self.assertRaises(AuthorizationDenied) as ctx:self.inspect()
        self.assertNotIn('database',str(ctx.exception).lower())
    def test_connection_failure_no_secrets(self):
        self.gate._connect=lambda: (_ for _ in ()).throw(RuntimeError('secret-connection-host'))
        with self.assertRaises(AuthorizationDenied) as ctx:self.inspect()
        self.assertNotIn('secret-',str(ctx.exception))
    def test_bad_autocommit_connection_denied(self):
        class Bad:
            autocommit=True
            def close(self): pass
        self.gate._connect=Bad
        with self.assertRaises(AuthorizationDenied):self.inspect()
    def test_checkpoint_key_must_be_independent(self):
        with self.assertRaises(AuthorizationDenied):
            LibraryRecoveryGate(identities=self.bridge,verifier=self.verifier,connect=self.conn,checkpoint_key=IK)
    def test_short_checkpoint_key_denied(self):
        with self.assertRaises(AuthorizationDenied):
            LibraryRecoveryGate(identities=self.bridge,verifier=self.verifier,connect=self.conn,checkpoint_key=b'x')
    def test_no_writes_during_inspect(self):
        before=[len(self.fixture.rows(table)) for table in ('aion_library_documents','aion_library_atomic_approval_burns','aion_library_atomic_audit')]
        self.inspect()
        self.checkpoint()
        after=[len(self.fixture.rows(table)) for table in ('aion_library_documents','aion_library_atomic_approval_burns','aion_library_atomic_audit')]
        self.assertEqual(before,after)
    def test_invalid_checkpoint_clock_denied(self):
        self.gate._clock=lambda:True
        with self.assertRaises(AuthorizationDenied):self.checkpoint()

if __name__=='__main__':unittest.main()
