"""Run a SYNTHETIC local acquisition boundary demo for A139 CI (NO LIVE DATA).

This is not Autopilot, Coleta, AION Worker, an external data client or a
production market collection implementation. Output only to runner.temp.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from atlasquant_market_boundary_a139 import (
    MemoryOnlyReservationLedger,SyntheticMarketFeed,collect_synthetic_market,
)


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--checkout-root",required=True)
    parser.add_argument("--output-dir",required=True)
    parser.add_argument("--source-sha",required=True)
    args=parser.parse_args()
    sha=args.source_sha.lower()
    if len(sha)!=40 or any(ch not in "0123456789abcdef" for ch in sha):
        print('{"status":"BLOCKED","reason":"BAD_SOURCE_SHA"}')
        return 2
    feed=SyntheticMarketFeed({
        "EUR/USD":{"bid":1.1,"ask":1.1002},
        "USD/JPY":{"bid":150.0,"ask":150.02},
    })
    ledger=MemoryOnlyReservationLedger(limit=2)
    result=collect_synthetic_market(
        run_id="labrun139"+sha[:12],
        symbols=("EUR/USD","USD/JPY"),
        feed=feed,
        quota=ledger,
        output_dir=Path(args.output_dir),
        checkout_root=Path(args.checkout_root),
        observed_at="2026-10-21T23:00:00Z",
    )
    if result.get("status")!="SYNTHETIC_OUTPUT_NOT_LIVE":
        print(json.dumps(result,sort_keys=True))
        return 1
    file=Path(args.output_dir)/result["filename"]
    result["synthetic_artifact_sha256"]=hashlib.sha256(file.read_bytes()).hexdigest()
    result["source_commit_untrusted"]=sha
    result["quota_reserved_units_memory_only"]=ledger.reserved_units
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
