"""AION P0 diagnostic: pre-19-Oct READ/WRITE candidate scope on CURRENT LAB.

READ: current STAGED host still caches a thread-affine live SQLiteChatStore;
      a Streamlit rerun on another Python thread DENIES rather than working.
      PASS proves a *known availability gap*, NOT remediation or P0 closure.

WRITE: current A61 Saga/Outbox staging uses SQLite SAVEPOINT correctly.
       PASS proves only local atomicity, NOT external effect or original P0 ID.

No network, credentials, live Streamlit process, provider, Worker or messages.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from aion_chat.store import SQLiteChatStore, StorageUnavailableError
import atlasquant_aion_chat_host_staging as host
import test_atlasquant_aion_chat_host_staging as fixture
import test_atlasquant_aion_saga_outbox_atomic_a61 as atomic


class PriorSQLiteReadCandidateOnCurrentHeadLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.session={}
        self.addCleanup(self.close_on_owner_thread)

    def close_on_owner_thread(self):
        host.close_all_staged_host_stores(self.session)

    def binding(self):
        return host.build_staged_host_binding(
            self.session, fixture.access(),
            config=fixture.config(self.root),
            environment="STAGING",
            runtime_context={"provider_enabled":False,"network_enabled":False},
        )

    def foreign_thread(self, function):
        with ThreadPoolExecutor(max_workers=1) as p:
            return p.submit(function).result(timeout=12)

    def test_01_read_candidate_staged_host_still_caches_native_thread_bound_store(self):
        binding=self.binding()
        self.assertIsInstance(binding["store"],SQLiteChatStore)
        self.assertTrue(hasattr(binding["store"],"db"))
        self.assertIs(self.binding()["store"],binding["store"])
        self.assertFalse(binding["provider_called"])
        self.assertFalse(binding["external_action_executed"])

    def test_02_rerun_in_another_thread_is_refused_but_does_not_orphan_handle(self):
        first=self.binding()
        store=first["store"]
        conversation=store.create_conversation(first["scope"],"lab-only")
        with self.assertRaisesRegex(
            StorageUnavailableError,"SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
            self.foreign_thread(self.binding)
        self.assertIs(self.binding()["store"],store)
        self.assertEqual(store.get_conversation(first["scope"],conversation.id).id,
                         conversation.id)
        self.assertEqual(len([k for k in self.session if str(k).startswith("aion")]),len([
            k for k in self.session if str(k).startswith("aion")]))

    def test_03_foreign_thread_close_all_denied_before_holder_mutation(self):
        first=self.binding()
        before=set(self.session)
        with self.assertRaisesRegex(
            StorageUnavailableError,"SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
            self.foreign_thread(lambda:
                host.close_all_staged_host_stores(self.session))
        self.assertEqual(set(self.session),before)
        self.assertIs(self.binding()["store"],first["store"])

    def test_04_foreign_thread_direct_read_denied_before_query(self):
        first=self.binding()
        c=first["store"].create_conversation(first["scope"],"persisted-lab")
        with self.assertRaisesRegex(
            StorageUnavailableError,"SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
            self.foreign_thread(lambda:
                first["store"].get_conversation(first["scope"],c.id))
        self.assertEqual(first["store"].get_conversation(first["scope"],c.id).title,
                         "persisted-lab")

    def test_05_foreign_thread_scoped_close_denied_without_losing_store(self):
        first=self.binding()
        with self.assertRaisesRegex(
            StorageUnavailableError,"SQLITE_STORE_CONNECTION_THREAD_MISMATCH"):
            self.foreign_thread(lambda:
                host.close_staged_host_store(self.session,first["scope"]))
        self.assertIs(self.binding()["store"],first["store"])

    def test_06_owner_thread_logout_reopen_restores_local_chat_availability(self):
        first=self.binding()
        c=first["store"].create_conversation(first["scope"],"after-reopen")
        self.assertEqual(host.close_all_staged_host_stores(self.session),1)
        reopened=self.binding()
        self.assertIsNot(reopened["store"],first["store"])
        self.assertEqual(
            reopened["store"].get_conversation(reopened["scope"],c.id).title,
            "after-reopen")
        self.assertFalse(reopened["grants_authority"])


class PriorSQLiteWriteCandidateOnCurrentHeadLAB(unittest.TestCase):
    def test_07_existing_a61_saga_event_exception_rolls_back_outbox(self):
        test=atomic.A61SagaOutboxAtomicStagingTests(
            "test_01_event_append_failure_leaves_no_orphan_outbox_or_decision")
        result=unittest.TestResult()
        test.run(result)
        self.assertEqual(result.testsRun,1)
        self.assertEqual(result.failures,[])
        self.assertEqual(result.errors,[])

    def test_08_existing_a61_nested_savepoint_rollback_preserves_outer_tx(self):
        test=atomic.A61SagaOutboxAtomicStagingTests(
            "test_06_nested_enqueue_sql_failure_preserves_parent_transaction")
        result=unittest.TestResult()
        test.run(result)
        self.assertEqual(result.testsRun,1)
        self.assertEqual(result.failures,[])
        self.assertEqual(result.errors,[])

    def test_09_prior_write_candidate_not_actual_external_effect(self):
        fixture_src=(Path(__file__).resolve().parents[1]/
                     "test_atlasquant_aion_saga_outbox_atomic_a61.py").read_text("utf-8")
        self.assertIn('self.assertEqual(self.outbox.effect_count(), 0)',fixture_src)
        self.assertIn('A61_INJECT_STEP_WRITE',fixture_src)

if __name__=="__main__":
    unittest.main()
