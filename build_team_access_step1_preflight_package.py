"""CLI for producing a zero-ledger Team Access Step 1 preflight packet."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_step1_preflight_package import (
    build_step1_preflight_package,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("materialization")
    parser.add_argument("authorization_package")
    parser.add_argument("observation")
    parser.add_argument("--output", required=True)
    parser.add_argument("--evaluated-at", default="")
    args = parser.parse_args()

    try:
        materialization = _load(args.materialization)
        authorization_package = _load(args.authorization_package)
        observation = _load(args.observation)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_STEP1_PREFLIGHT_PACKAGE_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    evaluated_at = args.evaluated_at or datetime.now(
        timezone.utc
    ).isoformat()

    result = build_step1_preflight_package(
        materialization,
        authorization_package,
        observation,
        evaluated_at=evaluated_at,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if result.get("state") != (
        "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET"
    ):
        return 2

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"Step 1 preflight package written to: {target}")
    print("No lifecycle step was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
