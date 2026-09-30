"""CLI for validating a Windows operator readiness -> baseline handoff."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_windows_operator_kit import (
    validate_windows_operator_readiness,
)
from atlasquant_aion_business_team_access_sandbox_evidence import (
    validate_baseline_evidence,
)
from atlasquant_aion_business_team_access_windows_operator_handoff import (
    build_operator_baseline_handoff,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("readiness")
    parser.add_argument("baseline")
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    try:
        readiness_raw = _load(args.readiness)
        baseline_raw = _load(args.baseline)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_WINDOWS_OPERATOR_HANDOFF_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    readiness = validate_windows_operator_readiness(readiness_raw)
    baseline = validate_baseline_evidence(baseline_raw)
    result = build_operator_baseline_handoff(
        readiness,
        baseline,
        reviewed_by=args.reviewed_by,
    )

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")

    return 0 if result.get("state") == (
        "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
