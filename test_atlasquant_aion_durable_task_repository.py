from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import multiprocessing as mp
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_durable_task_repository import (
    DurableTaskRepository,
    DurableTaskRepositoryError,
    DurableTaskRepositoryIntegrityError,
    SimulatedTaskStoreCrash,
)
from atlasquant_aion_durable_tasks import (
    cancel_durable_task,
    new_durable_task,
    pause_durable_task,
)


CREATED = "2026-10-05T10:00:00+00:00"
CHANGED = "2026-10-05T10:01:00+00:00"


def _scope(name="a"):
    return Scope(f"owner-{name}", f"tenant-{name}", f"workspace-{name}")


def _task(title="Durable CAS Task"):
    return new_durable_task(
        title,
        objective="prove physical atomic CAS",
        created_at=CREATED,
        source="TEST",
    )


def _process_cas_worker(
    db_path,
    owner,
    tenant,
    workspace,
    task_id,
    target,
    ready_queue,
    gate,
    result_queue,
):
    scope = Scope(owner, tenant, workspace)
    store = SQLiteChatStore(Path(db_path))
    try:
        repo = DurableTaskRepository(store, scope)
        base = repo.load(task_id)
        if target == "PAUSED":
            candidate = pause_durable_task(
                base,
                expected_revision=base["revision"],
                changed_at=CHANGED,
                next_action="resume later",
            )
        else:
            candidate = cancel_durable_task(
                base,
                expected_revision=base["revision"],
                changed_at=CHANGED,
            )
        ready_queue.put(("READY", target))
        if not gate.wait(15):
            result_queue.put((target, "GATE_TIMEOUT"))
            return
        try:
            result = repo.compare_and_swap(
                candidate,
                expected_revision=base["revision"],
            )
            result_queue.put((target, result["status"]))
        except DurableTaskRepositoryError as exc:
            result_queue.put((target, exc.code))
    finally:
        store.close()


class DurableTaskAtomicRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.scope = _scope("a")

    def _repo(self, raw, *, scope=None, fault_injector=None):
        store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
        repo = DurableTaskRepository(
            store,
            scope or self.scope,
            fault_injector=fault_injector,
        )
        return store, repo

    def test_create_load_and_idempotent_replay(self):
        with tempfile.TemporaryDirectory() as raw:
            store, repo = self._repo(raw)
            task = _task()
            first = repo.create(task)
            second = repo.create(task)
            self.assertEqual(first["status"], "CREATED")
            self.assertEqual(second["status"], "IDEMPOTENT")
            loaded = repo.load(task["durable_task_id"])
            self.assertEqual(loaded, task)
            report = repo.integrity_report()
            self.assertEqual(report["state"], "MATCH")
            self.assertTrue(report["atomic_cas"])
            self.assertEqual(report["multi_process_boundary"], "SQLITE_TRANSACTION")
            self.assertFalse(report["executes_action"])
            self.assertFalse(report["automatic_resume_executes"])
            store.close()

    def test_same_task_id_different_payload_is_collision(self):
        with tempfile.TemporaryDirectory() as raw:
            store, repo = self._repo(raw)
            task = _task()
            repo.create(task)
            changed = deepcopy(task)
            changed["objective"] = "different payload"
            with self.assertRaisesRegex(DurableTaskRepositoryError, "TASK_ID_COLLISION"):
                repo.create(changed)
            store.close()

    def test_atomic_cas_updates_exactly_one_revision(self):
        with tempfile.TemporaryDirectory() as raw:
            store, repo = self._repo(raw)
            task = _task()
            repo.create(task)
            candidate = pause_durable_task(
                task,
                expected_revision=1,
                changed_at=CHANGED,
                next_action="resume later",
            )
            out = repo.compare_and_swap(candidate, expected_revision=1)
            self.assertEqual(out["status"], "UPDATED")
            self.assertEqual(out["revision"], 2)
            self.assertEqual(repo.load(task["durable_task_id"])["state"], "PAUSED")
            store.close()

    def test_stale_writer_loses_after_another_revision_commits(self):
        with tempfile.TemporaryDirectory() as raw:
            store, repo = self._repo(raw)
            base = _task()
            repo.create(base)
            winner = pause_durable_task(
                base,
                expected_revision=1,
                changed_at=CHANGED,
            )
            loser = cancel_durable_task(
                base,
                expected_revision=1,
                changed_at=CHANGED,
            )
            repo.compare_and_swap(winner, expected_revision=1)
            with self.assertRaisesRegex(DurableTaskRepositoryError, "REVISION_CONFLICT"):
                repo.compare_and_swap(loser, expected_revision=1)
            persisted = repo.load(base["durable_task_id"])
            self.assertEqual(persisted["state"], "PAUSED")
            self.assertEqual(persisted["revision"], 2)
            store.close()

    def test_same_candidate_retry_after_commit_is_idempotent_even_with_old_expected_revision(self):
        with tempfile.TemporaryDirectory() as raw:
            store, repo = self._repo(raw)
            base = _task()
            repo.create(base)
            candidate = pause_durable_task(
                base,
                expected_revision=1,
                changed_at=CHANGED,
            )
            first = repo.compare_and_swap(candidate, expected_revision=1)
            retry = repo.compare_and_swap(candidate, expected_revision=1)
            self.assertEqual(first["status"], "UPDATED")
            self.assertEqual(retry["status"], "IDEMPOTENT")
            self.assertEqual(repo.load(base["durable_task_id"])["revision"], 2)
            store.close()

    def test_revision_skip_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            store, repo = self._repo(raw)
            base = _task()
            repo.create(base)
            candidate = pause_durable_task(
                base,
                expected_revision=1,
                changed_at=CHANGED,
            )
            candidate["revision"] = 3
            with self.assertRaisesRegex(
                DurableTaskRepositoryError,
                "CAS_REVISION_MUST_INCREMENT_ONCE",
            ):
                repo.compare_and_swap(candidate, expected_revision=1)
            self.assertEqual(repo.load(base["durable_task_id"])["revision"], 1)
            store.close()

    def test_terminal_task_cannot_be_reopened_by_forged_snapshot(self):
        with tempfile.TemporaryDirectory() as raw:
            store, repo = self._repo(raw)
            base = _task()
            repo.create(base)
            canceled = cancel_durable_task(
                base,
                expected_revision=1,
                changed_at=CHANGED,
            )
            repo.compare_and_swap(canceled, expected_revision=1)
            forged = deepcopy(canceled)
            forged["state"] = "PAUSED"
            forged["revision"] = 3
            forged["updated_at"] = "2026-10-05T10:02:00+00:00"
            with self.assertRaisesRegex(DurableTaskRepositoryError, "TASK_TERMINAL"):
                repo.compare_and_swap(forged, expected_revision=2)
            self.assertEqual(repo.load(base["durable_task_id"])["state"], "CANCELED")
            store.close()

    def test_before_commit_crash_rolls_back_revision(self):
        with tempfile.TemporaryDirectory() as raw:
            def crash(stage, context):
                if stage == "BEFORE_CAS_COMMIT":
                    raise SimulatedTaskStoreCrash(stage)

            store, repo = self._repo(raw, fault_injector=crash)
            base = _task()
            repo.create(base)
            candidate = pause_durable_task(
                base,
                expected_revision=1,
                changed_at=CHANGED,
            )
            with self.assertRaises(SimulatedTaskStoreCrash):
                repo.compare_and_swap(candidate, expected_revision=1)
            store.close()

            reopened = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            recovered = DurableTaskRepository(reopened, self.scope)
            self.assertEqual(recovered.load(base["durable_task_id"])["revision"], 1)
            self.assertEqual(recovered.integrity_report()["state"], "MATCH")
            reopened.close()

    def test_after_commit_lost_response_recovers_as_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as raw:
            triggered = {"done": False}
            def crash(stage, context):
                if stage == "AFTER_CAS_COMMIT" and not triggered["done"]:
                    triggered["done"] = True
                    raise SimulatedTaskStoreCrash(stage)

            store, repo = self._repo(raw, fault_injector=crash)
            base = _task()
            repo.create(base)
            candidate = pause_durable_task(
                base,
                expected_revision=1,
                changed_at=CHANGED,
            )
            with self.assertRaises(SimulatedTaskStoreCrash):
                repo.compare_and_swap(candidate, expected_revision=1)
            store.close()

            reopened = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            recovered = DurableTaskRepository(reopened, self.scope)
            self.assertEqual(recovered.load(base["durable_task_id"])["revision"], 2)
            retry = recovered.compare_and_swap(candidate, expected_revision=1)
            self.assertEqual(retry["status"], "IDEMPOTENT")
            reopened.close()

    def test_two_connections_same_candidate_yield_update_plus_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "chat.sqlite3"
            seed = SQLiteChatStore(path)
            seed_repo = DurableTaskRepository(seed, self.scope)
            base = _task()
            seed_repo.create(base)
            candidate = pause_durable_task(
                base,
                expected_revision=1,
                changed_at=CHANGED,
            )
            seed.close()

            def write():
                local = SQLiteChatStore(path)
                try:
                    repo = DurableTaskRepository(local, self.scope)
                    return repo.compare_and_swap(
                        candidate,
                        expected_revision=1,
                    )["status"]
                finally:
                    local.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses = sorted(pool.map(lambda _: write(), range(2)))
            self.assertEqual(statuses, ["IDEMPOTENT", "UPDATED"])

    def test_two_separate_processes_race_one_wins_atomic_cas(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "chat.sqlite3"
            seed = SQLiteChatStore(path)
            repo = DurableTaskRepository(seed, self.scope)
            base = _task()
            repo.create(base)
            seed.close()

            ctx = mp.get_context("spawn")
            ready = ctx.Queue()
            results = ctx.Queue()
            gate = ctx.Event()
            args = (
                str(path),
                self.scope.owner_id,
                self.scope.tenant_id,
                self.scope.workspace_id,
                base["durable_task_id"],
            )
            p1 = ctx.Process(
                target=_process_cas_worker,
                args=(*args, "PAUSED", ready, gate, results),
            )
            p2 = ctx.Process(
                target=_process_cas_worker,
                args=(*args, "CANCELED", ready, gate, results),
            )
            p1.start()
            p2.start()
            self.assertEqual(ready.get(timeout=15)[0], "READY")
            self.assertEqual(ready.get(timeout=15)[0], "READY")
            gate.set()
            rows = [results.get(timeout=15), results.get(timeout=15)]
            p1.join(timeout=15)
            p2.join(timeout=15)
            self.assertFalse(p1.is_alive())
            self.assertFalse(p2.is_alive())
            self.assertEqual(p1.exitcode, 0)
            self.assertEqual(p2.exitcode, 0)
            statuses = sorted(status for _target, status in rows)
            self.assertEqual(statuses, ["REVISION_CONFLICT", "UPDATED"])

            reopened = SQLiteChatStore(path)
            recovered = DurableTaskRepository(reopened, self.scope)
            persisted = recovered.load(base["durable_task_id"])
            self.assertEqual(persisted["revision"], 2)
            self.assertIn(persisted["state"], {"PAUSED", "CANCELED"})
            self.assertEqual(recovered.integrity_report()["state"], "MATCH")
            reopened.close()

    def test_cross_scope_cannot_read_foreign_task_and_same_id_can_exist_independently(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "chat.sqlite3"
            store_a = SQLiteChatStore(path)
            repo_a = DurableTaskRepository(store_a, _scope("a"))
            task = _task()
            repo_a.create(task)
            store_a.close()

            store_b = SQLiteChatStore(path)
            repo_b = DurableTaskRepository(store_b, _scope("b"))
            with self.assertRaises(LookupError):
                repo_b.load(task["durable_task_id"])
            created_b = repo_b.create(task)
            self.assertEqual(created_b["status"], "CREATED")
            self.assertEqual(len(repo_b.list()), 1)
            store_b.close()

    def test_digest_payload_revision_state_and_timestamp_corruption_fail_closed(self):
        mutations = [
            ("task_digest", "0" * 64, "TASK_DIGEST_MISMATCH"),
            ("revision", 9, "TASK_REVISION_BINDING_MISMATCH"),
            ("task_state", "DONE", "TASK_STATE_BINDING_MISMATCH"),
            ("updated_at", "2099-01-01T00:00:00+00:00", "TASK_UPDATED_AT_BINDING_MISMATCH"),
        ]
        for column, value, code in mutations:
            with self.subTest(column=column):
                with tempfile.TemporaryDirectory() as raw:
                    store, repo = self._repo(raw)
                    task = _task()
                    repo.create(task)
                    store.db.execute(
                        f"""UPDATE aion_durable_task_repository SET {column}=?
                            WHERE owner=? AND tenant=? AND workspace=? AND task_id=?""",
                        (value, self.scope.owner_id, self.scope.tenant_id, self.scope.workspace_id, task["durable_task_id"]),
                    )
                    with self.assertRaisesRegex(DurableTaskRepositoryIntegrityError, code):
                        repo.load(task["durable_task_id"])
                    self.assertEqual(repo.integrity_report()["state"], "MISMATCH")
                    store.close()

    def test_payload_rewrite_with_old_digest_is_detected(self):
        with tempfile.TemporaryDirectory() as raw:
            store, repo = self._repo(raw)
            task = _task()
            repo.create(task)
            store.db.execute(
                """UPDATE aion_durable_task_repository SET payload=?
                   WHERE owner=? AND tenant=? AND workspace=? AND task_id=?""",
                (
                    '{"forged":true}',
                    self.scope.owner_id,
                    self.scope.tenant_id,
                    self.scope.workspace_id,
                    task["durable_task_id"],
                ),
            )
            with self.assertRaisesRegex(DurableTaskRepositoryIntegrityError, "TASK_DIGEST_MISMATCH"):
                repo.load(task["durable_task_id"])
            store.close()

    def test_repository_operations_have_no_network_subprocess_or_automatic_resume(self):
        with tempfile.TemporaryDirectory() as raw:
            with patch("socket.socket", side_effect=AssertionError("socket forbidden")), patch(
                "subprocess.Popen",
                side_effect=AssertionError("subprocess forbidden"),
            ):
                store, repo = self._repo(raw)
                task = _task()
                created = repo.create(task)
                candidate = pause_durable_task(
                    created["task"],
                    expected_revision=1,
                    changed_at=CHANGED,
                )
                updated = repo.compare_and_swap(candidate, expected_revision=1)
                loaded = repo.load(task["durable_task_id"])
                report = repo.integrity_report()
                self.assertEqual(updated["status"], "UPDATED")
                self.assertEqual(loaded["revision"], 2)
                self.assertFalse(report["executes_action"])
                self.assertFalse(report["automatic_resume_executes"])
                store.close()


if __name__ == "__main__":
    unittest.main()
