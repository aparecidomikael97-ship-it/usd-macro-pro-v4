"""Explicit one-shot OCR October ARTICLE archive for AM12 local LAB.

RBNZ ordinary automated access is permitted by its 12-Nov-2026 terms
<=120/hour with RBNZ-Automated-Agent organisation/application identity.
This collector visits ONLY the OCTOBER release URL already obtained from
the RBNZ news XML feed and validated by GitHub Actions in #1967. It never
retries the formerly rejected OCR overview URL (HTTP403), follows redirects,
accesses paid market data, reaches MetaTrader or makes forecast/trade calls.

Default CLI or API without explicit flag does NOTHING. If the user manually
runs --capture before the NEXT event, fetch exactly once with 12s timeout,
test issuer original-byte SHA+HTML decision sentence+receipt clocks, then
write source and receipt into existing isolated LOCALAPPDATA/LAB archives
with the SAME recognized NZD_RBNZ_OCR stem (variant distinguished by URL).

Saving a document TODAY is not a 28 Oct point-in-time capture. A GitHub
Action's ephemeral SHA is not the same as an AM12 retained original.
No GO, market consensus, signed FX direction or profit claims.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import (
    Request, HTTPRedirectHandler, HTTPSHandler, build_opener,
)

from atlasquant_trader_nzd_rbnz_policy_source_variant_lab import (
    ADMITTED_STATE, VARIANT_OCTOBER,
    OCTOBER_ARTICLE_URL as URL,
    NEXT_SCHEDULED_RBNZ_DECISION_UTC as EXPIRES_UTC,
    inspect_nzd_rbnz_policy_variant_lab,
)
from atlasquant_trader_nzd_rbnz_xml_news_feed_lab import USER_AGENT

SCHEMA = "ATLASQUANT_NZD_OCT_RBNZ_ARTICLE_ONE_SHOT_LOCAL_CAPTURE_LAB_V1"
MAX_BYTES = 400_000
_STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp(text: Any) -> datetime | None:
    if type(text) is not str or _STAMP.fullmatch(text) is None:
        return None
    try:
        return datetime.strptime(
            text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def collect_october_rbnz_release_once_lab(
    *, explicit_capture: Any, request_open: Callable[..., Any] | None = None,
    stamp_clock: Callable[[], str] = _now,
) -> tuple[bytes, dict[str, Any]]:
    """One GET max. Returns ORIGINAL bytes only to explicit local caller."""
    if explicit_capture is not True:
        raise PermissionError("EXPLICIT_OCTOBER_CAPTURE_FLAG_REQUIRED")
    if not callable(stamp_clock):
        raise ValueError("CAPTURE_CLOCK_INVALID")
    if request_open is None:
        request_open = build_opener(_NoRedirect, HTTPSHandler).open
    if not callable(request_open):
        raise ValueError("CAPTURE_NETWORK_PROVIDER_INVALID")
    before = stamp_clock()
    begin = _stamp(before)
    if begin is None or begin >= EXPIRES_UTC:
        raise ValueError("OCTOBER_RELEASE_SUPERSEDED_OR_CLOCK_INVALID")
    request = Request(URL, headers={
        "User-Agent": USER_AGENT, "Accept": "text/html",
    }, method="GET")
    with request_open(request, timeout=12) as response:
        data = response.read(MAX_BYTES+1)
        if type(data) is not bytes or not 100 <= len(data) <= MAX_BYTES:
            raise ValueError("ORIGINAL_OCTOBER_ARTICLE_SIZE_INVALID")
        rec = {
            "source_url": URL,
            "final_url": response.geturl(),
            "http_status": response.status,
            "content_type": response.headers.get("Content-Type", ""),
            "body_sha256": sha256(data).hexdigest(),
            "started_at_utc": before,
            "finished_at_utc": stamp_clock(),
            "https_validation_claim": True,
            "redirects_followed": response.geturl() != URL,
        }
    end = _stamp(rec["finished_at_utc"])
    if end is None or end >= EXPIRES_UTC:
        raise ValueError("CAPTURE_ENDED_AFTER_DECEMBER_POLICY_EVENT")
    checked = inspect_nzd_rbnz_policy_variant_lab(
        original_html=data, receipt=rec, decision_at_utc=end)
    if (checked["state"] != ADMITTED_STATE
            or checked.get("source_variant") != VARIANT_OCTOBER):
        raise ValueError("OFFICIAL_RBNZ_RELEASE_BYTE_RECEIPT_REJECTED")
    return data, rec


def save_october_rbnz_release_local_lab(
    *, original_html: Any, receipt: Any, local_appdata: Any,
    as_of_utc: Any,
) -> tuple[str, str]:
    """Strict write-once local evidence; reject symlinks and overwrite."""
    if (type(local_appdata) is not str or not local_appdata
            or type(original_html) is not bytes
            or type(receipt) is not dict
            or type(as_of_utc) is not datetime
            or as_of_utc.tzinfo is None or as_of_utc.microsecond):
        raise ValueError("INVALID_LOCAL_ARCHIVE_SOURCE_OR_CLOCK")
    at = as_of_utc.astimezone(timezone.utc)
    if at >= EXPIRES_UTC:
        raise ValueError("OCR_OCTOBER_SOURCE_SUPERSEDED_NOT_SAVEABLE")
    report = inspect_nzd_rbnz_policy_variant_lab(
        original_html=original_html, receipt=receipt, decision_at_utc=at)
    if (report["state"] != ADMITTED_STATE
            or report["source_variant"] != VARIANT_OCTOBER):
        raise ValueError("RBNZ_ARTICLE_FAILED_SOURCE_VALIDATOR_NO_SAVE")

    root = Path(local_appdata)
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("ABSOLUTE_REAL_LOCALAPPDATA_REQUIRED")
    atlas = root/"AtlasQuant"
    lab = atlas/"LAB"
    folder = lab/"official_macro_receipts"
    if any(x.is_symlink() for x in (atlas,lab,folder)):
        raise ValueError("ISOLATED_LAB_DIRECTORY_SYMLINK_REFUSED")
    root_resolved = root.resolve(strict=False)
    if not folder.resolve(strict=False).is_relative_to(root_resolved):
        raise ValueError("LAB_ARCHIVE_OUTSIDE_LOCALAPPDATA_REFUSED")
    folder.mkdir(parents=True,exist_ok=True)

    # The reader already recognizes this generic NZD OCR archive stem.
    stamp = receipt["finished_at_utc"].replace("-","").replace(":","")
    basename = "NZD_RBNZ_OCR_"+stamp+"_"+receipt["body_sha256"][:12]
    original = folder/(basename+".html")
    meta = folder/(basename+".receipt.json")
    if original.exists() or meta.exists() or original.is_symlink() or meta.is_symlink():
        raise FileExistsError("OCTOBER_SOURCE_ALREADY_ARCHIVED_NO_OVERWRITE")
    source_created = False
    try:
        with original.open("xb") as file:
            source_created = True
            file.write(original_html)
        with meta.open("xb") as file:
            file.write((json.dumps(receipt,sort_keys=True,indent=2)+"\n")
                       .encode("utf-8"))
    except Exception:
        # Never leave a half-paired source in the archive if the receipt
        # could not be created. Does not modify any previous archive.
        if source_created and original.is_file() and not original.is_symlink():
            original.unlink()
        raise
    return original.name, meta.name


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="One-shot RBNZ October OCR archive")
    cli.add_argument("--capture", action="store_true")
    args = cli.parse_args(argv)
    if not args.capture:
        print("LAB_NO_HTTP_NO_FILES_EXPLICIT_FLAG_REQUIRED")
        return 2
    try:
        body, receipt = collect_october_rbnz_release_once_lab(
            explicit_capture=True)
        at = _stamp(receipt["finished_at_utc"])
        if at is None:
            raise ValueError("INVALID_LOCAL_CAPTURE_CLOCK")
        source, meta = save_october_rbnz_release_local_lab(
            original_html=body, receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA",""),
            as_of_utc=at)
        print(json.dumps({
            "state": "LAB_NZD_OCTOBER_RBNZ_ARTICLE_ARCHIVED_LOCALLY_NO_GO",
            "source_filename": source,
            "receipt_filename": meta,
            "body_sha256_local": receipt["body_sha256"],
            "historical_issuer_first_seen_verified": False,
            "forecast_or_calibrated_probability": None,
            "operational_bias": "AGUARDAR",
            "trade_authorized": False,
        }, sort_keys=True))
        return 0
    except (HTTPError, URLError, OSError, ValueError, TypeError,
            KeyError, OverflowError):
        print("LAB_RBNZ_OCTOBER_ARTICLE_CAPTURE_OR_ARCHIVE_FAILED_NO_GO")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "SCHEMA", "collect_october_rbnz_release_once_lab",
    "save_october_rbnz_release_local_lab", "main",
)
