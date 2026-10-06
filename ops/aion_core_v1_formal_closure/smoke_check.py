#!/usr/bin/env python3
"""OPS-only static smoke checks for formal closure tooling."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "ops" / "aion-core-v1-formal-closure" / "unsigned_v220_evidence_packet.json"
VALIDATOR = ROOT / "ops" / "aion_core_v1_formal_closure" / "validate_unsigned_v220_packet.py"


def main() -> int:
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), str(PACKET)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        return completed.returncode
    result = json.loads(completed.stdout.strip())
    assert result["state"] == "VALID_UNSIGNED_PACKET"
    assert result["required_dimension_count"] == 17
    assert result["contract_test_count_sum"] == 2729
    assert result["contains_private_key"] is False
    assert result["contains_signature"] is False
    assert result["network_called"] is False
    assert result["executes_action"] is False

    for rel in (
        "ops/aion_core_v1_formal_closure/export_v220_signing_bundle.py",
        "ops/aion_core_v1_formal_closure/apply_v220_signatures.py",
        "ops/aion_core_v1_formal_closure/prepare_v220_v222.py",
        "ops/aion_core_v1_formal_closure/perform_v223_runtime_write.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        assert "privatekey.generate" not in text
        assert "ed25519privatekey.generate" not in text
    writer = (ROOT / "ops/aion_core_v1_formal_closure/perform_v223_runtime_write.py").read_text(encoding="utf-8")
    assert "--execute-v223-write" in writer
    assert "allow_global_arming_transition=False" in writer
    assert "automatic_retry" in writer

    print(json.dumps({
        "state": "OPS_FORMAL_CLOSURE_SMOKE_PASS",
        "packet_digest": result["packet_digest"],
        "executes_action": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
