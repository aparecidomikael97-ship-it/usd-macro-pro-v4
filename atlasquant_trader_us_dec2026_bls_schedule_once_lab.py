"""One explicitly authorized official BLS December-2026 schedule capture.

Save an original HTML and an HTTP/UTC/SHA receipt only if the physical
calendar shows exactly three agreed release rows:
  CPI Nov 2026 + Real Earnings Nov 2026 together 10-Dec 08:30 ET,
  PPI Nov 2026 15-Dec 08:30 ET.
Never treat a calendar snapshot as consensus, publisher first-seen, data
availability for TD/TE, a directional Forex prediction or a trade signal.

No network or filesystem mutation when explicit capture flag is absent.
One fixed HTTPS GET, no retry, no redirect; never fetch BLS releases here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, HTTPRedirectHandler, build_opener
from zoneinfo import ZoneInfo
import argparse
import json
import re

SCHEMA = "ATLASQUANT_BLS_DEC26_SCHEDULE_ORIGINAL_CAPTURE_LAB_V1"
URL = "https://www.bls.gov/schedule/2026/12_sched_list.htm"
UTC = timezone.utc
MAX_BYTES = 650_000
FROZEN_CAPTURE_DEADLINE_UTC = datetime(2026, 12, 10, 12, 30, tzinfo=UTC)
TARGETS = (
    ("US_CPI_NOV2026", "Thursday, December 10, 2026",
     "Consumer Price Index for November 2026", 10),
    ("US_REAL_EARNINGS_NOV2026", "Thursday, December 10, 2026",
     "Real Earnings for November 2026", 10),
    ("US_PPI_NOV2026", "Tuesday, December 15, 2026",
     "Producer Price Index for November 2026", 15),
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.active = False
        self.text = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style", "noscript", "svg"):
            self.hidden += 1
        if self.hidden:
            return
        if tag == "tr":
            if self.active:
                raise ValueError("NESTED_TABLE_ROW_NOT_ALLOWED")
            self.active = True
            self.text = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style", "noscript", "svg") and self.hidden:
            self.hidden -= 1
            return
        if self.hidden:
            return
        if tag == "tr" and self.active:
            self.rows.append(" ".join(" ".join(self.text).split()))
            self.active = False
            self.text = []

    def handle_data(self, data):
        if self.active and not self.hidden:
            self.text.append(data)


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        return value.astimezone(UTC) if value.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLS_DEC26_SCHEDULE_BLOCKED_NO_GO",
        "reason": reason,
        "schedule_release_rows_reconciled": 0,
        "schedule_original_sha256": None,
        "original_html_locally_archived": False,
        "pre_event_consensus_authenticated": False,
        "publisher_first_seen_independently_attested": False,
        "source_time_server_authenticated": False,
        "registered_fx_forecasts": 0,
        "accuracy": None,
        "usd_bias": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "changes_to_fx28_672_slots": False,
        "mt5_calls": 0,
        "http_get_attempts": 0,
        "file_writes": 0,
    }


def inspect_dec2026_schedule_original_lab(*, raw_html: Any) -> dict[str, Any]:
    """Semantic check of one byte-identical BLS original, not HTTP identity."""
    out = _blocked("BLS_CALENDAR_HTML_ROW_IDENTITY_NOT_RECONCILED")
    if type(raw_html) is not bytes or not 100 <= len(raw_html) <= MAX_BYTES:
        return out
    try:
        parser = _Rows()
        # BLS HTML is ASCII-compatible; replacement cannot fabricate precise
        # release words, so invalid UTF-8 is rejected rather than repaired.
        parser.feed(raw_html.decode("utf-8", "strict"))
        parser.close()
        if parser.active or not parser.rows:
            return out
        matched = []
        for root, date_phrase, indicator, day in TARGETS:
            rows = [row for row in parser.rows
                    if date_phrase in row and indicator in row]
            if (len(rows) != 1
                    or re.search(r"\b08:30\s*AM\b", rows[0]) is None):
                return out
            eastern = datetime(2026, 12, day, 8, 30,
                               tzinfo=ZoneInfo("America/New_York"))
            expected = datetime(2026, 12, day, 13, 30, tzinfo=UTC)
            if eastern.astimezone(UTC) != expected:
                return out
            matched.append({
                "event_root": root,
                "scheduled_release_utc_calendar_claim": expected.isoformat(),
            })
        if len({row["event_root"] for row in matched}) != 3:
            return out
        out.update({
            "state": "LAB_BLS_DEC26_SCHEDULE_BODY_THREE_ROWS_RECONCILED_NO_GO",
            "reason": "OFFICIAL_SCHEDULE_BODY_SEMANTICS_ONLY_NOT_FIRST_SEEN",
            "schedule_release_rows_reconciled": 3,
            "scheduled_rows": matched,
            "co_release_CPI_real_earnings_same_instant": True,
            "schedule_original_sha256": sha256(raw_html).hexdigest(),
        })
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError):
        return _blocked("BLS_CALENDAR_HTML_PARSE_OR_ENCODING_INVALID")
    return out


def capture_dec2026_schedule_original_once_lab(
    *, allow_one_official_get: Any, output_root: Any,
    request_open: Callable[..., Any] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    out = _blocked("EXPLICIT_BLS_CALENDAR_CAPTURE_OPT_IN_REQUIRED")
    if allow_one_official_get is not True:
        return out
    if request_open is None:
        request_open = build_opener(_NoRedirect()).open
    if clock is None:
        clock = lambda: datetime.now(UTC)
    if not callable(request_open) or not callable(clock):
        return _blocked("INVALID_REQUEST_OR_CLOCK_PROVIDER")
    try:
        root = Path(output_root)
        if (not root.is_absolute() or root.is_symlink()
                or not root.is_dir()):
            return _blocked("EXISTING_ABSOLUTE_OUTPUT_DIRECTORY_REQUIRED")
        begin = _utc(clock())
        if begin is None or begin > FROZEN_CAPTURE_DEADLINE_UTC:
            return _blocked("CALENDAR_CAPTURE_AFTER_FIRST_PRE_EVENT_FREEZE")
        req = Request(URL, method="GET", headers={
            "Accept": "text/html",
            "Accept-Encoding": "identity",
            "User-Agent": "AtlasQuantTrader-LAB-Calendar-Research/1.0",
        })
        out["http_get_attempts"] = 1
        with request_open(req, timeout=15) as response:
            status = response.status
            final = response.geturl()
            mime = response.headers.get("Content-Type", "")
            encoding = response.headers.get("Content-Encoding", "identity")
            http_date = response.headers.get("Date", "")
            data = response.read(MAX_BYTES + 1)
        finish = _utc(clock())
        if (finish is None or finish < begin
                or finish > FROZEN_CAPTURE_DEADLINE_UTC
                or (finish - begin).total_seconds() > 180
                or type(status) is not int or status != 200
                or final != URL
                or type(mime) is not str
                or mime.split(";")[0].strip().lower() != "text/html"
                or encoding not in ("", "identity") or type(data) is not bytes
                or not 100 <= len(data) <= MAX_BYTES):
            out["reason"] = "RESPONSE_URL_HTTP_TYPE_SIZE_OR_CAPTURE_CLOCK_INVALID"
            return out
        try:
            server_time = _utc(parsedate_to_datetime(http_date))
        except (TypeError, ValueError, IndexError, OverflowError):
            server_time = None
        # HTTP Date remains a source CLAIM; this only rejects impossible
        # gross UTC disagreement and is not independent first-seen proof.
        if (server_time is None
                or not begin - timedelta(minutes=2) <= server_time
                       <= finish + timedelta(seconds=5)):
            out["reason"] = "BLS_HTTP_DATE_OUTSIDE_CAPTURE_CLOCK_WINDOW"
            return out
        parsed = inspect_dec2026_schedule_original_lab(raw_html=data)
        if parsed["schedule_release_rows_reconciled"] != 3:
            out["reason"] = "LIVE_BLS_SCHEDULE_ROWS_DO_NOT_MATCH_FROZEN_PLAN"
            return out
        digest = sha256(data).hexdigest()
        folder = root / (
            "US_BLS_DEC26_SCHEDULE_" + finish.strftime("%Y%m%dT%H%M%S%fZ")
            + "_" + digest[:12])
        folder.mkdir(mode=0o700, exist_ok=False)
        receipt = {
            "schema": SCHEMA,
            "url": URL, "http_status": status,
            "http_content_type": mime, "http_date_claim": http_date,
            "started_at_utc": begin.isoformat(),
            "finished_at_utc": finish.isoformat(),
            "original_html_bytes": len(data), "original_html_sha256": digest,
            "schedule_release_rows_reconciled": 3,
            "scheduled_rows": parsed["scheduled_rows"],
            "co_release_CPI_real_earnings_same_instant": True,
            "consensus_and_forex_prediction_verified": False,
            "first_seen_independently_attested": False,
        }
        with (folder / "original.html").open("xb") as f:
            f.write(data)
        with (folder / "receipt.json").open("xb") as f:
            f.write((json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode())
        # Read back exactly the written source bytes and local receipt before
        # describing a successful archived original.
        with (folder / "original.html").open("rb") as f:
            original = f.read()
        with (folder / "receipt.json").open("rb") as f:
            saved_receipt = json.load(f)
        if (sha256(original).hexdigest() != digest
                or saved_receipt != receipt):
            out["reason"] = "PHYSICAL_SOURCE_OR_RECEIPT_READBACK_FAILED"
            out["file_writes"] = 2
            return out
        parsed.update({
            "state": "LAB_BLS_DEC26_REAL_SCHEDULE_ORIGINAL_ARCHIVED_NO_GO",
            "reason": "REAL_BLS_CALENDAR_BODY_AND_LOCAL_HTTP_RECEIPT_NOT_PREDICTION",
            "original_html_locally_archived": True,
            "archive_basename": folder.name,
            "archive_original_bytes": len(data),
            "capture_finished_at_utc_local_claim": finish.isoformat(),
            "http_date_claim": http_date,
            "http_get_attempts": 1,
            "file_writes": 2,
        })
        return parsed
    except (OSError, ValueError, TypeError, UnicodeError, RuntimeError,
            OverflowError):
        return _blocked("BLS_CALENDAR_SOURCE_CAPTURE_OR_WRITE_FAILED_NO_RETRY")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="One original BLS calendar GET, no FX")
    p.add_argument("--capture-official", action="store_true")
    p.add_argument("--output-root", required=True)
    opts = p.parse_args(argv)
    report = capture_dec2026_schedule_original_once_lab(
        allow_one_official_get=opts.capture_official,
        output_root=opts.output_root,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["original_html_locally_archived"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
