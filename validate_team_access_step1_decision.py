"""CLI for validating one explicit Team Access Step 1 decision record."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_step1_decision_record import (
    validate_step1_decision_record,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step1_preflight_packet")
    parser.add_argument("decision_record")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        packet = _load(args.step1_preflight_packet)
        record = _load(args.decision_record)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_STEP1_DECISION_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    result = validate_step1_decision_record(packet, record)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if result.get("state") != (
        "EXPLICIT_SANDBOX_STEP_1_DECISION_RECORD_VERIFIED"
    ):
        return 2

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"Step 1 decision record written to: {target}")
    print("No lifecycle step was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
