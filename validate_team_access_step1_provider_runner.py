"""CLI for validating the guarded Team Access Step 1 provider runner."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_step1_provider_runner import (
    build_provider_runner_preflight,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("execution_envelope")
    parser.add_argument("apply_plan")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--authorization-token", default="")
    args = parser.parse_args()

    try:
        envelope = _load(args.execution_envelope)
        plan = _load(args.apply_plan)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_STEP1_PROVIDER_RUNNER_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    result = build_provider_runner_preflight(
        envelope,
        plan,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        base_url=args.base_url,
        sandbox_only=True,
        production_targeted=False,
        secrets_local=True,
        apply_requested=args.apply,
        authorization_token=args.authorization_token,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    allowed = {
        "STEP1_PROVIDER_RUNNER_PLAN_ONLY",
        "READY_FOR_EXPLICIT_MANUAL_STEP1_PROVIDER_APPLY",
    }
    if result.get("state") not in allowed:
        return 2

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
