"""Bootstrap/verify the AION runtime Checkpoint Mestre.

This command is intentionally narrow:
- if the runtime checkpoint does not exist, create the canonical checkpoint once;
- if it already exists, verify it and do not overwrite mutable runtime memory;
- fail closed on mismatch, migration requirement, unsafe branch or missing write
  capability during initial creation.

The workflow supplies an ephemeral repository-scoped GitHub token. No token is
written to disk or to the checkpoint.
"""
from __future__ import annotations

import json
import sys

from atlasquant_aion_memory import (
    default_checkpoint,
    load_runtime_checkpoint,
    runtime_configuration_status,
    runtime_write_preflight,
    save_runtime_checkpoint,
)


def _emit(label: str, payload: object) -> None:
    print(label + "=" + json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def main() -> int:
    config_status = runtime_configuration_status()
    _emit("AION_RUNTIME_CONFIG", config_status)
    if not config_status.get("read_ready"):
        print("AION_RUNTIME_BOOTSTRAP=BLOCKED_READ_NOT_READY")
        return 2

    current = load_runtime_checkpoint()
    _emit(
        "AION_RUNTIME_BEFORE",
        {
            "status": current.get("status"),
            "source": current.get("source"),
            "sha": current.get("sha"),
            "integrity": (current.get("integrity") or {}).get("state"),
        },
    )

    if current.get("status") == "NOT_FOUND":
        if not config_status.get("write_ready"):
            print("AION_RUNTIME_BOOTSTRAP=BLOCKED_WRITE_NOT_READY")
            return 3
        preflight = runtime_write_preflight(current)
        _emit("AION_RUNTIME_PREFLIGHT", preflight)
        if not preflight.get("allowed") or preflight.get("mode") != "CREATE":
            print("AION_RUNTIME_BOOTSTRAP=BLOCKED_PREFLIGHT")
            return 4

        result = save_runtime_checkpoint(
            default_checkpoint(),
            approved=True,
            expected_sha=str(preflight.get("expected_sha") or ""),
        )
        _emit(
            "AION_RUNTIME_CREATE",
            {
                "status": result.get("status"),
                "saved": result.get("saved"),
                "verified": result.get("verified"),
                "sha": result.get("sha"),
                "digest": result.get("digest"),
                "integrity": (result.get("integrity") or {}).get("state"),
            },
        )
        if not (result.get("saved") and result.get("verified") and result.get("status") == "CONFIRMED"):
            print("AION_RUNTIME_BOOTSTRAP=CREATE_FAILED")
            return 5

    elif current.get("status") == "CONFIRMED":
        integrity = current.get("integrity") or {}
        if integrity.get("state") != "CONFIRMED":
            _emit("AION_RUNTIME_VERIFY_BLOCKED", integrity)
            print("AION_RUNTIME_BOOTSTRAP=EXISTING_NOT_CONFIRMED")
            return 6
        print("AION_RUNTIME_BOOTSTRAP=EXISTING_CONFIRMED_NO_WRITE")

    else:
        print("AION_RUNTIME_BOOTSTRAP=RUNTIME_STATE_BLOCKED")
        return 7

    final = load_runtime_checkpoint()
    integrity = final.get("integrity") or {}
    checkpoint = final.get("checkpoint") or {}
    summary = {
        "status": final.get("status"),
        "source": final.get("source"),
        "sha": final.get("sha"),
        "integrity": integrity.get("state"),
        "checkpoint_version": checkpoint.get("checkpoint_version"),
        "foundation_revision": ((checkpoint.get("aion") or {}).get("foundation_revision")),
    }
    _emit("AION_RUNTIME_AFTER", summary)
    if (
        final.get("status") != "CONFIRMED"
        or integrity.get("state") != "CONFIRMED"
        or int(checkpoint.get("checkpoint_version") or 0) < 14
    ):
        print("AION_RUNTIME_BOOTSTRAP=FINAL_VERIFY_FAILED")
        return 8

    print("AION_RUNTIME_BOOTSTRAP=CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
