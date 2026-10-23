"""A185 — LIVE AION sqlite shared-handle/unguarded-connection negative controls.

LAB only. Tests actual SQLiteChatStore + ExecutionOutbox + CumulativeAuthorityBudget
+ ExecutionSaga on synthetic SQLite data. No broker, real credentials or Worker.

A GREEN job means negative controls reproduced. This module does NOT install
an external monotonic epoch, protect a native VFS, or close any P0.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSaga


class A185ActualLiveConnectionBoundaryLab(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="a185-aion-live-")
        self.path = Path(self.tmp.name) / "aion.sqlite"
        self.scope = Scope(owner_id="synthetic-owner", tenant_id="synthetic-tenant",
                           workspace_id="synthetic-workspace")
        self.store = SQLiteChatStore(self.path)
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.budget = CumulativeAuthorityBudget(
            self.store, self.scope, authority_budget_ref="synthetic-budget",
            policy_version="LAB-A185")
        self.saga = ExecutionSaga(
            self.store, self.scope, outbox=self.outbox,
            authority_budget=self.budget)
        self.epoch = {"captured": 1, "authority": 1, "calls": 0}

    def tearDown(self) -> None:
        try:
            self.store.db.set_progress_handler(None, 0)
            self.store.close()
        finally:
            self.tmp.cleanup()

    def _install_demo_hook(self) -> None:
        def check() -> int:
            self.epoch["calls"] += 1
            return int(self.epoch["captured"] != self.epoch["authority"])

        self.store.db.set_progress_handler(check, 1)

    def test_aion_store_outbox_budget_and_saga_reuse_actual_native_connection(self) -> None:
        self.assertIs(self.outbox.db, self.store.db)
        self.assertIs(self.budget.db, self.store.db)
        self.assertIs(self.saga.db, self.store.db)
        self.assertIs(self.outbox.store, self.store)
        self.assertIs(self.saga.store, self.store)
        print("A185_AION_SHARED_DB_HANDLE=CHAT_OUTBOX_BUDGET_SAGA")

    def test_revoked_epoch_denies_cached_store_and_outbox_queries(self) -> None:
        self.store.create_conversation(self.scope, title="synthetic-cache")
        self._install_demo_hook()
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM conversations").fetchone()[0], 1)
        self.assertEqual(len(self.outbox.list()), 0)
        self.epoch["authority"] = 2
        with self.assertRaisesRegex(sqlite3.OperationalError, "(?i)interrupt"):
            self.store.db.execute("SELECT count(*) FROM conversations").fetchone()
        with self.assertRaisesRegex(sqlite3.OperationalError, "(?i)interrupt"):
            self.outbox.list()
        self.assertGreater(self.epoch["calls"], 0)
        self.epoch["authority"] = 1
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM conversations").fetchone()[0], 1)
        print("A185_AION_SHARED_HANDLE_CACHE_REVOKED=DENIED_BY_SYNTHETIC_PROGRESS_HANDLER")

    def test_fresh_raw_sqlite_connection_bypasses_aion_connection_hook(self) -> None:
        self._install_demo_hook()
        self.assertEqual(self.store.db.execute("SELECT 1").fetchone()[0], 1)
        self.epoch["authority"] = 2
        with self.assertRaisesRegex(sqlite3.OperationalError, "(?i)interrupt"):
            self.store.db.execute("SELECT 1").fetchone()
        with sqlite3.connect(self.path) as parallel:
            parallel.execute("CREATE TABLE IF NOT EXISTS a185_bypass(n INTEGER NOT NULL)")
            parallel.execute("INSERT INTO a185_bypass VALUES (7)")
        self.epoch["authority"] = 1
        self.assertEqual(self.store.db.execute(
            "SELECT n FROM a185_bypass").fetchone()[0], 7)
        print("A185_AION_SEPARATE_SQLITE_CONNECT_BYPASS=WRITES_DURING_REVOKED_EPOCH")

    def test_store_reopen_is_a_new_connection_without_old_epoch_guard(self) -> None:
        self._install_demo_hook()
        self.epoch["authority"] = 2
        with self.assertRaises(sqlite3.OperationalError):
            self.store.db.execute("SELECT 1").fetchone()
        reopened = SQLiteChatStore(self.path)
        try:
            self.assertIsNot(reopened.db, self.store.db)
            self.assertEqual(reopened.db.execute("SELECT 1").fetchone()[0], 1)
            print("A185_AION_NEW_STORE_OPEN_BYPASS=UNGUARDED_CONNECTION")
        finally:
            reopened.close()


if __name__ == "__main__":
    print(f"A185_SQLITE_VERSION={sqlite3.sqlite_version}")
    unittest.main(verbosity=2)
