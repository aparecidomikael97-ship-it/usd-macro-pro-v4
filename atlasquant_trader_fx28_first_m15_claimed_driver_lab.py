"""Draft-only safe integration of atomic claim -> existing FX28 M15 collector.

NOT scheduled on AM12. No CLI and no direct import of MetaTrader5.
Only an explicitly supplied API object is used, solely by the unchanged
collector; no trading API is invoked here. All failures preserve the marker.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from atlasquant_trader_fx28_first_m15_atomic_claim_lab import (
    WINDOW, CLAIM_EARLIEST_UTC, CLAIM_DEADLINE_UTC, claim_once_lab,
)
from atlasquant_trader_fx28_ny17_m15_writeonce_capture_lab import collect_window_lab
from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_fx28_m15_semantic_postcheck_lab import assert_semantics

SCHEMA="ATLASQUANT_FX28_FIRST_M15_CLAIMED_CAPTURE_DRIVER_LAB_V1"

def run_claimed_first_m15_lab(
    api:Any,*,terminal_path:str,output_root:Path,
    clock:Callable[[],datetime],
)->dict[str,Any]:
    """EXACTLY ONE claimed window attempt, with no implicit retries.

    On prior marker, archive, failed MT5 query or unexpected exception,
    never perform another MT5 call. Empty arrays may remain documented
    gaps. An exception during the collector preserves the permanent marker.
    """
    out={
        "schema":SCHEMA,
        "state":"LAB_CLAIMED_FIRST_M15_NO_GO",
        "reason":"NOT_ATTEMPTED",
        "window":WINDOW,
        "claim_created":False,
        "claim_sha256":None,
        "collector_state":None,
        "collector_reason":None,
        "archive_dir":None,
        "captured_m15_total":None,
        "missing_m15_total":None,
        "semantically_verified_symbols":None,
        "independent_broker_price_source_attested":False,
        "prediction_witness_authenticated":False,
        "trade_authorized":False,
        "publishable":False,
        "currently_connected_to_scheduled_runner":False,
        "automatic_retries_allowed":False,
    }
    if (type(terminal_path) is not str or not _terminal_path_ok(terminal_path)
            or not isinstance(output_root,Path) or not callable(clock)):
        out["reason"]="INVALID_CALL_PARAMETERS_NO_CLAIM"
        return out
    # Always atomically reserve the attempt BEFORE touching the MT5 API.
    claim=claim_once_lab(archive_root=output_root,clock=clock)
    out["claim_created"]=claim["exclusive_claim_created"]
    out["claim_sha256"]=claim.get("claim_sha256")
    if not claim["exclusive_claim_created"]:
        out["reason"]=claim["reason"]
        return out
    try:
        # The atomic claim's timestamp is only the time at marker creation.
        # Re-read the clock BEFORE any MT5 call. A paused process could
        # resume after 23:00 UTC while retaining an earlier claimed time.
        pre_collect=clock()
        if (not isinstance(pre_collect,datetime)
                or pre_collect.tzinfo is None
                or pre_collect.utcoffset() is None):
            out["reason"]="POST_CLAIM_CLOCK_INVALID_NO_MT5_NO_RETRY"
            return out
        pre_collect=pre_collect.astimezone(timezone.utc)
        if not CLAIM_EARLIEST_UTC<=pre_collect<CLAIM_DEADLINE_UTC:
            out["reason"]="POST_CLAIM_CAPTURE_START_OUTSIDE_DEADLINE_NO_MT5_NO_RETRY"
            return out

        captured=collect_window_lab(
            api,window=WINDOW,terminal_path=terminal_path,
            output_root=output_root,clock=clock)
        out["collector_state"]=captured["state"]
        out["collector_reason"]=captured["reason"]
        out["captured_m15_total"]=captured.get("captured_m15_total")
        out["missing_m15_total"]=captured.get("missing_m15_total")
        archive=captured.get("archive_dir")
        if archive:
            out["archive_dir"]=archive
        # After broker API returns, a late archive is retained for forensic
        # review but is NEVER promoted to prospective first-M15 evidence.
        # No retry; permanent claim remains reserved.
        post_collect=clock()
        if (not isinstance(post_collect,datetime)
                or post_collect.tzinfo is None
                or post_collect.utcoffset() is None):
            out["reason"]="POST_COLLECT_CLOCK_INVALID_NO_RETRY"
            return out
        post_collect=post_collect.astimezone(timezone.utc)
        if not CLAIM_EARLIEST_UTC<=post_collect<CLAIM_DEADLINE_UTC:
            out["reason"]="POST_COLLECT_OUTSIDE_DEADLINE_PROSPECTIVE_REJECTED_NO_RETRY"
            return out
        if not archive:
            out["reason"]="COLLECTOR_BLOCKED_CLAIM_PERMANENT_NO_RETRY"
            return out
        checked=assert_semantics(Path(archive))
        if checked["symbols_structurally_verified"]!=28:
            out["reason"]="SEMANTIC_READBACK_INCOMPLETE_NO_RETRY"
            return out
        out["semantically_verified_symbols"]=28
        count=out["captured_m15_total"]
        gaps=out["missing_m15_total"]
        if (type(count) is not int or type(gaps) is not int
                or not 0 <= count <= 28 or count + gaps != 28
                or checked["m15_rows_semantically_checked"] != count
                or checked["m15_gaps_from_base_verifier"] != gaps):
            out["reason"]="CLAIMED_COHORT_COUNTS_INCONSISTENT_NO_RETRY"
            return out
        # Archive integrity can succeed even if ZERO broker bars exist.
        # Distinguish a valid gap record from genuine observed prices.
        if count == 0:
            out["state"]="LAB_CLAIMED_FIRST_M15_ZERO_PRICE_OBSERVED_NO_GO"
            out["reason"]="ZERO_OF_28_NOMINAL_BARS_NO_MARKET_PRICE_NO_RETRY"
        elif count < 28:
            out["state"]="LAB_CLAIMED_FIRST_M15_PARTIAL_PRICE_OBSERVED_NO_GO"
            out["reason"]="INCOMPLETE_NOMINAL_M15_COHORT_NO_RETRY"
        else:
            out["state"]="LAB_CLAIMED_FIRST_M15_ARCHIVE_CHECKED_NO_GO"
            out["reason"]="ALL_28_NOMINAL_M15_ROWS_LOCAL_CLAIM_ONLY_NO_BROKER_PIT"
        return out
    except Exception as exc:
        # Do not delete the claimed marker or repeat IO. Keep diagnostic
        # type only; no raw broker payload or local account data in output.
        out["reason"]="CLAIMED_CAPTURE_EXCEPTION_"+type(exc).__name__+"_NO_RETRY"
        return out

__all__=("SCHEMA","run_claimed_first_m15_lab")
