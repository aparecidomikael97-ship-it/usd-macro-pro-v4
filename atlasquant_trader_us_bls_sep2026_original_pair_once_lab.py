"""One-time REAL BLS Sep-2026 CPI/PPI source collection, documentary LAB only.

Official issuer URLs and exact release identities are pinned below. GETs are
at most one per source, no redirect, retry, fallback, token, or API substitute.
All captured originals are *POST-EVENT*, irrespective of 2026 October embargo.
Archives carry an untrusted local time claim and original-byte SHA256, NOT
independent publisher first-seen/first-print vintage attestation.

Pure strict HTML parser also works fully offline on supplied bytes. The CLI
requires --capture-official to access either network URL. No Forex forecast,
consensus, FX price, probabilities, alerts, deploy, or order access.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import argparse
import json
import re
from typing import Any, Callable

UTC = timezone.utc
SCHEMA = "ATLASQUANT_BLS_CPI_PPI_SEPTEMBER2026_ORIGINAL_PAIR_LAB_V1"
MANIFEST_SCHEMA = "ATLASQUANT_BLS_SEP2026_TWO_ORIGINALS_RECEIPT_V1"
MAX_BYTES = 4*1024*1024
MIN_BYTES = 100_000
SPECS = {
    "CPI": {
        "url": "https://www.bls.gov/news.release/archives/cpi_10142026.htm",
        "release_utc": "2026-10-14T12:30:00+00:00",
        "edition": "USDL-26-1574",
        "title": "CONSUMER PRICE INDEX - SEPTEMBER 2026",
        "table": "Table 1. Consumer Price Index for All Urban Consumers",
        "headline_pattern": r"\bThe Consumer Price Index for All Urban Consumers \(CPI-U\) increased (0\.[0-9]+) percent on a seasonally adjusted basis in September\b",
        "headline_reference": "0.6",
    },
    "PPI": {
        "url": "https://www.bls.gov/news.release/archives/ppi_10152026.htm",
        "release_utc": "2026-10-15T12:30:00+00:00",
        "edition": "USDL 26-1576",
        "title": "PRODUCER PRICE INDEXES - SEPTEMBER 2026",
        "table": "Table 1. Producer price index percentage changes",
        "headline_pattern": r"\bThe Producer Price Index for final demand increased (1\.[0-9]+) percent in September, seasonally adjusted\b",
        "headline_reference": "1.3",
    },
}
_ARCHIVE = re.compile(r"US_BLS_SEP2026_CPI_PPI_(20[0-9]{6}T[0-9]{6}Z)_([0-9a-f]{12})\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_STAMP = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_MANIFEST_FIELDS = frozenset({"schema", "sources", "pair_digest", "last_capture_utc"})
_SOURCE_FIELDS = frozenset({
    "url", "http_status", "content_type", "http_date_claim",
    "started_utc", "finished_utc", "raw_sha256", "raw_bytes",
    "reference_period", "metric", "sa_mom_pct_body_claim",
    "publisher_first_seen_independently_attested",
})


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.ignored:
            self.ignored -= 1

    def handle_data(self, data):
        if self.ignored == 0:
            self.parts.append(data)


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _utc(t: Any) -> datetime | None:
    if type(t) is not datetime or t.tzinfo is None or t.microsecond:
        return None
    try:
        return t.astimezone(UTC) if t.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _stamp(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(t: Any) -> datetime | None:
    if type(t) is not str or _STAMP.fullmatch(t) is None:
        return None
    try:
        return _utc(datetime.fromisoformat(t.replace("Z", "+00:00")))
    except (ValueError, TypeError, OverflowError):
        return None


def _failure(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_SEP2026_BLS_TWO_ORIGINALS_BLOCKED_NO_GO",
        "reason": reason,
        "required_event_roots": ["US_CPI_SEP2026", "US_PPI_SEP2026"],
        "documentary_original_count": 0,
        "paired_original_source_sha256": {},
        "paired_headline_sa_mom_pct": {},
        "archive_basename": None,
        "http_get_attempts": 0,
        "consensus_pre_event_authenticated": False,
        "first_print_original_independently_authenticated": False,
        "market_reaction_causally_identified": False,
        "independent_fx_forecast_trials": 0,
        "out_of_sample_accuracy": None,
        "forex_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "original_fx28_672_slots_modified": False,
    }


def inspect_sep2026_bls_release_body_lab(*, kind: Any, raw_html: Any) -> dict[str, str] | None:
    if kind not in SPECS or type(kind) is not str or type(raw_html) is not bytes:
        return None
    if not MIN_BYTES <= len(raw_html) <= MAX_BYTES:
        return None
    # Read the full original body; never accept a headline declared by caller.
    try:
        p = _VisibleText()
        p.feed(raw_html.decode("utf-8"))
        p.close()
        text = re.sub(r"\s+", " ", " ".join(p.parts))
    except (UnicodeError, ValueError, OverflowError):
        return None
    spec = SPECS[kind]
    if (spec["edition"] not in text or spec["title"] not in text
            or spec["table"] not in text
            or "Bureau of Labor Statistics" not in text):
        return None
    hits = re.findall(spec["headline_pattern"], text)
    if hits != [spec["headline_reference"]]:
        return None
    return {
        "kind": kind, "reference_period": "2026-09",
        "metric": "HEADLINE_MOM_SA_PCT",
        "sa_mom_pct_body_claim": hits[0],
        "original_sha256": sha256(raw_html).hexdigest(),
        "original_bytes": str(len(raw_html)),
    }


def _pair_digest(raw: dict[str, bytes]) -> str:
    payload = b"ATLASQUANT_BLS_2026_09_CPI_PPI_PAIR_V1\0"
    for k in ("CPI", "PPI"):
        body = raw[k]
        payload += k.encode() + len(body).to_bytes(8, "big") + sha256(body).digest()
    return sha256(payload).hexdigest()


def _unique_pairs(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("DUPLICATE_JSON_KEY")
        d[k] = v
    return d


def replay_sep2026_bls_original_pair_lab(
    *, output_root: Any, archive_basename: Any, as_of_utc: Any,
) -> dict[str, Any]:
    out = _failure("ORIGINAL_PAIR_MANIFEST_OR_BYTES_INVALID")
    now = _utc(as_of_utc)
    if (now is None or type(archive_basename) is not str
            or _ARCHIVE.fullmatch(archive_basename) is None):
        return out
    try:
        root = Path(output_root)
        folder = root / archive_basename
        paths = {k: folder / (k.lower() + "_original.html") for k in SPECS}
        receipt = folder / "receipt.json"
        if (root.is_symlink() or not root.is_dir() or folder.is_symlink()
                or not folder.is_dir() or receipt.is_symlink()
                or not receipt.is_file() or receipt.stat().st_size > 8192
                or any(p.is_symlink() or not p.is_file()
                       or not MIN_BYTES <= p.stat().st_size <= MAX_BYTES
                       for p in paths.values())):
            return out
        info = json.loads(receipt.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_pairs)
        if (type(info) is not dict or set(info) != _MANIFEST_FIELDS
                or info["schema"] != MANIFEST_SCHEMA
                or type(info["sources"]) is not dict
                or set(info["sources"]) != set(SPECS)
                or type(info["pair_digest"]) is not str
                or _HEX.fullmatch(info["pair_digest"]) is None):
            return out
        raw = {k: p.read_bytes() for k, p in paths.items()}
        if info["pair_digest"] != _pair_digest(raw):
            return out
        match = _ARCHIVE.fullmatch(archive_basename)
        latest = _parse_utc(info["last_capture_utc"])
        if (latest is None or latest > now or match is None
                or match.group(1) != latest.strftime("%Y%m%dT%H%M%SZ")
                or match.group(2) != info["pair_digest"][:12]):
            return out
        extracted = {}
        for k in ("CPI", "PPI"):
            v = info["sources"][k]
            if type(v) is not dict or set(v) != _SOURCE_FIELDS:
                return out
            start, end = _parse_utc(v["started_utc"]), _parse_utc(v["finished_utc"])
            spec = SPECS[k]
            parsed = inspect_sep2026_bls_release_body_lab(kind=k, raw_html=raw[k])
            if (start is None or end is None
                    or not datetime.fromisoformat(spec["release_utc"]) <= start <= end <= latest
                    or (end-start).total_seconds() > 180
                    or v["url"] != spec["url"]
                    or type(v["http_status"]) is not int or v["http_status"] != 200
                    or type(v["content_type"]) is not str
                    or v["content_type"].split(";")[0].strip().lower() != "text/html"
                    or type(v["http_date_claim"]) is not str
                    or v["publisher_first_seen_independently_attested"] is not False
                    or v["reference_period"] != "2026-09"
                    or v["metric"] != "HEADLINE_MOM_SA_PCT"
                    or parsed is None
                    or v["raw_sha256"] != parsed["original_sha256"]
                    or v["raw_bytes"] != len(raw[k])
                    or v["sa_mom_pct_body_claim"] != parsed["sa_mom_pct_body_claim"]):
                return out
            extracted[k] = parsed
        out.update({
            "state": "LAB_SEP2026_BLS_TWO_ORIGINALS_REPLAYED_POST_EVENT_NO_GO",
            "reason": "TWO_ORIGINAL_RELEASE_BODIES_RECONCILED_NOT_PIT_FIRST_PRINT",
            "documentary_original_count": 2,
            "paired_original_source_sha256":
                {k: extracted[k]["original_sha256"] for k in extracted},
            "paired_headline_sa_mom_pct":
                {k: extracted[k]["sa_mom_pct_body_claim"] for k in extracted},
            "archive_basename": archive_basename,
            "last_capture_utc_claim": info["last_capture_utc"],
        })
    except (OSError, TypeError, ValueError, KeyError, UnicodeError, OverflowError):
        return _failure("ORIGINAL_PAIR_MANIFEST_OR_BYTES_INVALID")
    return out


def capture_sep2026_bls_original_pair_once_lab(
    *, allow_two_official_gets: Any, output_root: Any,
    opener: Callable[..., Any] | None = None,
    clock: Callable[[], datetime] = _now,
) -> dict[str, Any]:
    out = _failure("EXPLICIT_OPT_IN_REQUIRED")
    if allow_two_official_gets is not True:
        return out
    try:
        root = Path(output_root)
        if root.is_symlink() or not root.is_dir():
            out["reason"] = "EXISTING_SAFE_OUTPUT_ROOT_REQUIRED"
            return out
    except (OSError, TypeError, ValueError):
        out["reason"] = "EXISTING_SAFE_OUTPUT_ROOT_REQUIRED"
        return out
    open_once = opener or build_opener(_NoRedirect()).open
    raw = {}
    receipts = {}
    try:
        for k in ("CPI", "PPI"):
            spec = SPECS[k]
            start = _utc(clock())
            if start is None or start < datetime.fromisoformat(spec["release_utc"]):
                out["reason"] = "PRE_RELEASE_OR_INVALID_CAPTURE_CLOCK"
                return out
            request = Request(spec["url"], headers={
                "User-Agent": "AtlasQuantTrader-LAB-Research/1.0",
                "Accept": "text/html", "Accept-Encoding": "identity",
                "Connection": "close",
            }, method="GET")
            out["http_get_attempts"] += 1
            with open_once(request, timeout=15) as response:
                status = response.status
                url = response.geturl()
                mime = response.headers.get("Content-Type", "")
                enc = response.headers.get("Content-Encoding", "identity")
                length = response.headers.get("Content-Length")
                http_date = response.headers.get("Date", "")
                body = response.read(MAX_BYTES + 1)
            end = _utc(clock())
            parsed = inspect_sep2026_bls_release_body_lab(kind=k, raw_html=body)
            if (type(status) is not int or status != 200 or url != spec["url"]
                    or type(mime) is not str
                    or mime.split(";")[0].strip().lower() != "text/html"
                    or enc not in ("identity", "")
                    or end is None or end < start
                    or (end-start).total_seconds() > 180
                    or type(body) is not bytes or parsed is None
                    or (length is not None and
                        (not str(length).isdigit() or int(length) != len(body)))):
                out["reason"] = k+"_HTTP_OR_OFFICIAL_RELEASE_SEMANTICS_REJECTED"
                return out
            raw[k] = body
            receipts[k] = {
                "url": url, "http_status": status, "content_type": mime,
                "http_date_claim": http_date, "started_utc": _stamp(start),
                "finished_utc": _stamp(end),
                "raw_sha256": parsed["original_sha256"],
                "raw_bytes": len(body),
                "reference_period": "2026-09",
                "metric": "HEADLINE_MOM_SA_PCT",
                "sa_mom_pct_body_claim": parsed["sa_mom_pct_body_claim"],
                "publisher_first_seen_independently_attested": False,
            }
        digest = _pair_digest(raw)
        basename = ("US_BLS_SEP2026_CPI_PPI_" +
                    end.strftime("%Y%m%dT%H%M%SZ") + "_" + digest[:12])
        folder = root / basename
        folder.mkdir(mode=0o700, exist_ok=False)
        for k in ("CPI", "PPI"):
            with (folder / (k.lower()+"_original.html")).open("xb") as file:
                file.write(raw[k])
        metadata = {
            "schema": MANIFEST_SCHEMA, "sources": receipts,
            "pair_digest": digest, "last_capture_utc": _stamp(end),
        }
        with (folder / "receipt.json").open("xb") as file:
            file.write((json.dumps(metadata, sort_keys=True, separators=(",", ":"))+"\n").encode())
        checked = replay_sep2026_bls_original_pair_lab(
            output_root=root, archive_basename=basename, as_of_utc=end)
        if checked["documentary_original_count"] != 2:
            out["reason"] = "POST_WRITE_ORIGINAL_SOURCE_REPLAY_FAILED"
            return out
        checked["http_get_attempts"] = 2
        return checked
    except (OSError, URLError, HTTPError, TimeoutError,
            TypeError, ValueError, OverflowError, UnicodeError):
        out["reason"] = "BLS_READ_OR_ARCHIVE_ERROR_NO_RETRY"
        return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exactly two historical September 2026 BLS originals in LAB")
    parser.add_argument("--capture-official", action="store_true")
    parser.add_argument("--output-root", required=True)
    a = parser.parse_args(argv)
    r = capture_sep2026_bls_original_pair_once_lab(
        allow_two_official_gets=a.capture_official, output_root=a.output_root)
    print(json.dumps(r, sort_keys=True, indent=2))
    return 0 if r["documentary_original_count"] == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
