"""Manual-only, explicitly opted-in MT5 7-USD-cross historical tick exporter.

No automatic MetaTrader5 import, initialize, login, symbol_select, trading
calls, workers, network fetches, schedules or background behavior. The caller
must already have an initialized and connected read-only terminal API object.

Each of seven pairs is queried at four fixed macro-event clock anchors with
COPY_TICKS_INFO, strictly within [anchor-5000ms, anchor]. The LAST returned
Bid/Ask tick may be stored only when all reported ticks in that bounded range
have valid UTC millisecond timestamps, legitimate quote grids, and positive
spreads. Missing/stale/future/corrupt data -> NO-GO for the WHOLE archive.

Seven CSVs and one local receipt are written to a NEW private LAB event folder
only AFTER all 28 price snapshots are validated, with exclusive staging,
readback SHA256 and the independent archive validator #1994. No overwrite.
Local source and broker labels are NOT independent first-seen or execution proof.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    _price, _symbol_spec_for_capture, _terminal_company_label,
)
from atlasquant_trader_ppi7_mt5_bidask_tick_preflight_lab import _milliseconds
from atlasquant_trader_us_macro_mt5_bidask_anchor_archive_lab import (
    ANCHORS, EVENTS, PAIR_ORDER, SOURCE_KIND, LocalMT5BidAskAnchorReceipt,
    inspect_local_mt5_7fx_bidask_anchor_archive_lab,
)

SCHEMA="ATLASQUANT_MT5_7FX_MANUAL_BIDASK_TICK_EXPORT_LAB_V1"
_MANUAL_FOLDER=("AtlasQuant","LAB","MT5_7FX_BIDASK_ANCHORS")
_OFFSETS=(-15,15,60,240)
_HEADERS=("anchor","anchor_epoch_msc","tick_time_msc","bid","ask")
_MAX_PER_WINDOW=1000
_MAX_AGE_MS=5000
_OK_REPLAY="LAB_US_MACRO_7FX_TICK_BIDASK_ARCHIVE_DOCUMENTARY_ONLY_NO_GO"


def _blocked(reason:str,*,root_id:str|None=None,read_calls:int=0)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "state":"LAB_MT5_7FX_MANUAL_TICK_EXPORT_BLOCKED_NO_GO",
        "reason":reason,"event_root":root_id,
        "expected_pair_count":7,"expected_anchor_count":4,
        "historical_tick_read_calls":read_calls,
        "tick_snapshots_selected":0,"local_files_written":0,
        "private_event_directory":None,
        "source_kind":SOURCE_KIND,
        "bidask_original_sha256_by_pair_local_claim":None,
        "broker_company_observed_locally_not_authenticated":None,
        "archive_replayed_by_independent_offline_validator":False,
        "historical_data_first_seen_independently_authenticated":False,
        "terminal_company_identity_independently_authenticated":False,
        "quote_completeness_or_executability_authenticated":False,
        "slippage_commission_fills_authenticated":False,
        "out_of_sample_directional_trials":0,
        "forex_accuracy":None,"calibrated_probability":None,
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,"publishable":False,
        "orders_or_positions_accessed":False,
        "terminal_visibility_changed_by_script":False,
        "broker_login_performed":False,
        "new_workers_or_cron_enabled":False,
        "fx28_original_672_slots_changed":False,
        "http_requests":0,"new_cost_brl":0,
    }


def _utc(value:Any)->datetime|None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        return value.astimezone(timezone.utc) if value.utcoffset() is not None else None
    except (ValueError,TypeError,OverflowError):
        return None


def _safe_root(value:Any)->Path|None:
    if not isinstance(value,Path) or not value.is_absolute():
        return None
    if value.parts[-3:]!=_MANUAL_FOLDER or ".." in value.parts:
        return None
    try:
        if any(x.is_symlink() for x in (value,*value.parents)):
            return None
        return value
    except (OSError,RuntimeError,ValueError):
        return None


def _tick_csv_for_pair(
    api:Any,*,pair:str,release:datetime,digits:int,read_counter:list[int],
)->bytes:
    output=StringIO(newline="")
    writer=csv.writer(output,lineterminator="\n")
    writer.writerow(_HEADERS)
    for label,offset in zip(ANCHORS,_OFFSETS):
        anchor=release+timedelta(minutes=offset)
        anchor_ms=int(anchor.timestamp())*1000
        start_ms=anchor_ms-_MAX_AGE_MS
        start=datetime.fromtimestamp(start_ms/1000,tz=timezone.utc)
        read_counter[0]+=1
        ticks=api.copy_ticks_range(pair,start,anchor,api.COPY_TICKS_INFO)
        if ticks is None or not 1<=len(ticks)<=_MAX_PER_WINDOW:
            raise ValueError("MISSING_OR_UNBOUNDED_TICK_WINDOW")
        latest=None
        previous_time=None
        for tick in ticks:
            try:
                ms=_milliseconds(tick["time_msc"])
                seconds=tick["time"]
                if (isinstance(seconds,(bool,float,str))
                        or int(seconds)!=seconds or ms//1000!=int(seconds)
                        or not start_ms<=ms<=anchor_ms
                        or previous_time is not None and ms<previous_time):
                    raise ValueError("TICK_TIME_RANGE_ORDER_OR_SECOND_MISMATCH")
                bid,bid_text=_price(tick["bid"],quote_digits=digits)
                ask,ask_text=_price(tick["ask"],quote_digits=digits)
                if ask<=bid:
                    raise ValueError("TICK_ZERO_OR_CROSSED_SPREAD")
                latest=(ms,bid_text,ask_text)
                previous_time=ms
            except (KeyError,IndexError,TypeError,AttributeError,OverflowError) as exc:
                raise ValueError("MISSING_TICK_TIME_OR_PRICE_FIELDS") from exc
        if latest is None:
            raise ValueError("TICK_QUOTE_WINDOW_EMPTY")
        writer.writerow((label,anchor_ms,latest[0],latest[1],latest[2]))
    return output.getvalue().encode("utf-8")


def export_manual_mt5_7fx_bidask_anchors_lab(
    api:Any,*,event_root:Any,output_root:Any,
    allow_explicit_manual_export:bool,clock:Callable[[],datetime],
)->dict[str,Any]:
    """One-shot, opt-in, already-connected terminal; no live trading paths."""
    root_id=event_root if type(event_root) is str and event_root in EVENTS else None
    out=_blocked("NO_EXPLICIT_MANUAL_OPT_IN_OR_INVALID_PRIVATE_LAB_PATH",root_id=root_id)
    root=_safe_root(output_root)
    if (allow_explicit_manual_export is not True or root_id is None
            or root is None or not callable(clock)):
        return out
    try:
        now=_utc(clock())
    except (ValueError,TypeError,RuntimeError,OverflowError):
        now=None
    if now is None:
        out["reason"]="INVALID_LOCAL_CAPTURE_CLOCK"
        return out
    release=EVENTS[root_id]
    if now<release+timedelta(hours=4):
        out["reason"]="EVENT_OR_H4_TICK_WINDOW_IS_STILL_FUTURE"
        return out
    target=root/root_id
    if target.exists() or target.is_symlink():
        out["reason"]="ORIGINAL_EVENT_ARCHIVE_ALREADY_EXISTS_NO_OVERWRITE"
        return out
    read_counter=[0]
    pending={}
    local_company=None
    try:
        terminal=api.terminal_info()
        if terminal is None or getattr(terminal,"connected",None) is not True:
            raise ValueError("TERMINAL_NOT_ALREADY_CONNECTED")
        local_company=_terminal_company_label(terminal)
        if local_company is None or len(local_company)<2:
            raise ValueError("TERMINAL_COMPANY_LABEL_NOT_VALID")
        for pair in PAIR_ORDER:
            info=api.symbol_info(pair)
            if info is None or type(getattr(info,"visible",None)) is not bool:
                raise ValueError("REQUIRED_CANONICAL_SYMBOL_MISSING")
            visible=info.visible
            spec=_symbol_spec_for_capture(info,pair)
            if spec is None:
                raise ValueError("SYMBOL_BASE_QUOTE_OR_PRECISION_INVALID")
            # Accumulate the number of calls in a mutable proxy so a raised
            # exception cannot report a fabricated success counter.
            raw=_tick_csv_for_pair(
                api,pair=pair,release=release,digits=spec["digits_claim"],
                read_counter=read_counter)
            after=api.symbol_info(pair)
            if (after is None or type(getattr(after,"visible",None)) is not bool
                    or after.visible!=visible):
                raise ValueError("MARKET_WATCH_VISIBILITY_CHANGED_DURING_READ")
            pending[pair]=raw
        ended=_utc(clock())
        if ended is None or ended<now:
            raise ValueError("CAPTURE_CLOCK_BACKWARDS")
    except (ValueError,OSError,TypeError,AttributeError,RuntimeError,
            OverflowError,KeyError,IndexError) as exc:
        return _blocked("MT5_READ_ONLY_TICK_EXPORT_REJECTED:"+str(exc)[:90],
                        root_id=root_id,read_calls=read_counter[0])

    out=_blocked("PRIVATE_LOCAL_ARCHIVE_WRITE_OR_REPLAY_FAILED",
                 root_id=root_id,read_calls=read_counter[0])
    try:
        root.mkdir(parents=True,exist_ok=True)
        if _safe_root(root) is None or target.exists() or target.is_symlink():
            out["reason"]="OUTPUT_DIRECTORY_CHANGED_OR_ARCHIVE_EXISTS"
            return out
        hashes={pair:sha256(pending[pair]).hexdigest() for pair in PAIR_ORDER}
        if len(set(hashes.values()))!=len(PAIR_ORDER):
            out["reason"]="REPEATED_PAIR_ORIGINAL_DIGESTS"
            return out
        receipt=LocalMT5BidAskAnchorReceipt(
            event_root=root_id,source_kind=SOURCE_KIND,
            captured_at_utc=ended,sha256_by_pair=hashes,
            broker_company_label_claim=local_company,
        )
        # Stage all private files, run the standalone replay verifier and
        # only then rename the finished event directory into place.
        with TemporaryDirectory(dir=root,prefix=".uncommitted_bidask_") as tmp:
            stage=Path(tmp)/root_id
            stage.mkdir()
            for pair in PAIR_ORDER:
                file=stage/f"{pair}_BIDASK_ANCHORS.csv"
                with file.open("xb") as stream:
                    stream.write(pending[pair])
                if sha256(file.read_bytes()).hexdigest()!=hashes[pair]:
                    raise ValueError("LOCAL_TICK_ORIGINAL_READBACK_SHA_CHANGED")
            manifest={
                "schema":SCHEMA,"event_root":root_id,
                "source_kind":SOURCE_KIND,
                "captured_at_utc":ended.isoformat(),
                "sha256_by_pair":hashes,
                "broker_company_label_claim":local_company,
                "read_only_no_trades_or_accounts":True,
                "independent_broker_provenance_verified":False,
            }
            with (stage/"receipt.json").open("x",encoding="utf-8") as stream:
                json.dump(manifest,stream,sort_keys=True,ensure_ascii=False)
            check=inspect_local_mt5_7fx_bidask_anchor_archive_lab(
                archive_root=Path(tmp),receipt=receipt,inspected_at_utc=ended)
            if (check["state"]!=
                "LAB_US_MACRO_7FX_TICK_BIDASK_ARCHIVE_DOCUMENTARY_ONLY_NO_GO"
                    or check["replayed_pair_count"]!=len(PAIR_ORDER)
                    or check["trade_authorized"] is not False):
                raise ValueError("INDEPENDENT_LOCAL_BIDASK_REPLAY_REJECTED")
            if target.exists() or target.is_symlink():
                raise ValueError("DESTINATION_ALREADY_EXISTS_NO_OVERWRITE")
            stage.rename(target)
    except (ValueError,OSError,TypeError,RuntimeError,OverflowError):
        return out
    out.update({
        "state":"LAB_MT5_7FX_LOCAL_BIDASK_ORIGINALS_EXPORTED_NO_TRADING",
        "reason":"LOCAL_SNAPSHOTS_AND_SHA_REPLAYED_BROKER_FIRST_SEEN_NOT_ATTESTED",
        "tick_snapshots_selected":len(PAIR_ORDER)*len(ANCHORS),
        "local_files_written":len(PAIR_ORDER)+1,
        "private_event_directory":str(target),
        "bidask_original_sha256_by_pair_local_claim":hashes,
        "broker_company_observed_locally_not_authenticated":local_company,
        "archive_replayed_by_independent_offline_validator":True,
    })
    return out


def _unique_json_pairs(entries:list[tuple[str,Any]])->dict[str,Any]:
    result={}
    for key,value in entries:
        if key in result:
            raise ValueError("DUPLICATED_LOCAL_MANIFEST_JSON_KEY")
        result[key]=value
    return result


def load_manual_mt5_bidask_receipt_lab(
    *,archive_root:Any,event_root:Any,inspected_at_utc:Any,
)->LocalMT5BidAskAnchorReceipt:
    """Reopen a previously exported receipt; never trust an arbitrary dict.

    Raises ValueError on any archive/cutoff mismatch. Replays all 7 CSVs
    under the independently developed #1994 offline source-file validator.
    A local SHA still is not an independent broker/origin attestation.
    """
    root=_safe_root(archive_root)
    now=_utc(inspected_at_utc)
    if root is None or now is None or type(event_root) is not str or event_root not in EVENTS:
        raise ValueError("INVALID_PRIVATE_ROOT_EVENT_OR_REPLAY_CUTOFF")
    folder=root/event_root
    manifest_path=folder/"receipt.json"
    if (folder.is_symlink() or not folder.is_dir()
            or manifest_path.is_symlink() or not manifest_path.is_file()
            or not 100<=manifest_path.stat().st_size<=4096):
        raise ValueError("PRIVATE_LOCAL_RECEIPT_MISSING_OR_UNSAFE")
    try:
        source=json.loads(manifest_path.read_text("utf-8"),
                          object_pairs_hook=_unique_json_pairs)
        if (type(source) is not dict or set(source)!={
            "schema","event_root","source_kind","captured_at_utc",
            "sha256_by_pair","broker_company_label_claim",
            "read_only_no_trades_or_accounts",
            "independent_broker_provenance_verified",
        } or source["schema"]!=SCHEMA or source["event_root"]!=event_root
                or source["source_kind"]!=SOURCE_KIND
                or source["read_only_no_trades_or_accounts"] is not True
                or source["independent_broker_provenance_verified"] is not False
                or type(source["captured_at_utc"]) is not str):
            raise ValueError("MANIFEST_SCHEMA_OR_POLICY_INVALID")
        timestamp=datetime.fromisoformat(source["captured_at_utc"])
        receipt=LocalMT5BidAskAnchorReceipt(
            event_root=event_root,source_kind=SOURCE_KIND,
            captured_at_utc=timestamp,
            sha256_by_pair=source["sha256_by_pair"],
            broker_company_label_claim=source["broker_company_label_claim"],
        )
        replay=inspect_local_mt5_7fx_bidask_anchor_archive_lab(
            archive_root=root,receipt=receipt,inspected_at_utc=now)
        if replay["state"]!=_OK_REPLAY or replay["trade_authorized"] is not False:
            raise ValueError("REPLAY_FAILED_OR_ORIGINAL_TAMPERED")
        return receipt
    except (OSError,UnicodeError,KeyError,TypeError,ValueError,RuntimeError) as exc:
        raise ValueError("LOCAL_RECEIPT_OR_REPLAY_NOT_AUTHENTICATED") from exc


__all__=(
    "SCHEMA","export_manual_mt5_7fx_bidask_anchors_lab",
    "load_manual_mt5_bidask_receipt_lab",
)
