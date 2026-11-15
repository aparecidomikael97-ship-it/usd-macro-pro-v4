"""FX28 LAB deterministic atomic single-attempt claim (NOT the scheduled collector).

A one-window permanent marker is created through O_CREAT | O_EXCL; never
delete, replace, retry, or infer market data from it. Any crash/incomplete
claim remains a STOP until human documentary review. This component is
NOT deployed into the 15 Nov scheduled task and cannot protect a collector
that ignores its claim. No MT5, network, trading, prices, scheduling or
modification to frozen campaign slots.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from typing import Any,Callable
import json,os

SCHEMA="ATLASQUANT_FX28_FIRST_M15_ATOMIC_ATTEMPT_CLAIM_LAB_V1"
WINDOW="CAMPAIGN_FIRST_M15_20261115"
CLAIM_NAME=WINDOW+"_ATOMIC_ATTEMPT_CLAIM.json"
MAX_CLAIM_BYTES=2048
CLAIM_EARLIEST_UTC=datetime(2026,11,15,22,15,tzinfo=timezone.utc)
CLAIM_DEADLINE_UTC=datetime(2026,11,15,23,0,tzinfo=timezone.utc) # exclusive; local-clock claim, not attestation

def _out(reason: str) -> dict[str,Any]:
    return {
        "schema":SCHEMA,"window":WINDOW,
        "state":"LAB_FX28_M15_ATOMIC_CLAIM_BLOCKED_NO_GO",
        "reason":reason,
        "exclusive_claim_created":False,
        "archive_capture_allowed_by_this_module":False,
        "prior_archive_or_claim_found":None,
        "atomic_claim_is_not_scheduled_collector_integration":True,
        "old_collector_may_ignore_claim":True,
        "claim_does_not_authenticate_broker_or_market":True,
        "trading_authorized":False,"operational_bias":"AGUARDAR",
        "http_requests":0,"mt5_calls":0,"trade_calls":0,
    }

def inspect_claim_lab(*, archive_root:Any) -> dict[str,Any]:
    """Read-only preflight. A clean scan is NOT a concurrency lock."""
    from atlasquant_trader_fx28_first_m15_no_duplicate_precheck_lab import (
        check_no_prior_attempt_lab,
    )
    return check_no_prior_attempt_lab(archive_root=archive_root,window=WINDOW)

def claim_once_lab(*,archive_root:Any,clock:Callable[[],datetime]) -> dict[str,Any]:
    """Acquire exactly one persistent attempt marker; never run the collector.

    Correctness among callers USING THIS same claim is derived from the
    file system's exclusive-create semantics. A collector that bypasses
    this module remains unprotected; safety integration is still required.
    """
    out=_out("INVALID_ROOT_OR_WINDOW")
    if not isinstance(archive_root,Path) or not archive_root.is_absolute():
        return out
    try:
        if archive_root.is_symlink() or not archive_root.is_dir():
            return _out("MISSING_UNSAFE_OR_NON_DIRECTORY_ROOT_FAIL_CLOSED")
        now=clock()
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            return _out("INVALID_CLOCK_FAIL_CLOSED")
        now=now.astimezone(timezone.utc)
        # Do not make the first actual prospective claim before the
        # 22:00-22:15 UTC first M15 has closed.
        if now<CLAIM_EARLIEST_UTC:
            return _out("FROZEN_M15_NOT_CLOSED_NO_CLAIM")
        # A late historical read cannot masquerade as a prospective
        # Sunday-open observation. Allow a bounded 45-min reporting lag
        # after M15 close (the frozen 22:00-22:15 sample is unchanged).
        if now>=CLAIM_DEADLINE_UTC:
            return _out("PROSPECTIVE_CLAIM_AFTER_DEADLINE_NO_BACKFILL")
        first=inspect_claim_lab(archive_root=archive_root)
        if not first.get("single_attempt_start_precheck_clear"):
            blocked=_out("PRIOR_OR_UNKNOWN_ARCHIVE_OR_CLAIM_FAIL_CLOSED")
            blocked["prior_archive_or_claim_found"]=first.get("existing_candidate_count")
            return blocked
        claim=archive_root/CLAIM_NAME
        payload={
            "schema":SCHEMA,"window":WINDOW,
            "window_open_utc":"2026-11-15T22:00:00+00:00",
            "window_end_utc":"2026-11-15T22:15:00+00:00",
            "claimed_at_utc_local_clock_unattested":now.isoformat(),
            "one_attempt_only":True,
            "source_first_seen_attested":False,
            "broker_identity_authenticated":False,
            "trading_authorized":False,
            "never_retry_without_human_review":True,
        }
        raw=(json.dumps(payload,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
        if len(raw)>MAX_CLAIM_BYTES:
            return _out("CLAIM_PAYLOAD_TOO_LARGE_FAIL_CLOSED")
        # Exclusive OS-level file create is the narrow atomic primitive.
        # A partial marker is intentionally NEVER removed on any failure.
        try:
            fd=os.open(str(claim),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError:
            blocked=_out("ATOMIC_CLAIM_ALREADY_EXISTS_NO_SECOND_ATTEMPT")
            blocked["prior_archive_or_claim_found"]=1
            return blocked
        except OSError:
            return _out("ATOMIC_CLAIM_EXCLUSIVE_CREATE_FAILED")
        try:
            with os.fdopen(fd,"wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        except (OSError,ValueError):
            return _out("CLAIM_WRITE_INCOMPLETE_MARKER_PERSISTS_NO_RETRY")
        out.update({
            "state":"LAB_FX28_M15_ATOMIC_ATTEMPT_RESERVED_CLAIM_ONLY_NO_GO",
            "reason":"EXCLUSIVE_ATTEMPT_MARKER_CREATED_NOT_MARKET_CAPTURE",
            "exclusive_claim_created":True,
            "prior_archive_or_claim_found":0,
            "claim_filename":CLAIM_NAME,
            "claim_sha256":sha256(raw).hexdigest(),
            "claimed_at_utc_local_clock_unattested":now.isoformat(),
            "archive_capture_allowed_by_this_module":False,
            "file_writes":1,
        })
        return out
    except (OSError,ValueError,TypeError,RuntimeError):
        return _out("INSPECTION_OR_CLOCK_FAILED_FAIL_CLOSED")

__all__=("SCHEMA","WINDOW","CLAIM_NAME","CLAIM_EARLIEST_UTC","CLAIM_DEADLINE_UTC","claim_once_lab","inspect_claim_lab")
