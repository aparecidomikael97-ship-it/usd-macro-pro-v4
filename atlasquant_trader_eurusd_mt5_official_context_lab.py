"""EUR/USD LAB: connect a private MT5 snapshot to four official page references.

This is NOT an operational macro feed. The original official web pages were
researched retrospectively, not independently captured before past trades;
HICP/CPI months and Fed/ECB rate instruments are not directly comparable.
The integration exposes evidence gaps and never promotes a price direction.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from atlasquant_trader_eurusd_nov6_official_asof_lab import (
    inspect_eurusd_nov6_official_asof_lab,
)
from atlasquant_trader_mt5_macro_join_lab import join_mt5_macro_lab

SCHEMA = "ATLASQUANT_TRADER_EURUSD_MT5_FOUR_OFFICIAL_DOCS_READINESS_LAB_V1"
PRICE_OK = "LAB_PRICE_MACRO_COVERAGE_AUDITED_UNATTESTED"
DOC_OK = "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED"
MAX_PRICE_BYTES = 1_000_000
MAX_CASEBOOK_BYTES = 6_000


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "evaluated_at_utc": None,
        "mt5_snapshot_sha256": None, "official_casebook_sha256": None,
        "price_pairs_validated": 0,
        "eurusd_m15_recent": False, "eurusd_d1_recent": False,
        "eurusd_w1_recent": False,
        "official_document_refs_visible": 0,
        "documents": [], "inflation_reference_periods_match": False,
        "inflation_methodologies_comparable": False,
        "rate_instruments_directly_comparable": False,
        "next_us_cpi_oct2026_event_utc": "2026-11-10T13:30:00Z",
        "next_us_cpi_oct2026_actual": None,
        "next_us_cpi_oct2026_headline_yoy_eligible": False,
        "macro_source_vintage_independently_verified": False,
        "broker_price_origin_independently_verified": False,
        "all_indicators_same_period_and_metric": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_eurusd_mt5_official_context_lab(
    *, mt5_snapshot_raw: Any, official_casebook_raw: Any,
    as_of_utc: datetime,
) -> dict[str, Any]:
    """Reuse already-tested validators; document context cannot become a bias."""
    out = _blocked("INVALID_SNAPSHOT_CASEBOOK_OR_CLOCK")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or as_of_utc.microsecond != 0
            or not isinstance(mt5_snapshot_raw, bytes)
            or not 100 <= len(mt5_snapshot_raw) <= MAX_PRICE_BYTES
            or not isinstance(official_casebook_raw, bytes)
            or not 200 <= len(official_casebook_raw) <= MAX_CASEBOOK_BYTES):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    price = join_mt5_macro_lab(snapshot_raw=mt5_snapshot_raw,
                               macro_raw_by_pair={}, decision_at_utc=now)
    if price["state"] != PRICE_OK or price["price_pairs_validated"] != 28:
        out["reason"] = "MT5_CLOSED_BARS_FAILED_CHRONOLOGY_OR_STRUCTURE"
        return out
    documents = inspect_eurusd_nov6_official_asof_lab(
        official_casebook_raw, as_of_utc=now)
    if documents["state"] != DOC_OK or documents["visible_document_count"] != 4:
        out["reason"] = "FOUR_OFFICIAL_PAGES_NOT_VISIBLE_OR_CASEBOOK_UNVERIFIED"
        return out
    row = price["pairs"].get("EUR/USD")
    if row is None or row["macro_state"] != "MISSING":
        out["reason"] = "DOCUMENT_REFERENCES_CANNOT_BE_MISLABELED_AS_MACRO_RECEIPTS"
        return out
    present = documents["visible_documents_as_retrospective_references"]
    if {(d["currency"], d["family"]) for d in present} != {
        ("USD", "INFLATION"), ("USD", "POLICY"),
        ("EUR", "INFLATION"), ("EUR", "POLICY"),
    }:
        out["reason"] = "OFFICIAL_PAGE_SIDES_OR_TYPES_INCOMPLETE"
        return out
    out.update({
        "state": "LAB_EURUSD_PRICE_AND_OFFICIAL_PAGES_VISIBLE_UNATTESTED_NO_BIAS",
        "reason": "INCOMPATIBLE_METRICS_NONPIT_PAGES_AND_NO_PREDICTION_PROOF",
        "evaluated_at_utc": now.isoformat(),
        "mt5_snapshot_sha256": price["snapshot_sha256"],
        "official_casebook_sha256": sha256(official_casebook_raw).hexdigest(),
        "price_pairs_validated": price["price_pairs_validated"],
        "eurusd_m15_recent": row["timeframes"]["M15"]["recent_for_research"],
        "eurusd_d1_recent": row["timeframes"]["D1"]["recent_for_research"],
        "eurusd_w1_recent": row["timeframes"]["W1"]["recent_for_research"],
        "official_document_refs_visible": len(present),
        "documents": present,
        "inflation_reference_periods_match": documents["inflation_observation_periods_match"],
        "inflation_methodologies_comparable": documents["inflation_statistical_methods_comparable"],
        "rate_instruments_directly_comparable": documents["policy_rate_instruments_directly_comparable"],
    })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline EUR/USD MT5 + official docs LAB")
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--casebook", required=True, type=Path)
    parser.add_argument("--out", type=Path, help="New local JSON report, no overwrite")
    args = parser.parse_args(argv)
    try:
        if (not args.snapshot.is_file() or not args.casebook.is_file()
                or not 100 <= args.snapshot.stat().st_size <= MAX_PRICE_BYTES
                or not 200 <= args.casebook.stat().st_size <= MAX_CASEBOOK_BYTES):
            print("FILES_MISSING_OR_EXCESSIVE")
            return 2
        price_raw = args.snapshot.read_bytes()
        case_raw = args.casebook.read_bytes()
    except OSError:
        print("FILES_UNAVAILABLE")
        return 2
    report = inspect_eurusd_mt5_official_context_lab(
        mt5_snapshot_raw=price_raw, official_casebook_raw=case_raw,
        as_of_utc=datetime.now(timezone.utc).replace(microsecond=0),
    )
    if args.out and report["state"] != "LAB_BLOCKED":
        try:
            with args.out.open("x", encoding="utf-8") as destination:
                json.dump(report, destination, ensure_ascii=False, sort_keys=True, allow_nan=False)
                destination.write("\n")
        except OSError:
            print("REPORT_FILE_NOT_CREATED")
            return 2
    print(json.dumps({k: report[k] for k in (
        "state", "reason", "price_pairs_validated", "official_document_refs_visible",
        "eurusd_m15_recent", "eurusd_d1_recent", "eurusd_w1_recent",
        "operational_bias", "trade_authorized")}, ensure_ascii=False, sort_keys=True))
    return 0 if report["state"] != "LAB_BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
