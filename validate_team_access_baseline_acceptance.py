"""CLI for validating explicit Team Access sandbox baseline acceptance."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_sandbox_baseline_acceptance import (
    validate_baseline_acceptance,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("handoff")
    parser.add_argument("acceptance_record")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    try:
        handoff = _load(args.handoff)
        record = _load(args.acceptance_record)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_SANDBOX_BASELINE_ACCEPTANCE_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    result = validate_baseline_acceptance(handoff, record)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")

    return 0 if result.get("state") == (
        "EXPLICIT_SANDBOX_BASELINE_ACCEPTANCE_VERIFIED"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
