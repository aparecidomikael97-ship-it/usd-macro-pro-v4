"""CLI for materializing a reviewable Team Access sandbox lifecycle plan."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    materialize_lifecycle_plan,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline")
    parser.add_argument("baseline_acceptance")
    parser.add_argument("--test-username", required=True)
    parser.add_argument("--tenant-id", action="append", required=True)
    parser.add_argument(
        "--factor-type",
        choices=("PASSKEY", "SECURITY_KEY", "TOTP"),
        required=True,
    )
    parser.add_argument("--requested-by", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    try:
        baseline = _load(args.baseline)
        acceptance = _load(args.baseline_acceptance)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_SANDBOX_LIFECYCLE_MATERIALIZATION_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    result = materialize_lifecycle_plan(
        baseline,
        acceptance,
        test_username=args.test_username,
        tenant_ids=args.tenant_id,
        factor_type=args.factor_type,
        requested_by=args.requested_by,
    )

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")

    return 0 if result.get("state") == (
        "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
