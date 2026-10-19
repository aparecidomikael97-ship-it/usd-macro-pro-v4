"""P0 LAB: staged session must retain SQLite handles when owner-thread close fails.

Test contracts authored before host patch. All handles/paths/scopes are synthetic
and temporary; no live Streamlit session, Worker, provider or external action.
The SQLite store's owner-thread contract is already active in the LAB base.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError, HEALTHY
from atlasquant_aion_chat_host_staging import (
    get_or_create_staged_store,
    close_all_staged_host_stores,
    close_staged_host_store,
    _holder_key,
    _ACTIVE_SCOPE_KEY,
    _store_path,
)

ONE = Scope("fixture-owner", "fixture-tenant", "fixture-workspace")
TWO = Scope("fixture-other", "fixture-tenant", "fixture-workspace")
DENIAL = "SQLITE_STORE_CONNECTION_THREAD_MISMATCH"


class P0StagedHostCleanupOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p0-staged-host-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.session = {}
        self.primary = get_or_create_staged_store(
            self.session, ONE, self.root, session_binding_digest="owner-session-a"
        )
        # On failure, use the owner thread to close any still-managed handles.
        self.addCleanup(self.owner_cleanup)

    def owner_cleanup(self):
        # No foreign worker should remain after joining futures.
        close_all_staged_host_stores(self.session)

    def foreign(self, operation):
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(operation).result(timeout=12)

    def assert_primary_preserved(self):
        self.assertIs(self.session[_holder_key(ONE)]["store"], self.primary)
        self.assertEqual(self.session[_ACTIVE_SCOPE_KEY], _holder_key(ONE))
        self.assertEqual(self.primary.storage_health(deep=True)["state"], HEALTHY)

    def test_01_wrong_thread_close_all_does_not_pop_or_detach_owner_handle(self):
        original = dict(self.session)
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            self.foreign(lambda: close_all_staged_host_stores(self.session))
        self.assertEqual(self.session, original)
        self.assert_primary_preserved()

    def test_02_wrong_thread_close_scoped_does_not_pop_handle(self):
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            self.foreign(lambda: close_staged_host_store(self.session, ONE))
        self.assert_primary_preserved()

    def test_03_wrong_thread_binding_rotation_cannot_discard_old_handle(self):
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            self.foreign(lambda: get_or_create_staged_store(
                self.session, ONE, self.root, session_binding_digest="owner-session-b"
            ))
        self.assert_primary_preserved()
        self.assertEqual(self.session[_holder_key(ONE)]["session_binding_digest"], "owner-session-a")

    def test_04_wrong_thread_scope_switch_preserves_existing_owner_binding(self):
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            self.foreign(lambda: get_or_create_staged_store(
                self.session, TWO, self.root, session_binding_digest="foreign-session"
            ))
        self.assert_primary_preserved()
        self.assertNotIn(_holder_key(TWO), self.session)
        self.assertFalse(_store_path(TWO, self.root).exists())

    def test_05_foreign_validation_of_existing_binding_denies_without_mutation(self):
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            self.foreign(lambda: get_or_create_staged_store(
                self.session, ONE, self.root, session_binding_digest="owner-session-a"
            ))
        self.assert_primary_preserved()

    def test_06_owner_can_close_everything_after_failed_wrong_thread_attempt(self):
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            self.foreign(lambda: close_all_staged_host_stores(self.session))
        self.assertEqual(close_all_staged_host_stores(self.session), 1)
        self.assertNotIn(_ACTIVE_SCOPE_KEY, self.session)
        self.assertNotIn(_holder_key(ONE), self.session)
        self.assertIsNone(self.primary.db)
        self.assertEqual(close_all_staged_host_stores(self.session), 0)

    def test_07_owner_can_rotate_binding_after_foreign_failed_rotation(self):
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            self.foreign(lambda: get_or_create_staged_store(
                self.session, ONE, self.root, session_binding_digest="owner-session-b"
            ))
        successor = get_or_create_staged_store(
            self.session, ONE, self.root, session_binding_digest="owner-session-b"
        )
        self.assertIsNot(successor, self.primary)
        self.assertIsNone(self.primary.db)
        self.assertIs(self.session[_holder_key(ONE)]["store"], successor)
        self.assertEqual(successor.storage_health()["state"], HEALTHY)

    def test_08_preflight_all_handles_before_any_remove(self):
        additional = SQLiteChatStore(_store_path(TWO, self.root))
        self.session[_holder_key(TWO)] = {
            "schema": "fixture", "path": str(_store_path(TWO, self.root)),
            "store": additional, "session_binding_digest": "two",
        }
        try:
            with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
                self.foreign(lambda: close_all_staged_host_stores(self.session))
            self.assertIs(self.session[_holder_key(ONE)]["store"], self.primary)
            self.assertIs(self.session[_holder_key(TWO)]["store"], additional)
            self.assertEqual(additional.storage_health()["state"], HEALTHY)
        finally:
            # Owner thread cleanup is allowed after an unsuccessful foreign call.
            self.assertEqual(close_all_staged_host_stores(self.session), 2)

    def test_09_owner_scope_switch_still_closes_old_handle(self):
        another = get_or_create_staged_store(
            self.session, TWO, self.root, session_binding_digest="new-owner"
        )
        self.assertIsNot(another, self.primary)
        self.assertIsNone(self.primary.db)
        self.assertIs(self.session[_holder_key(TWO)]["store"], another)
        self.assertNotIn(_holder_key(ONE), self.session)

    def test_10_owner_scoped_close_is_idempotent_and_clears_active(self):
        self.assertTrue(close_staged_host_store(self.session, ONE))
        self.assertIsNone(self.primary.db)
        self.assertNotIn(_holder_key(ONE), self.session)
        self.assertNotIn(_ACTIVE_SCOPE_KEY, self.session)
        self.assertFalse(close_staged_host_store(self.session, ONE))


if __name__ == "__main__":
    unittest.main()
