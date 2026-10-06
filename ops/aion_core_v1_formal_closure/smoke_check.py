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

TOOLS = (
    "ops/aion_core_v1_formal_closure/export_v220_signing_bundle.py",
    "ops/aion_core_v1_formal_closure/apply_v220_signatures.py",
    "ops/aion_core_v1_formal_closure/prepare_v220_v222.py",
    "ops/aion_core_v1_formal_closure/perform_v223_runtime_write.py",
    "ops/aion_core_v1_formal_closure/prepare_v224_owner_signature.py",
    "ops/aion_core_v1_formal_closure/verify_v224_prepare_v225.py",
    "ops/aion_core_v1_formal_closure/perform_v225_v226.py",
)


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
    assert result["observed_dimension_count"] == 17
    assert result["contract_test_count_sum"] == 2729
    assert result["contains_private_key"] is False
    assert result["contains_signature"] is False
    assert result["network_called"] is False
    assert result["executes_action"] is False

    for rel in TOOLS:
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        assert "ed25519privatekey.generate" not in text
        assert "privatekey.generate" not in text
        assert "generate_private_key" not in text

    v223 = (ROOT / "ops/aion_core_v1_formal_closure/perform_v223_runtime_write.py").read_text(encoding="utf-8")
    assert "--execute-v223-write" in v223
    assert "allow_global_arming_transition=False" in v223
    assert "automatic_retry" in v223
    assert "approved=True" in v223

    v224 = (ROOT / "ops/aion_core_v1_formal_closure/prepare_v224_owner_signature.py").read_text(encoding="utf-8")
    assert "PersistentNonceRegistry" not in v224
    assert "nonce_consumed" in v224
    assert "signature_performed" in v224

    v225 = (ROOT / "ops/aion_core_v1_formal_closure/verify_v224_prepare_v225.py").read_text(encoding="utf-8")
    assert "ensure_registry_outside_repo" in v225
    assert "decision_nonce_consumed" in v225
    assert "build_owner_decision_request" in v225
    assert "verify_owner_signature" in v225

    v226 = (ROOT / "ops/aion_core_v1_formal_closure/perform_v225_v226.py").read_text(encoding="utf-8")
    assert "--execute-v226-write" in v226
    assert "ensure_registry_outside_repo" in v226
    assert "allow_global_arming_transition=False" in v226
    assert "automatic_retry" in v226
    assert "if not args.execute_v226_write" in v226
    # The decision nonce must only be claimed in the explicit execution path.
    assert v226.index("if not args.execute_v226_write") < v226.index("verify_owner_decision(")

    print(json.dumps({
        "state": "OPS_FORMAL_CLOSURE_SMOKE_PASS",
        "packet_digest": result["packet_digest"],
        "dimension_count": 17,
        "test_count_sum": 2729,
        "private_key_generation_present": False,
        "v223_write_requires_explicit_flag": True,
        "v226_write_requires_explicit_flag": True,
        "decision_nonce_consumed_in_dry_run": False,
        "executes_action": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
