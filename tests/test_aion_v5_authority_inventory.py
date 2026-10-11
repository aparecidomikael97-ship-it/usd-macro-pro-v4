"""Unchanged gates, false authority, capacity and reconstruction boundaries."""
from copy import deepcopy
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
import unittest
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS
from atlasquant_aion_first_install_preparation_v4.outcomes import NO_TRUST
from atlasquant_aion_first_install_preparation_v5.contracts import outcome,digest
from atlasquant_aion_first_install_preparation_v3.ledger_storage import canonical
from tests.aion_receipt_admission_fixtures_v5 import AdmissionFixture

ROOT=Path(__file__).resolve().parents[1]
class InventoryTests(unittest.TestCase):
    def test_original_twenty_gate_manifest_byte_identity(self):
        p=ROOT/'docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json'
        self.assertEqual(sha256(p.read_bytes()).hexdigest(),'b95f4065edfa3d871e40f885d9133954ece871391896bbe3d0344e922ba48516')
        from atlasquant_aion_first_install_preparation.plan import DEPENDENCIES
        self.assertEqual(len(DEPENDENCIES),20)

    def test_all_outcomes_keep_every_authority_false(self):
        for state in ('BLOCKED','UNKNOWN_OUTCOME','RECONCILIATION_REQUIRED','REFERENCE_DURABLE_ADMISSION_UNTRUSTED'):
            with self.subTest(state=state):
                r=outcome(state,**{k:True for k in AUTHORITY_FIELDS},**{k:True for k in NO_TRUST if k not in AUTHORITY_FIELDS})
                for k in (*AUTHORITY_FIELDS,*NO_TRUST):self.assertFalse(r[k])
                self.assertEqual(r['status'],'HARD_NO_GO')

    def test_core_and_v1_v4_files_not_in_publication_inventory(self):
        # This is an explicit diff-contract check, not an implementation mirror.
        inventory=ROOT/'docs/aion/AION_V5_FILE_INVENTORY_2026-10-11.json'
        paths=json.loads(inventory.read_text())['new_files']
        self.assertEqual(len(paths),len(set(paths)))
        for path in paths:
            self.assertTrue(path.startswith(('atlasquant_aion_first_install_preparation_v5/',
                'tests/','tools/aion_first_install_v5_ci.py','.github/workflows/aion-first-install-master-v5.yml','docs/aion/')))
            self.assertNotIn('EXTERNAL_ENROLLMENT_GATE_V1',path)
            self.assertTrue((ROOT/path).is_file())

    def test_recomputed_hash_cannot_hide_consumed_nonce_regression(self):
        f=AdmissionFixture()
        try:
            f.issue();f.admit()
            with closing(sqlite3.connect(f.path)) as db:
                db.row_factory=sqlite3.Row;last=db.execute('SELECT * FROM journal ORDER BY sequence DESC LIMIT 1').fetchone()
                state=json.loads(last['state_json']);next(iter(state['nonces'].values()))['state']='ISSUED'
                raw=canonical(state);body={k:last[k] for k in ('sequence','operation_id','request_digest','previous_digest','state_json')};body['state_json']=raw
                forged=digest(body)
                db.execute('UPDATE journal SET state_json=?,event_digest=? WHERE sequence=?',(raw,forged,last['sequence']))
                db.execute('UPDATE current SET state_json=?,head=?',(raw,forged));db.commit()
            self.assertEqual(f.store.read(f.retained)['state'],'BLOCKED')
        finally:f.close()

    def test_huge_field_is_rejected_before_fetch_materialization(self):
        f=AdmissionFixture()
        try:
            f.issue()
            with closing(sqlite3.connect(f.path)) as db:
                db.execute('UPDATE journal SET operation_id=?',('x'*200000,));db.commit()
            self.assertEqual(f.store.read(f.retained)['state'],'BLOCKED')
        finally:f.close()

    def test_unknown_local_states_do_not_become_success(self):
        f=AdmissionFixture()
        try:
            f.issue()
            with closing(sqlite3.connect(f.path)) as db:
                db.execute('UPDATE current SET head=?',('a'*64,));db.commit()
            self.assertEqual(f.admit()['state'],'BLOCKED')
        finally:f.close()

    def test_rehashed_invalid_signature_cannot_be_reconciled_as_admitted(self):
        f=AdmissionFixture()
        try:
            f.issue();f.admit()
            with closing(sqlite3.connect(f.path)) as db:
                db.row_factory=sqlite3.Row;last=db.execute('SELECT * FROM journal ORDER BY sequence DESC LIMIT 1').fetchone()
                state=json.loads(last['state_json']);rid=f.receipts[0]['receipt_id'];record=state['receipts'][rid]
                record['receipt']['signature']='00'*64;record['receipt_digest']=digest(record['receipt'])
                state['floors'][0]['receipt_digest']=record['receipt_digest']
                raw=canonical(state);body={k:last[k] for k in ('sequence','operation_id','request_digest','previous_digest','state_json')};body['state_json']=raw
                forged=digest(body)
                db.execute('UPDATE journal SET state_json=?,event_digest=? WHERE sequence=?',(raw,forged,last['sequence']))
                db.execute('UPDATE current SET state_json=?,head=?',(raw,forged));db.commit()
            request=dict(bindings=f.bindings,receipts=f.receipts,causal=f.anchor.causal)
            self.assertEqual(f.store.reconcile('fixture-admit',digest(request),f.retained)['state'],'BLOCKED')
        finally:f.close()

if __name__=='__main__':unittest.main()
