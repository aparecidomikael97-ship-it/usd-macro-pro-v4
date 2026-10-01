"""Opt-in integration against ephemeral REAL PostgreSQL (GitHub Actions service).

Requires AION_LIB_TEST_PG_DSN (synthetic CI database only) and psycopg 3.
Normal local/quality test runs skip this suite; never contact production.
"""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor

from aion_core.library_authorization import AttestationVerifier, AuthorizationDenied
from aion_core.library_atomic_store import AtomicLibraryStore, MIGRATION_POSTGRESQL
from aion_core.library_foundation import LibraryCatalog
from test_aion_core_library_atomic_store import IK, AK, RK, NOW, make_proofs

DSN = os.environ.get('AION_LIB_TEST_PG_DSN')


@unittest.skipUnless(DSN, 'synthetic PostgreSQL integration DSN not configured')
class EphemeralPostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DSN:
            return
        try:
            import psycopg
        except ImportError as exc:
            raise unittest.SkipTest('psycopg driver unavailable') from exc
        cls.psycopg=psycopg
        # Deliberately opt-in only; destructive schema setup on ephemeral CI DB.
        if 'localhost' not in DSN and '127.0.0.1' not in DSN:
            raise unittest.SkipTest('real PG tests restricted to localhost sandbox')
        with psycopg.connect(DSN,autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute(MIGRATION_POSTGRESQL)

    def setUp(self):
        with self.psycopg.connect(DSN,autocommit=True) as db:
            with db.cursor() as cur:
                cur.execute('TRUNCATE TABLE aion_library_atomic_audit, '
                            'aion_library_atomic_approval_burns, aion_library_documents RESTART IDENTITY CASCADE')
        self.factory=lambda:self.psycopg.connect(DSN)
        self.verifier=AttestationVerifier(identity_issuers={'authz':IK},approval_issuers={'human':AK},
                          rights_issuers={'license':RK},clock=lambda:NOW)
        self.store=AtomicLibraryStore(connect=self.factory,verifier=self.verifier,clock=lambda:NOW)
        catalog=LibraryCatalog()
        self.entry=catalog.register_document(tenant_id='T-A',domain_id='TRADER',document_id='DOC-1',
              version=1,sha256='a'*64,source_type='BOOK',source_reference='isbn:123',
              license_kind='CC_BY',rights_holder='publisher',usage_scope='INTERNAL',
              human_approved_by='reviewer')
        self.entry=catalog.transition(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,
                                     to_state='METADATA_REVIEW',actor='reviewer')
        self.proofs=make_proofs(self.entry)
        self.store.import_reviewed(trusted_entry=self.entry)

    def counts(self):
        with self.psycopg.connect(DSN,autocommit=True) as db:
            with db.cursor() as c:
                return [c.execute('SELECT count(*) FROM '+x).fetchone()[0] for x in
                     ('aion_library_documents','aion_library_atomic_approval_burns','aion_library_atomic_audit')]

    def approve(self,**kw):
        ident,approval,rights=self.proofs
        args=dict(tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,
                  identity_envelope=ident,approval_envelope=approval,rights_envelope=rights)
        args.update(kw)
        return self.store.approve(**args)

    def test_real_postgres_atomic_approval(self):
        result=self.approve()
        self.assertEqual(self.counts(),[1,1,2])
        with self.psycopg.connect(DSN) as db:
            with db.cursor() as c:
                c.execute('SELECT state FROM aion_library_documents WHERE entry_id=%s',(self.entry.entry_id,))
                self.assertEqual(c.fetchone(),('APPROVED_FOR_INDEXING',))
                c.execute('SELECT prev_hash FROM aion_library_atomic_audit WHERE event_type=%s',('APPROVE_INDEX',))
                self.assertRegex(c.fetchone()[0],r'^[0-9a-f]{64}$')
        self.assertRegex(result.audit_hash,r'^[0-9a-f]{64}$')

    def test_real_postgres_concurrent_approval_only_one(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            out=list(pool.map(lambda _:self._try_approve(),range(5)))
        self.assertEqual(out.count('approved'),1,out)
        self.assertEqual(out.count('denied'),4,out)
        self.assertEqual(self.counts(),[1,1,2])

    def _try_approve(self):
        try:self.approve();return 'approved'
        except AuthorizationDenied:return 'denied'

    def test_real_postgres_failed_audit_rolls_back_all(self):
        with self.psycopg.connect(DSN,autocommit=True) as db:
            with db.cursor() as c:
                c.execute('''CREATE OR REPLACE FUNCTION aion_ci_reject_approval() RETURNS trigger
                  LANGUAGE plpgsql AS $$ BEGIN IF NEW.event_type = 'APPROVE_INDEX' THEN
                  RAISE EXCEPTION 'synthetic CI audit blocker'; END IF; RETURN NEW; END; $$''')
                c.execute('''CREATE TRIGGER aion_ci_reject BEFORE INSERT ON aion_library_atomic_audit
                              FOR EACH ROW EXECUTE FUNCTION aion_ci_reject_approval()''')
        def cleanup():
            with self.psycopg.connect(DSN,autocommit=True) as db:
                with db.cursor() as c:
                    c.execute('DROP TRIGGER IF EXISTS aion_ci_reject ON aion_library_atomic_audit')
                    c.execute('DROP FUNCTION IF EXISTS aion_ci_reject_approval()')
        self.addCleanup(cleanup)
        with self.assertRaises(AuthorizationDenied): self.approve()
        self.assertEqual(self.counts(),[1,0,1])
        with self.psycopg.connect(DSN) as db:
            with db.cursor() as c:
                c.execute('SELECT state FROM aion_library_documents WHERE entry_id=%s',(self.entry.entry_id,))
                self.assertEqual(c.fetchone(),('METADATA_REVIEW',))

    def test_real_postgres_cross_tenant_denied(self):
        with self.assertRaises(AuthorizationDenied):self.approve(tenant_id='T-B')
        self.assertEqual(self.counts(),[1,0,1])

    def test_real_postgres_same_nonce_after_reconnect_denied(self):
        self.approve()
        other=AtomicLibraryStore(connect=self.factory,verifier=self.verifier,clock=lambda:NOW)
        with self.assertRaises(AuthorizationDenied):other.approve(
            tenant_id='T-A',domain_id='TRADER',entry_id=self.entry.entry_id,
            identity_envelope=self.proofs[0],approval_envelope=self.proofs[1],rights_envelope=self.proofs[2])
        self.assertEqual(self.counts(),[1,1,2])

if __name__=='__main__':unittest.main()
