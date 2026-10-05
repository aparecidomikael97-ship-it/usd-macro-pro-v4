"""Standalone helper used only by durable-task multi-process CAS tests."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_durable_task_repository import (
    DurableTaskRepository,
    DurableTaskRepositoryError,
)
from atlasquant_aion_durable_tasks import cancel_durable_task, pause_durable_task


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 11:
        raise SystemExit(
            "usage: worker DB OWNER TENANT WORKSPACE TASK_ID TARGET "
            "READY_PATH BARRIER_PATH RESULT_PATH CHANGED_AT"
        )
    (
        _prog,
        db_path,
        owner,
        tenant,
        workspace,
        task_id,
        target,
        ready_path,
        barrier_path,
        result_path,
        changed_at,
    ) = argv
    scope = Scope(owner, tenant, workspace)
    store = SQLiteChatStore(Path(db_path))
    try:
        repo = DurableTaskRepository(store, scope)
        base = repo.load(task_id)
        if target == "PAUSED":
            candidate = pause_durable_task(
                base,
                expected_revision=base["revision"],
                changed_at=changed_at,
                next_action="resume later",
            )
        elif target == "CANCELED":
            candidate = cancel_durable_task(
                base,
                expected_revision=base["revision"],
                changed_at=changed_at,
            )
        else:
            raise ValueError("unsupported target")
        Path(ready_path).write_text("READY", encoding="utf-8")
        deadline = time.monotonic() + 20.0
        barrier = Path(barrier_path)
        while not barrier.exists():
            if time.monotonic() >= deadline:
                _write_json(Path(result_path), {
                    "target": target,
                    "status": "BARRIER_TIMEOUT",
                })
                return 3
            time.sleep(0.02)
        try:
            result = repo.compare_and_swap(
                candidate,
                expected_revision=base["revision"],
            )
            status = result["status"]
        except DurableTaskRepositoryError as exc:
            status = exc.code
        _write_json(Path(result_path), {
            "target": target,
            "status": status,
        })
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
