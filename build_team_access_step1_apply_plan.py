"""CLI for building a non-executable Team Access Step 1 provider apply plan."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_step1_apply_plan import (
    build_step1_apply_plan,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("execution_envelope")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        envelope = _load(args.execution_envelope)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    result = build_step1_apply_plan(envelope)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if result.get("state") != (
        "READY_FOR_ADMIN_TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_REVIEW"
    ):
        return 2

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"Step 1 provider apply plan written to: {target}")
    print("No provider command was generated and no account was created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
