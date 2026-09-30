"""CLI for validating Team Access sandbox baseline evidence."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

from atlasquant_aion_business_team_access_sandbox_evidence import (
    validate_baseline_evidence,
    lifecycle_evidence_template,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "evidence",
        help="Path to team-access-baseline-evidence.json",
    )
    parser.add_argument(
        "--write-template",
        default="",
        help="Optional path for a sanitized lifecycle evidence template",
    )
    args = parser.parse_args()

    path = Path(args.evidence)
    if not path.is_file():
        print(json.dumps({
            "state": "TEAM_ACCESS_SANDBOX_BASELINE_EVIDENCE_FILE_NOT_FOUND",
            "path": str(path),
        }, ensure_ascii=False))
        return 2

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_SANDBOX_BASELINE_EVIDENCE_INVALID_JSON",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    review = validate_baseline_evidence(payload)
    print(json.dumps(review, ensure_ascii=False, indent=2))

    if review.get("state") != "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW":
        return 2

    if args.write_template:
        target = Path(args.write_template)
        template = lifecycle_evidence_template(review)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(template, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Lifecycle review template written to: {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
