"""Offline seven-USD-FX MT5 historical Bid/Ask anchor receipt validation, LAB.

Unlike M15 bar spread samples, local tick-level originals must declare
four Bid/Ask snapshots per pair immediately BEFORE fixed event-relative
UTC anchors. Local SHA/CSV/geometry validation CANNOT independently attest
publisher first-seen, actual terminal identity, tick-feed completeness,
broker execution, commissions, slippage, causality, or financial accuracy.

Pure read-only Python. No MetaTrader5 import, network, file writes, orders,
login or background workers. The source-kind label is only a local claim.
Seven USD crosses x four anchors = 28 related price observations,
NOT 28 independent macro predictions.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from typing import Any

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import EVENTS as DEC_EVENTS

SCHEMA="ATLASQUANT_US_MACRO_MT5_7FX_TICK_BIDASK_ANCHOR_ARCHIVE_LAB_V1"
SOURCE_KIND="MT5_COPY_TICKS_INFO_HISTORICAL_LOCAL_CLAIM_ONLY"
EVENTS={
    "US_PPI_OCT2026":datetime(2026,11,13,13,30,tzinfo=timezone.utc),
    **{root:dt for root,_,_,dt in DEC_EVENTS},
}
PAIR_ORDER=tuple(USD_FX)
ANCHORS=("PRE15","POST15","POST60","POST240")
_OFFSETS=(-15,15,60,240)
_FIELDS=("anchor","anchor_epoch_msc","tick_time_msc","bid","ask")
_MAX_CSV_BYTES=4096
_MAX_QUOTE_AGE=5000
_DIGEST=re.compile(r"[0-9a-f]{64}\Z")
_INT=re.compile(r"[1-9][0-9]{12}\Z")
_PRICE=re.compile(r"(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,8})?\Z")


@dataclass(frozen=True)
class LocalMT5BidAskAnchorReceipt:
    event_root:str
    source_kind:str
    captured_at_utc:datetime
    sha256_by_pair:dict[str,str]
    broker_company_label_claim:str


def _utc(t:Any)->datetime|None:
    if type(t) is not datetime or t.tzinfo is None:
        return None
    try:
        return t.astimezone(timezone.utc) if t.utcoffset() is not None else None
    except (ValueError,TypeError,OverflowError):
        return None


def _blocked(reason:str,*,event_root:str|None=None)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "state":"LAB_US_MACRO_7FX_TICK_BIDASK_ARCHIVE_BLOCKED_HARD_NO_GO",
        "reason":reason,
        "event_root":event_root,
        "fixed_event_release_utc":EVENTS[event_root].isoformat()
            if event_root in EVENTS else None,
        "expected_usd_crosses":list(PAIR_ORDER),
        "expected_anchor_names":list(ANCHORS),
        "expected_pair_count":7,"expected_quote_rows":28,
        "replayed_pair_count":0,"replayed_bidask_anchor_rows":0,
        "local_quote_spread_samples_bps_by_pair":None,
        "missing_pair_means_whole_study_abstains":True,
        "quote_age_limit_milliseconds":_MAX_QUOTE_AGE,
        "prices_are_historical_receipt_claims_only":True,
        "mt5_broker_identity_independently_authenticated":False,
        "quote_bid_ask_source_first_seen_independently_authenticated":False,
        "tick_stream_complete_and_latest_quote_independently_verified":False,
        "bidask_at_execution_venue_independently_verified":False,
        "slippage_commission_and_order_fill_verified":False,
        "actual_trading_cost_verified":False,
        "net_return_or_pnl_calculated":False,
        "forecast_precommitted_and_verified":False,
        "independent_fx_directional_trials":0,
        "historical_forex_accuracy":None,"calibrated_probability":None,
        "operational_bias":"AGUARDAR","publishable":False,
        "trade_authorized":False,"mt5_calls":0,
        "http_requests":0,"file_writes":0,
        "worker_enabled":False,"scheduler_enabled":False,
        "fx28_original_672_slots_changed":False,"new_cost_brl":0,
    }


def _numeric(raw:Any)->Decimal|None:
    if type(raw) is not str or _PRICE.fullmatch(raw) is None:
        return None
    try:
        n=Decimal(raw)
        return n if n.is_finite() and n>0 else None
    except (ValueError,InvalidOperation,OverflowError):
        return None


def _read_one_pair(*,folder:Path,pair:str,digest:str,release:datetime)->list[dict[str,Any]]:
    file=folder/f"{pair}_BIDASK_ANCHORS.csv"
    if (file.is_symlink() or not file.is_file()
            or not 100<=file.stat().st_size<=_MAX_CSV_BYTES):
        raise ValueError("PAIR_ORIGINAL_MISSING_SYMLINK_OR_WRONG_SIZE")
    raw=file.read_bytes()
    if sha256(raw).hexdigest()!=digest:
        raise ValueError("PRICE_TICK_ORIGINAL_SHA256_CHANGED")
    try:
        reader=csv.DictReader(StringIO(raw.decode("utf-8","strict"),newline=""))
        if tuple(reader.fieldnames or ())!=_FIELDS:
            raise ValueError("BIDASK_CSV_COLUMNS_NOT_EXACTLY_REGISTERED")
        rows=list(reader)
    except (UnicodeError,csv.Error) as exc:
        raise ValueError("BIDASK_CSV_CORRUPT") from exc
    if len(rows)!=len(ANCHORS):
        raise ValueError("FOUR_CANONICAL_ANCHORS_REQUIRED_PER_PAIR")
    output=[]
    for i,row in enumerate(rows):
        if (None in row or len(row)!=len(_FIELDS)
                or any(type(value) is not str for value in row.values())
                or row["anchor"]!=ANCHORS[i]):
            raise ValueError("ANCHOR_ROW_DUPLICATED_MISSING_OR_OUT_OF_ORDER")
        a,t=row["anchor_epoch_msc"],row["tick_time_msc"]
        if _INT.fullmatch(a) is None or _INT.fullmatch(t) is None:
            raise ValueError("MILLISECOND_TICK_TIMESTAMPS_INVALID")
        anchor_ms=int((release+timedelta(minutes=_OFFSETS[i])).timestamp())*1000
        if int(a)!=anchor_ms or not 0<=int(a)-int(t)<=_MAX_QUOTE_AGE:
            raise ValueError("TICK_AFTER_ANCHOR_STALE_OR_NOT_FROZEN")
        bid,ask=_numeric(row["bid"]),_numeric(row["ask"])
        if bid is None or ask is None or bid>=ask:
            raise ValueError("NO_POSITIVE_NONCROSSED_BIDASK_AT_FROZEN_ANCHOR")
        spread_bps=((ask-bid)/((bid+ask)/Decimal(2))*Decimal(10000)).quantize(
            Decimal("0.001"),rounding=ROUND_HALF_UP)
        output.append({
            "anchor":ANCHORS[i],
            "fixed_anchor_utc":(release+timedelta(minutes=_OFFSETS[i])).isoformat(),
            "tick_age_milliseconds_local_claim":int(a)-int(t),
            "bid_quote_local_claim":format(bid,"f"),
            "ask_quote_local_claim":format(ask,"f"),
            "bid_ask_spread_bps_local_claim":format(spread_bps,"f"),
            "historical_quote_not_executable_spread_or_fill":True,
        })
    return output


def inspect_local_mt5_7fx_bidask_anchor_archive_lab(
    *,archive_root:Any,receipt:Any,inspected_at_utc:Any,
)->dict[str,Any]:
    """All seven local original files or NONE; never partial statistics."""
    root_id=(receipt.event_root if type(receipt) is LocalMT5BidAskAnchorReceipt
             and type(receipt.event_root) is str and receipt.event_root in EVENTS
             else None)
    out=_blocked("SOURCE_EVENT_RECEIPT_OR_RESEARCH_CUTOFF_INVALID",event_root=root_id)
    now=_utc(inspected_at_utc)
    if (now is None or type(receipt) is not LocalMT5BidAskAnchorReceipt
            or root_id is None or receipt.source_kind!=SOURCE_KIND
            or type(receipt.sha256_by_pair) is not dict
            or set(receipt.sha256_by_pair)!=set(PAIR_ORDER)
            or any(type(v) is not str or _DIGEST.fullmatch(v) is None
                   for v in receipt.sha256_by_pair.values())
            or len(set(receipt.sha256_by_pair.values()))!=len(PAIR_ORDER)
            or type(receipt.broker_company_label_claim) is not str
            or not 2<=len(receipt.broker_company_label_claim)<=100
            or not receipt.broker_company_label_claim.isprintable()):
        return out
    captured=_utc(receipt.captured_at_utc)
    release=EVENTS[root_id]
    close=release+timedelta(hours=4)
    if now<close:
        out["reason"]="FUTURE_EVENT_OR_FOUR_HOUR_REACTION_WINDOW_NOT_CLOSED"
        return out
    if captured is None or not close<=captured<=now:
        out["reason"]="HISTORICAL_TICK_EXPORT_CAPTURE_CLOCK_INVALID"
        return out
    try:
        root=Path(archive_root)
        folder=root/root_id
        if (root.is_symlink() or folder.is_symlink()
                or not root.is_dir() or not folder.is_dir()):
            out["reason"]="PRIVATE_LOCAL_ARCHIVE_DIRECTORY_REQUIRED"
            return out
        stats={}
        for pair in PAIR_ORDER:
            stats[pair]=_read_one_pair(
                folder=folder,pair=pair,digest=receipt.sha256_by_pair[pair],
                release=release)
    except (OSError,ValueError,TypeError,OverflowError,UnicodeError,
            RuntimeError,RecursionError):
        out["reason"]="ONE_OR_MORE_BIDASK_ORIGINALS_FAILED_STRICT_REPLAY"
        return out
    out.update({
        "state":"LAB_US_MACRO_7FX_TICK_BIDASK_ARCHIVE_DOCUMENTARY_ONLY_NO_GO",
        "reason":"SEVEN_LOCAL_MT5_TICK_FILES_REPLAYED_NOT_BROKER_OR_EXECUTION_ATTESTED",
        "replayed_pair_count":len(stats),
        "replayed_bidask_anchor_rows":len(stats)*len(ANCHORS),
        "local_quote_spread_samples_bps_by_pair":stats,
    })
    return out


__all__=(
    "SCHEMA","SOURCE_KIND","EVENTS","PAIR_ORDER","ANCHORS",
    "LocalMT5BidAskAnchorReceipt",
    "inspect_local_mt5_7fx_bidask_anchor_archive_lab",
)
