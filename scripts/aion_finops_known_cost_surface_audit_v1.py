"""Read only the eight public source files of the known AION cost-path audit.

Does not read provider credentials, .env, account settings, Render API,
billing accounts, bank statements or GitHub secrets. No writes or network.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from atlasquant_aion_finops_known_cost_surface_audit_v1 import (
    SOURCE_PATHS, MAX_TEXT, known_cost_source_audit,
)


def run_static_audit(root: Path) -> dict:
    try:
        base=root.resolve(strict=True)
        inputs={}
        for name in SOURCE_PATHS:
            path=base/name
            # Explicit known path only, never follow source symlinks or read
            # secrets, user folders, env, tokens or repository history.
            if path.is_symlink() or not path.is_file():
                raise ValueError("SOURCE_NOT_REGULAR_FILE")
            if path.stat().st_size>MAX_TEXT*4:
                raise ValueError("SOURCE_OVERSIZE")
            contents=path.read_text("utf-8")
            if len(contents)>MAX_TEXT:
                raise ValueError("SOURCE_TOO_LARGE")
            inputs[name]=contents
        return known_cost_source_audit(inputs)
    except (ValueError, OSError, UnicodeError):
        return {
            "schema":"ATLASQUANT_AION_FINOPS_KNOWN_COST_SOURCE_AUDIT_V1",
            "state":"BLOCKED",
            "blockers":["REQUIRED_KNOWN_SOURCE_NOT_READABLE"],
            "secrets_examined_or_exported":False,
            "billable_api_called_during_scan":False,
        }


def main() -> int:
    result=run_static_audit(ROOT)
    print(json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=True))
    return 0 if result.get("state")=="KNOWN_COST_SURFACES_STATIC_REVIEW_REQUIRED" else 2


if __name__ == "__main__":
    sys.exit(main())
