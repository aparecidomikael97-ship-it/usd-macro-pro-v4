"""CLI for validating a materialized Team Access lifecycle authorization."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from atlasquant_aion_business_team_access_lifecycle_authorization_package import (
    validate_materialized_authorization,
)


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("materialization")
    parser.add_argument("authorization_record")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        materialization = _load(args.materialization)
        record = _load(args.authorization_record)
    except Exception as exc:
        print(json.dumps({
            "state": "TEAM_ACCESS_LIFECYCLE_AUTHORIZATION_PACKAGE_INPUT_ERROR",
            "error": str(exc),
        }, ensure_ascii=False))
        return 2

    result = validate_materialized_authorization(
        materialization,
        record,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)

    if result.get("state") != (
        "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED"
    ):
        return 2

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered + "\n", encoding="utf-8")
    print(f"Authorization package written to: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
