"""CLI for building and validating the Step 1 ledger append decision."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_step1_ledger_append_contract import (
    build_ledger_append_decision_request,
    validate_ledger_append_decision,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step1_preflight_packet")
    parser.add_argument("receipt_review")
    parser.add_argument("--decision-record", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        packet = _load(args.step1_preflight_packet)
        review = _load(args.receipt_review)
    except Exception as exc:
        print(json.dumps({
            "state": "STEP1_LEDGER_APPEND_CONTRACT_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    request = build_ledger_append_decision_request(packet, review)
    result = {"request": request}

    if args.decision_record:
        try:
            record = _load(args.decision_record)
        except Exception as exc:
            print(json.dumps({
                "state": "STEP1_LEDGER_APPEND_DECISION_INPUT_ERROR",
                "error": str(exc),
            }, ensure_ascii=False))
            return 2
        result["decision"] = validate_ledger_append_decision(
            request, record
        )

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")

    if request.get("state") != (
        "READY_FOR_EXPLICIT_STEP1_LEDGER_APPEND_DECISION"
    ):
        return 2
    if args.decision_record and result["decision"].get("state") != (
        "EXPLICIT_STEP1_LEDGER_APPEND_DECISION_VERIFIED"
    ):
        return 2

    print("No lifecycle ledger write was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
