"""One-off, opt-in, PRE-EVENT source-byte capture for the Dec-2026 CPI/PPI LAB.

Capture a single HTML page for one event/provider, from a bounded approved URL,
with no redirect, retry, fallback, credentials, browser or paid API. Preserve
original bytes and HTTP/UTC claims, then REPLAY them through the source custody
gate. The schedule has to be checked manually before capture; it is not itself
independently attested here. Never infer a numeric consensus from an HTML body.

No network without --capture-official AND --confirm-bls-schedule-reviewed.
Not an ongoing GitHub scheduler, broker workflow, FX forecast or signal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone, date
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import (
    EVENTS, SOURCE_NAMES, OriginalPreEventSourceClaim,
    _TD_URL, _TE_URL, _MAX_BYTES,
    _td_edition_in_capture_window,
    inspect_us_dec2026_pre_event_consensus_custody_lab,
)

SCHEMA = "ATLASQUANT_US_DEC2026_ONE_GET_SOURCE_ARCHIVAL_LAB_V1"
RECEIPT_SCHEMA = "ATLASQUANT_US_DEC2026_SOURCE_ORIGINAL_HTTP_RECEIPT_V1"
UTC = timezone.utc
_EVENT_TIME = {root: release for root, _, _, release in EVENTS}
_DOC_FIELDS = frozenset((
    "schema", "event_root", "provider", "source_url", "final_url",
    "started_at_utc", "finished_at_utc", "http_status", "content_type",
    "http_date_claim", "original_html_bytes", "original_html_sha256",
    "manual_bls_schedule_review_claim_only",
    "numerical_consensus_semantics_authenticated",
))
_ROOT = re.compile(r"US_DEC2026_(US_(?:CPI|PPI)_NOV2026)_(TD_ECONOMICS|TRADING_ECONOMICS)_(20\d{6}T\d{12}Z)_([0-9a-f]{12})\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _now() -> datetime:
    return datetime.now(UTC)


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        return value.astimezone(UTC) if value.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _parse_iso(value: Any) -> datetime | None:
    if type(value) is not str or len(value) > 45 or not value.endswith("+00:00"):
        return None
    try:
        return _utc(datetime.fromisoformat(value))
    except (TypeError, ValueError, OverflowError):
        return None


def _get_url_valid(*, provider: str, url: Any, release: datetime) -> bool:
    if type(url) is not str:
        return False
    if provider == "TRADING_ECONOMICS":
        return url == _TE_URL
    if provider != "TD_ECONOMICS" or _TD_URL.fullmatch(url) is None:
        return False
    # A TD archived upcoming.htm path contains an ISO calendar edition date.
    # Don't pass a stale edition from a previous month as the event preview.
    edition = re.search(r"/tables/(20\d{2}-\d{2}-\d{2})/upcoming\.htm\Z", url)
    if edition is None:
        return False
    try:
        issue = date.fromisoformat(edition.group(1))
    except ValueError:
        return False
    return (release - timedelta(days=7)).date() <= issue <= release.date()


def _blocked(reason: str, *, get_attempts: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_DEC2026_ONE_GET_BLOCKED_NO_GO",
        "reason": reason, "http_get_attempts": get_attempts,
        "original_replayed_from_disk": False,
        "source_original_sha256": None,
        "source_original_bytes": None,
        "archive_basename": None,
        "event_root": None, "provider": None,
        "local_receipt_finished_utc_claim": None,
        "numerical_consensus_semantics_authenticated": False,
        "original_source_first_seen_independently_authenticated": False,
        "bls_schedule_independently_reconfirmed": False,
        "fx_direction": None, "fx_accuracy": None,
        "official_actual": None, "economic_surprise": None,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "trade_authorized": False,
        "operational_bias": "AGUARDAR",
        "original_fx28_672_slots_modified": False,
    }


def _unique_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("DUPLICATE_RECEIPT_KEY")
        result[k] = v
    return result


def _source_claim(body: bytes, receipt: dict[str, Any]) -> OriginalPreEventSourceClaim:
    return OriginalPreEventSourceClaim(
        event_root=receipt["event_root"], provider=receipt["provider"],
        source_url=receipt["source_url"], final_url=receipt["final_url"],
        html_original_bytes=body,
        original_sha256_claim=receipt["original_html_sha256"],
        http_status=receipt["http_status"], http_content_type=receipt["content_type"],
        http_date_claim=receipt["http_date_claim"],
        started_at_utc=_parse_iso(receipt["started_at_utc"]),
        finished_at_utc=_parse_iso(receipt["finished_at_utc"]),
    )


def _reconcile(body: Any, receipt: Any, *, cutoff: Any) -> bool:
    if (type(receipt) is not dict or set(receipt) != _DOC_FIELDS
            or receipt.get("schema") != RECEIPT_SCHEMA
            or receipt.get("manual_bls_schedule_review_claim_only") is not True
            or receipt.get("numerical_consensus_semantics_authenticated") is not False
            or receipt.get("event_root") not in _EVENT_TIME
            or receipt.get("provider") not in SOURCE_NAMES
            or type(body) is not bytes
            or type(receipt.get("original_html_sha256")) is not str
            or _SHA.fullmatch(receipt["original_html_sha256"]) is None
            or type(receipt.get("original_html_bytes")) is not int
            or len(body) != receipt["original_html_bytes"]
            or sha256(body).hexdigest() != receipt["original_html_sha256"]
            or not _get_url_valid(provider=receipt["provider"],
                                  url=receipt.get("source_url"),
                                  release=_EVENT_TIME[receipt["event_root"]])):
        return False
    start, finish = (_parse_iso(receipt.get("started_at_utc")),
                     _parse_iso(receipt.get("finished_at_utc")))
    now = _utc(cutoff)
    if (now is None or start is None or finish is None or finish > now
            or not start <= finish
            or (finish-start).total_seconds() > 180):
        return False
    inspected = inspect_us_dec2026_pre_event_consensus_custody_lab(
        snapshots=(_source_claim(body, receipt),), research_cutoff_utc=now,
    )
    return (
        inspected["state"] == "LAB_DEC2026_PRE_EVENT_SOURCE_CUSTODY_ONLY_NO_GO"
        and inspected["locally_sha_reconciled_pre_event_source_documents"] == 1
        and inspected["event_roots_with_two_local_source_hashes"] == 0
        and inspected["economically_validated_pre_event_consensus_events"] == 0
        and inspected["validated_out_of_sample_trading_trials"] == 0
        and inspected["trade_authorized"] is False
        and inspected["publishable"] is False
    )


def replay_dec2026_one_get_original_lab(
    *, output_root: Any, archive_basename: Any, research_cutoff_utc: Any,
) -> dict[str, Any]:
    out = _blocked("MISSING_OR_INVALID_STORED_ORIGINAL")
    now = _utc(research_cutoff_utc)
    if (now is None or type(archive_basename) is not str
            or _ROOT.fullmatch(archive_basename) is None):
        return out
    try:
        root=Path(output_root)
        folder=root/archive_basename
        original, metadata=folder/"original.html", folder/"receipt.json"
        if (root.is_symlink() or not root.is_dir()
                or folder.is_symlink() or not folder.is_dir()
                or original.is_symlink() or metadata.is_symlink()
                or not original.is_file() or not metadata.is_file()
                or metadata.stat().st_size > 8192
                or not 100 <= original.stat().st_size <= max(_MAX_BYTES.values())):
            return out
        receipt=json.loads(metadata.read_text("utf-8"),
                           object_pairs_hook=_unique_json_pairs)
        if type(receipt) is not dict:
            return out
        end=_parse_iso(receipt.get("finished_at_utc"))
        if end is None or end > now:
            return _blocked("ORIGINAL_FUTURE_CAPTURE_NOT_VISIBLE")
        match=_ROOT.fullmatch(archive_basename)
        raw=original.read_bytes()
        if (match is None or match.group(1) != receipt.get("event_root")
                or match.group(2) != receipt.get("provider")
                or match.group(3) != end.strftime("%Y%m%dT%H%M%S%fZ")
                or match.group(4) != sha256(raw).hexdigest()[:12]
                or not _reconcile(raw,receipt,cutoff=now)):
            return out
        out.update({
            "state": "LAB_DEC2026_ONE_GET_ORIGINAL_LOCALLY_REPLAYED_NO_GO",
            "reason": "ORIGINAL_BYTES_AND_LOCAL_PRE_EVENT_CLAIM_VERIFIED_NOT_CONSENSUS",
            "original_replayed_from_disk": True,
            "source_original_sha256": sha256(raw).hexdigest(),
            "source_original_bytes": len(raw),
            "archive_basename": archive_basename,
            "event_root": receipt["event_root"], "provider": receipt["provider"],
            "local_receipt_finished_utc_claim": receipt["finished_at_utc"],
        })
    except (OSError, ValueError, TypeError, UnicodeError,
            RuntimeError, OverflowError):
        return _blocked("MISSING_OR_INVALID_STORED_ORIGINAL")
    return out


def capture_dec2026_one_get_original_lab(
    *, allow_one_official_get: Any, confirm_bls_schedule_reviewed: Any,
    event_root: Any, provider: Any, source_url: Any, output_root: Any,
    open_url: Callable[..., Any] | None = None,
    clock: Callable[[], datetime] = _now,
) -> dict[str, Any]:
    out=_blocked("EXPLICIT_CAPTURE_AND_SCHEDULE_REVIEW_OPT_IN_REQUIRED")
    if allow_one_official_get is not True or confirm_bls_schedule_reviewed is not True:
        return out
    if (type(event_root) is not str or event_root not in _EVENT_TIME
            or type(provider) is not str or provider not in SOURCE_NAMES
            or not _get_url_valid(provider=provider, url=source_url,
                                   release=_EVENT_TIME[event_root])):
        return _blocked("UNSUPPORTED_EVENT_OR_PROVIDER_URL")
    try:
        root=Path(output_root)
        if root.is_symlink() or not root.is_dir():
            return _blocked("EXISTING_REAL_DIRECTORY_REQUIRED")
    except (TypeError, ValueError, OSError):
        return _blocked("EXISTING_REAL_DIRECTORY_REQUIRED")
    start=_utc(clock())
    release=_EVENT_TIME[event_root]
    if (start is None or not release-timedelta(days=7) <= start
            or start > release-timedelta(hours=1)):
        return _blocked("PRE_EVENT_CAPTURE_WINDOW_NOT_OPEN_OR_ALREADY_FROZEN")
    # The weekly TD archive cannot claim to exist at a date BEFORE its
    # own YYYY-MM-DD edition, even if an attacker supplied an HTTP 200 body.
    # This preflight occurs BEFORE the single permitted GET.
    if provider == "TD_ECONOMICS" and not _td_edition_in_capture_window(
            source_url, release=release, captured_start=start):
        return _blocked("TD_WEEKLY_EDITION_POSTDATES_CAPTURE")

    req=Request(source_url,headers={
        "User-Agent":"AtlasQuantTrader-LAB-Research/1.0",
        "Accept":"text/html", "Accept-Encoding":"identity",
        "Connection":"close",
    },method="GET")
    out["http_get_attempts"]=1
    opener=open_url or build_opener(_NoRedirect()).open
    try:
        with opener(req,timeout=15) as response:
            status=response.status
            final=response.geturl()
            mime=response.headers.get("Content-Type","")
            http_date=response.headers.get("Date","")
            encoding=response.headers.get("Content-Encoding","identity")
            content_length=response.headers.get("Content-Length")
            data=response.read(_MAX_BYTES[provider]+1)
        finish=_utc(clock())
        if (type(data) is not bytes or type(status) is not int or status != 200
                or final != source_url or type(mime) is not str
                or mime.split(";")[0].strip().lower() != "text/html"
                or encoding not in ("","identity")
                or not 100 <= len(data) <= _MAX_BYTES[provider]
                or (content_length is not None and
                    (not str(content_length).isdigit()
                     or int(content_length) != len(data)))
                or finish is None or finish < start
                or finish > release-timedelta(hours=1)
                or (finish-start).total_seconds() > 180):
            out["reason"]="OFFICIAL_PAGE_HTTP_OR_CAPTURE_WINDOW_INVALID"
            return out
        digest=sha256(data).hexdigest()
        receipt={
            "schema": RECEIPT_SCHEMA, "event_root":event_root,
            "provider":provider,"source_url":source_url,"final_url":final,
            "started_at_utc":start.isoformat(),
            "finished_at_utc":finish.isoformat(),
            "http_status":status,"content_type":mime,
            "http_date_claim":http_date,
            "original_html_bytes":len(data),
            "original_html_sha256":digest,
            "manual_bls_schedule_review_claim_only":True,
            "numerical_consensus_semantics_authenticated":False,
        }
        if not _reconcile(data,receipt,cutoff=finish):
            out["reason"]="ORIGINAL_SOURCE_CUSTODY_GATE_REJECTED"
            return out
        basename=("US_DEC2026_"+event_root+"_"+provider+"_"
                  +finish.strftime("%Y%m%dT%H%M%S%fZ")+"_"+digest[:12])
        folder=root/basename
        folder.mkdir(mode=0o700,exist_ok=False)
        with (folder/"original.html").open("xb") as file:
            file.write(data)
        with (folder/"receipt.json").open("xb") as file:
            file.write((json.dumps(receipt,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8"))
        verified=replay_dec2026_one_get_original_lab(
            output_root=root, archive_basename=basename,
            research_cutoff_utc=finish)
        if not verified["original_replayed_from_disk"]:
            return _blocked("LOCAL_REPLAY_FAILED",get_attempts=1)
        verified["http_get_attempts"]=1
        return verified
    except (OSError, HTTPError, URLError, TimeoutError,
            TypeError, ValueError, UnicodeError, OverflowError, RuntimeError):
        return _blocked("SOURCE_GET_OR_LOCAL_WRITE_FAILED_NO_RETRY",get_attempts=1)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(
        description="One pre-event TD/TE HTML original capture; no numeric forecast")
    parser.add_argument("--capture-official",action="store_true")
    parser.add_argument("--confirm-bls-schedule-reviewed",action="store_true")
    parser.add_argument("--event-root",choices=sorted(_EVENT_TIME),required=True)
    parser.add_argument("--provider",choices=SOURCE_NAMES,required=True)
    parser.add_argument("--source-url",required=True)
    parser.add_argument("--output-root",required=True)
    a=parser.parse_args(argv)
    result=capture_dec2026_one_get_original_lab(
        allow_one_official_get=a.capture_official,
        confirm_bls_schedule_reviewed=a.confirm_bls_schedule_reviewed,
        event_root=a.event_root,provider=a.provider,
        source_url=a.source_url,output_root=a.output_root)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["original_replayed_from_disk"] else 2


if __name__=="__main__":
    raise SystemExit(main())
