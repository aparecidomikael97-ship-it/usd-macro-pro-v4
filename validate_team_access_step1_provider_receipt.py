"""CLI for validating the Step 1 provider receipt and ledger preview."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_step1_provider_receipt_review import (
    validate_provider_receipt_and_preview_ledger,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("materialization")
    parser.add_argument("authorization_package")
    parser.add_argument("step1_preflight_packet")
    parser.add_argument("execution_envelope")
    parser.add_argument("apply_plan")
    parser.add_argument("runner_preflight")
    parser.add_argument("provider_receipt")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        materialization = _load(args.materialization)
        authorization = _load(args.authorization_package)
        packet = _load(args.step1_preflight_packet)
        envelope = _load(args.execution_envelope)
        apply_plan = _load(args.apply_plan)
        runner = _load(args.runner_preflight)
        receipt = _load(args.provider_receipt)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_STEP1_PROVIDER_RECEIPT_REVIEW_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    result = validate_provider_receipt_and_preview_ledger(
        materialization,
        authorization,
        packet,
        envelope,
        apply_plan,
        runner,
        receipt,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if result.get("state") != (
        "READY_FOR_ADMIN_TEAM_ACCESS_STEP1_LEDGER_APPEND_REVIEW"
    ):
        return 2

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"Receipt review written to: {target}")
    print("No lifecycle ledger append was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
