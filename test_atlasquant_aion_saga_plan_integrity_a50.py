import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timezone
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator
NOW=datetime(2026,10,13,tzinfo=timezone.utc)
class PlanIntegrityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.store=SQLiteChatStore(Path(self.tmp.name)/'SIMULATED.sqlite');self.addCleanup(self.store.close)
  self.scope=Scope('SIMULATED_OWNER','SIMULATED_TENANT','SIMULATED_WORKSPACE')
  self.outbox=ExecutionOutbox(self.store,self.scope)
  budget=CumulativeAuthorityBudget(self.store,self.scope,authority_budget_ref='SIMULATED_BUDGET',policy_version='SIMULATED_POLICY')
  self.saga=ExecutionSagaCoordinator(self.store,self.scope,outbox=self.outbox,authority_budget=budget)
  self.saga.create(saga_id='SIMULATED_SAGA',steps=[dict(step_key='one',action='local_plan',payload={'note':'SIMULATED ORIGINAL'},capability_class='LOW_RISK',risk_points=1,reversible=True,compensation_action='local_undo',compensation_payload={'note':'SIMULATED UNDO'},compensation_risk_points=1)],created_at=NOW)
 def report(self):return self.saga.integrity_report('SIMULATED_SAGA')
 def test_pristine(self):
  r=self.report();self.assertEqual(r['state'],'MATCH');self.assertFalse(r['producer_effect_verified']);self.assertFalse(r['authorizes_execution'])
 def test_payload_tamper_preserving_events_rejected(self):
  with self.store.db:self.store.db.execute("UPDATE aion_execution_saga_steps SET payload=?",(json.dumps({'note':'SIMULATED TAMPER'}),))
  self.assertEqual(self.report()['state'],'MISMATCH')
 def test_risk_tamper_rejected(self):
  with self.store.db:self.store.db.execute('UPDATE aion_execution_saga_steps SET risk_points=2')
  self.assertEqual(self.report()['state'],'MISMATCH')
 def test_compensation_payload_tamper_rejected(self):
  with self.store.db:self.store.db.execute("UPDATE aion_execution_saga_steps SET compensation_payload='{}'")
  self.assertEqual(self.report()['state'],'MISMATCH')
 def test_missing_steps_rejected(self):
  with self.store.db:self.store.db.execute('DELETE FROM aion_execution_saga_steps')
  self.assertEqual(self.report()['state'],'MISMATCH')
 def test_tampered_plan_digest_rejected(self):
  with self.store.db:self.store.db.execute("UPDATE aion_execution_sagas SET plan_digest=?",('f'*64,))
  self.assertEqual(self.report()['state'],'MISMATCH')
 def test_valid_enqueue_preserves_plan(self):
  self.saga.enqueue_next('SIMULATED_SAGA',authorization_ref='SIMULATED_APPROVAL',valid_until=NOW.replace(minute=5),created_at=NOW)
  self.assertEqual(self.report()['state'],'MATCH');self.assertEqual(self.outbox.effect_count(),0)
