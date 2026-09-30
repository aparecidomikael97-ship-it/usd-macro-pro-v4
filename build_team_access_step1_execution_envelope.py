"""CLI for preparing a read-only Team Access Step 1 execution envelope."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_step1_execution_envelope import (
    build_step1_execution_envelope,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("materialization")
    parser.add_argument("step1_preflight_packet")
    parser.add_argument("step1_decision_record")
    parser.add_argument("execution_observation")
    parser.add_argument("--output", required=True)
    parser.add_argument("--prepared-at", default="")
    args = parser.parse_args()

    try:
        materialization = _load(args.materialization)
        packet = _load(args.step1_preflight_packet)
        decision = _load(args.step1_decision_record)
        observation = _load(args.execution_observation)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_STEP1_EXECUTION_ENVELOPE_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    prepared_at = args.prepared_at or datetime.now(timezone.utc).isoformat()

    result = build_step1_execution_envelope(
        materialization,
        packet,
        decision,
        observation,
        prepared_at=prepared_at,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if result.get("state") != (
        "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY"
    ):
        return 2

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"Step 1 execution envelope written to: {target}")
    print("No provider command was generated or executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
