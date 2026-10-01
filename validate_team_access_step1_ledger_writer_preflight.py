"""Read-only preflight for the Step 1 persistent lifecycle ledger writer.

This command never appends a ledger entry. Passing --apply is refused.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

from atlasquant_aion_business_team_access_step1_ledger_persistent_writer import (
    MAX_PREFLIGHT_STATE,
    apply_step1_ledger_persistence,
    build_ledger_writer_preflight,
)

BANNER = "PLAN ONLY — NO LEDGER WRITE PERFORMED"


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan-only preflight for the Step 1 lifecycle ledger writer.",
    )
    parser.add_argument("--allowed-root", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--step1-preflight", required=True)
    parser.add_argument("--receipt-review", required=True)
    parser.add_argument("--decision-record", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Refused. Physical persistence is not implemented.",
    )
    args = parser.parse_args(argv)
    print(BANNER)

    if args.apply:
        refused = apply_step1_ledger_persistence()
        print(json.dumps(refused, ensure_ascii=False, indent=2))
        return 2

    try:
        packet = _load(args.step1_preflight)
        review = _load(args.receipt_review)
        record = _load(args.decision_record)
    except Exception as exc:
        print(json.dumps({
            "state": "STEP1_LEDGER_WRITER_PREFLIGHT_INPUT_ERROR",
            "error": type(exc).__name__,
            "banner": "PERSISTENCE NOT AUTHORIZED",
            "ledger_write_performed": False,
        }, ensure_ascii=False))
        return 2

    plan = build_ledger_writer_preflight(
        allowed_root=Path(args.allowed_root),
        ledger_path=Path(args.ledger),
        step1_preflight_packet=packet,
        receipt_review=review,
        decision_record=record,
        mode="PLAN_ONLY",
    )
    rendered = json.dumps(plan, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        target = Path(args.output)
        ledger = Path(args.ledger)
        if target.resolve() == ledger.resolve():
            print(json.dumps({
                "state": "STEP1_LEDGER_WRITER_OUTPUT_REFUSED",
                "reason": "output_must_not_be_ledger",
                "ledger_write_performed": False,
            }, ensure_ascii=False))
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    if plan.get("state") != MAX_PREFLIGHT_STATE:
        return 2
    if plan.get("ledger_write_performed") is not False:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
