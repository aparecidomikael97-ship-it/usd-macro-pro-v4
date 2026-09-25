"""Migrate an existing AION runtime Checkpoint to the current schema.

No network I/O. The caller supplies an existing JSON file and receives a
normalized upgraded file. Existing runtime data is preserved where the current
canonical schema supports it.

Fail-closed rules:
- source integrity must be CONFIRMED or MIGRATION_REQUIRED;
- dirty persisted checkpoints are not migrated automatically;
- output integrity must be CONFIRMED;
- real trading must remain disabled.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
    ensure_operating_checkpoint,
)


def migrate_checkpoint(input_path:str|Path,output_path:str|Path)->dict[str,Any]:
    source=Path(input_path)
    target=Path(output_path)
    raw=json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw,dict):
        raise ValueError("runtime checkpoint must be an object")

    before=checkpoint_integrity_report(raw)
    if before.get("state") not in {"CONFIRMED","MIGRATION_REQUIRED"}:
        raise ValueError(f"source integrity not write-safe: {before.get('state')}")
    operating=raw.get("operating") if isinstance(raw.get("operating"),dict) else {}
    if bool(operating.get("dirty",False)):
        raise ValueError("persisted runtime checkpoint is dirty; automatic migration blocked")

    upgraded=ensure_operating_checkpoint(raw)
    upgraded["operating"]["dirty"]=False
    upgraded["aion"]["real_trading"]=False

    after=checkpoint_integrity_report(upgraded)
    if after.get("state")!="CONFIRMED":
        raise ValueError(f"migrated integrity not confirmed: {after.get('state')}")

    expected=int(default_checkpoint().get("checkpoint_version") or 0)
    actual=int(upgraded.get("checkpoint_version") or 0)
    if actual<expected:
        raise ValueError(f"migration did not reach current schema V{expected}")
    if bool(upgraded.get("aion",{}).get("real_trading",False)):
        raise ValueError("real trading must remain disabled")

    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(
        json.dumps(upgraded,ensure_ascii=False,indent=2,sort_keys=True,default=str)+"\n",
        encoding="utf-8",
    )
    return {
        "status":"CONFIRMED",
        "before_state":before.get("state"),
        "before_version":int(raw.get("checkpoint_version") or 0),
        "after_version":actual,
        "digest":checkpoint_source_digest(upgraded),
        "real_trading":False,
    }


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    print(json.dumps(migrate_checkpoint(args.input,args.output),ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
