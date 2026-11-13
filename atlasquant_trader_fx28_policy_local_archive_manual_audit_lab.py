"""Manual read-only report of local G8 policy source archive consistency.

Run explicitly with --audit on the machine containing the issuer source
archives. No web request, broker call, file writes, GitHub comments or
alerts. The cutoff is the local current UTC clock; its accuracy is not
independently authenticated and cannot establish historical first-seen.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os

from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    inspect_fx28_official_policy_archive_replay_lab,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="FX28 bank-source archive LAB audit")
    parser.add_argument("--audit", action="store_true",
                        help="Read already-saved local issuer files; never fetch.")
    args = parser.parse_args()
    if not args.audit:
        print("LAB_NO_ACTION: pass --audit to inspect local public files (read-only)")
        return 2
    report = inspect_fx28_official_policy_archive_replay_lab(
        local_appdata=os.environ.get("LOCALAPPDATA", ""),
        decision_at_utc=datetime.now(timezone.utc).replace(microsecond=0),
    )
    # No issuer source body, local absolute path, account data or number of
    # pips is emitted. This is a policy-source inventory, NOT a forecast.
    print(json.dumps({
        "state": report["state"],
        "reason": report["reason"],
        "policy_source_contracts": report["policy_issuer_contracts_available"],
        "local_archive_folder_present": report["folder_present_on_this_runtime"],
        "policy_currencies_locally_checked":
            report["currencies_with_local_original_bytes_validated"],
        "checked_currency_codes": report["currencies_locally_checked"],
        "missing_currency_codes": report["currencies_missing"],
        "rejected_currency_reasons": report["currencies_rejected"],
        "pairs_with_both_policy_originals":
            report["pairs_with_both_policy_originals_locally_checked"],
        "pairs_without_both_policy_originals":
            report["pairs_lacking_at_least_one_policy_original"],
        "historical_pit_verified": False,
        "full_bilateral_cpi_verified": False,
        "forecasts_pre_event_witnessed": False,
        "calibrated_directional_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "new_cost_brl": 0,
    }, ensure_ascii=False, indent=2))
    return 0 if report["folder_present_on_this_runtime"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
