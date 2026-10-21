"""AION P0 A139 — synthetic-only market acquisition/quota/output boundary (LAB).

This module deliberately has NO real HTTP/provider/GitHub writer. It models
the separation needed BEFORE a paid data-source integration can be reviewed.
Only the exact SyntheticMarketFeed type can be used; no config/env flag
upgrades its authority. A memory-only quota ledger is NOT a durable
production credit reservation and provides NO exactly-once guarantee.

The output is outside the checkout; no runtime checkpoint path can be chosen.
No synthetic quote should be called live, recent or externally authenticated.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any

SCHEMA="AION_P0_MARKET_SYNTHETIC_ACQUISITION_BOUNDARY_V1"
SYMBOL_ALLOWLIST=frozenset({"EUR/USD","USD/JPY","GBP/USD"})
RUN_ID_PATTERN=re.compile(r"[a-z][a-z0-9_-]{7,47}")
SECRET_KEYS=frozenset({
    "token","password","api_key","secret","authorization","private_key",
    "client_secret","access_key","github_token_historico","gh_token_app",
    "owner_approved","independent_witness","verified_owner",
})
MAX_OUTPUT_BYTES=32_768


def canonical_json(value:Any)->bytes:
    return (json.dumps(
        value,
        ensure_ascii=False,sort_keys=True,separators=(",",":"),
        allow_nan=False,
    )+"\n").encode("utf-8")


class SyntheticMarketFeed:
    """Explicitly named fake source. read() MUST NOT call any network."""
    def __init__(self,quotes:dict[str,Any],*,events:list[str]|None=None):
        if type(quotes) is not dict:
            raise TypeError("Synthetic market fixtures must be a dict")
        self.quotes=quotes
        self.calls:list[str]=[]
        self.events=events

    def read(self,symbol:str):
        self.calls.append(symbol)
        if self.events is not None:
            self.events.append("read:"+symbol)
        value=self.quotes[symbol]
        if isinstance(value,Exception):
            raise value
        return value


class MemoryOnlyReservationLedger:
    """LAB model: holds ambiguous reservations; NEVER retries or refunds."""
    def __init__(self,*,limit:int,events:list[str]|None=None,available:bool=True):
        if type(limit) is not int or not (1<=limit<=100):
            raise ValueError("Memory LAB budget limit must be 1..100")
        if type(available) is not bool:
            raise ValueError("Ledger availability must be a bool")
        self.limit=limit
        self.events=events
        self.available=available
        self.reserved_units=0
        self.reservations:dict[str,int]={}

    def reserve(self,run_id:str,units:int)->bool:
        if (
            not self.available or type(units) is not int or units<=0
            or run_id in self.reservations
            or self.reserved_units+units>self.limit
        ):
            return False
        self.reservations[run_id]=units
        self.reserved_units+=units
        if self.events is not None:
            self.events.append(f"reserve:{run_id}:{units}")
        return True


def output_name(run_id:str)->str:
    if type(run_id) is not str or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("Invalid synthetic run identifier")
    return f"aion_a139_synthetic_market_{run_id}.json"


def _blocked(status:str,reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "status":status,
        "reason":reason,
        "saved":False,
        "market_files_written":0,
        "external_provider_called":False,
        "runtime_write_authorized":False,
        "independent_witness_enrolled":False,
        "human_owner_verified":False,
        "automatic_retry_allowed":False,
        "worker_executed":False,
        "source_authority":"SYNTHETIC_FIXTURE_ONLY",
    }


def _validate_quote(value:Any)->dict[str,float]:
    if not isinstance(value,dict) or type(value) is not dict:
        raise ValueError("Quote fixture must be a literal object")
    if set(value)!={"bid","ask"}:
        raise ValueError("Quote fixture fields must be exactly bid,ask")
    bid=value["bid"]
    ask=value["ask"]
    if type(bid) not in (int,float) or type(ask) not in (int,float):
        raise ValueError("Quote prices must be numbers, not booleans")
    if not math.isfinite(bid) or not math.isfinite(ask):
        raise ValueError("No non-finite synthetic prices")
    if not (0<float(bid)<float(ask)):
        raise ValueError("Bid must be strictly below ask")
    return {"bid":float(bid),"ask":float(ask)}


def _safe_output_dir(output_dir:Any,checkout_root:Any,filename:str)->Path:
    try:
        output=Path(output_dir)
        root=Path(checkout_root)
    except (TypeError,ValueError) as exc:
        raise ValueError("Invalid output or checkout directory") from exc
    if not output.is_absolute() or not root.is_absolute():
        raise ValueError("Absolute output and checkout directories required")
    if not root.is_dir() or not output.is_dir():
        raise ValueError("Checkout and isolated output directory must already exist")
    # Reject a direct symlink as well as a symlink within the output path.
    for component in (output,*output.parents):
        if component.is_symlink():
            raise ValueError("Symlink output path is unsafe")
    resolved_output=output.resolve(strict=True)
    resolved_root=root.resolve(strict=True)
    if resolved_output==resolved_root or resolved_output.is_relative_to(resolved_root):
        raise ValueError("Output must be outside repository")
    destination=resolved_output/filename
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Do not overwrite a previous market artifact")
    return destination


def collect_synthetic_market(
    *,run_id, symbols, feed, quota,
    output_dir,checkout_root,observed_at,
)->dict[str,Any]:
    """Acquire explicit fake quotes only, reserve before read, write once.

    No live provider adaptation exists in this module. Even a successful
    result is SYNTHETIC_OUTPUT_NOT_LIVE and never a production receipt.
    """
    try:
        filename=output_name(run_id)
        if type(feed) is not SyntheticMarketFeed:
            raise ValueError("Only the explicit in-memory fake is admissible")
        if type(quota) is not MemoryOnlyReservationLedger:
            raise ValueError("Only the in-memory LAB ledger is admissible")
        if type(symbols) not in (tuple,list) or len(symbols)==0:
            raise ValueError("At least one literal market symbol is needed")
        if (
            len(symbols)>len(SYMBOL_ALLOWLIST)
            or any(type(x) is not str or x not in SYMBOL_ALLOWLIST for x in symbols)
            or len(set(symbols))!=len(symbols)
        ):
            raise ValueError("Unlisted/duplicate symbol")
        if type(observed_at) is not str or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",observed_at
        ):
            raise ValueError("Unparseable synthetic clock value")
        moment=datetime.fromisoformat(observed_at.replace("Z","+00:00"))
        if moment.tzinfo!=timezone.utc:
            raise ValueError("Expected UTC synthetic clock")
        destination=_safe_output_dir(output_dir,checkout_root,filename)
    except (OSError,TypeError,ValueError) as exc:
        return _blocked("BLOCKED_NO_PROVIDER_FETCH",type(exc).__name__)
    if not quota.reserve(run_id,len(symbols)):
        return _blocked("BLOCKED_NO_PROVIDER_FETCH","LAB_BUDGET_UNAVAILABLE_OR_DUPLICATE")
    # There is deliberately NO "release" operation on an uncertain outcome.
    collected={}
    for symbol in symbols:
        try:
            collected[symbol]=_validate_quote(feed.read(symbol))
        except (Exception,) as exc:
            # Any unknown/missing/ambiguous read stays reserved, no replay.
            # This is a fake reader, but the conservative rule models H0.
            return _blocked("UNCERTAIN_NO_AUTOMATIC_RETRY",type(exc).__name__)
    payload={
        "schema":"AION_A139_SYNTHETIC_QUOTES_V1",
        "run_id":run_id,
        "quotes":collected,
    }
    raw_payload=canonical_json(payload)
    envelope={
        "schema":SCHEMA,
        "run_id":run_id,
        "observed_at":observed_at,
        "freshness_status":"NOT_VERIFIED_NOT_LIVE",
        "source_authority":"SYNTHETIC_FIXTURE_ONLY",
        "provider_fetch_performed":False,
        "external_provider_called":False,
        "runtime_write_authorized":False,
        "independent_witness_enrolled":False,
        "human_owner_verified":False,
        "worker_executed":False,
        "automatic_retry_allowed":False,
        "reservation_state":"LAB_RESERVED_NOT_REFUNDABLE",
        "reservation_units":len(symbols),
        "payload_sha256":hashlib.sha256(raw_payload).hexdigest(),
        "quote_payload":payload,
    }
    data=canonical_json(envelope)
    if len(data)>MAX_OUTPUT_BYTES:
        return _blocked("BLOCKED_INVALID_SYNTHETIC_DATA","SIZE_LIMIT")
    try:
        # Exclusive creation blocks overwrite. The caller chooses only a
        # preexisting output directory, NEVER a GitHub path or checkpoint.
        with destination.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except (OSError,FileExistsError) as exc:
        # No provider retry. A filesystem write error may be ambiguous.
        return _blocked("UNCERTAIN_SINK_NOT_COMMITTED",type(exc).__name__)
    return {
        "schema":SCHEMA,
        "status":"SYNTHETIC_OUTPUT_NOT_LIVE",
        "filename":filename,
        "market_files_written":1,
        "saved":True,
        "reservation_units":len(symbols),
        "external_provider_called":False,
        "runtime_write_authorized":False,
        "independent_witness_enrolled":False,
        "human_owner_verified":False,
        "automatic_retry_allowed":False,
        "worker_executed":False,
        "source_authority":"SYNTHETIC_FIXTURE_ONLY",
    }
