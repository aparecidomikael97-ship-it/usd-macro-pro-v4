"""CLI for building one accepted Team Access sandbox lifecycle plan."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    build_lifecycle_test_plan,
)
from atlasquant_aion_business_team_access_lifecycle_plan_package import (
    validate_lifecycle_plan_package,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline")
    parser.add_argument("baseline_acceptance")
    parser.add_argument("--test-username", required=True)
    parser.add_argument("--tenant", action="append", required=True)
    parser.add_argument(
        "--factor",
        required=True,
        choices=["PASSKEY", "SECURITY_KEY", "TOTP"],
    )
    parser.add_argument("--requested-by", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        baseline = _load(args.baseline)
        acceptance = _load(args.baseline_acceptance)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_LIFECYCLE_PLAN_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    plan = build_lifecycle_test_plan(
        baseline,
        baseline_acceptance=acceptance,
        test_username=args.test_username,
        tenant_ids=args.tenant,
        factor_type=args.factor,
        requested_by=args.requested_by,
    )
    package = validate_lifecycle_plan_package(plan)

    rendered = json.dumps(plan, ensure_ascii=False, indent=2)
    print(json.dumps(package, ensure_ascii=False, indent=2))

    if package.get("state") != (
        "READY_FOR_ADMIN_TEAM_ACCESS_LIFECYCLE_AUTHORIZATION_RECORD"
    ):
        return 2

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"Lifecycle plan written to: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
