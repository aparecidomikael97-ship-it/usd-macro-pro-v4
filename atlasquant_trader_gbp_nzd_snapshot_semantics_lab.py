"""Read-only semantic audit of three SHA-pinned GBP/NZD HTML captures.

The pinned SHA-256 values were recorded after the AM12 fetch in draft PR
#1851; this verifies local consistency against that checkpoint, not publisher
authenticity at original release time. Visible-text patterns are conservative
heuristics, not economic truth or forecast validation. NO network, MT5, orders.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any

from atlasquant_trader_gbp_nzd_official_capture_lab import MAX_BYTES, SCHEMA as CAPTURE_SCHEMA, TARGETS

SCHEMA = "ATLASQUANT_TRADER_GBP_NZD_PINNED_HTML_SEMANTICS_LAB_V1"
MAX_RECEIPT_BYTES = 16000

# SHA-256 after real public HTTP GET on AM12 2026-11-08 UTC, sealed as literal
# digests in the same draft PR. The actual HTML/JSON remain only on AM12.
PINS = {
    "GBP_CPI_2026_09": {
        "filename": "GBP_CPI_2026_09_20261108T030010Z_e072c7cb9810.html",
        "body_sha256": "e072c7cb9810acb7fae428e9e25c44d4f682554a0a9a723c585110d877e9b731",
        "receipt_sha256": "a6c3a0fe8c3712113492f57f0fc5b6e05a580b3375b869c7536f31ba6704b9fe",
        "capture_finished_at_utc": "2026-11-08T03:00:10Z",
    },
    "NZD_CPI_2026_Q3": {
        "filename": "NZD_CPI_2026_Q3_20261108T030016Z_60d8a4e18bab.html",
        "body_sha256": "60d8a4e18bab2aa456ad4db023f328c9bb91a094f58b6057928450fd22ddb35f",
        "receipt_sha256": "c52909a02c17c7154a73c47b0d92281896dd74c4cde7344d2c2d1ea369cb3a6f",
        "capture_finished_at_utc": "2026-11-08T03:00:16Z",
    },
    "GBP_BANK_RATE_2026_11": {
        "filename": "GBP_BANK_RATE_2026_11_20261108T030017Z_288a9039e016.html",
        "body_sha256": "288a9039e016a279fd2ca264dd43628ff124226606060f71d309322b03833433",
        "receipt_sha256": "71c91d79c9aaf7f26d3387bdb22710dde5f8aca994a1131a5bc96a04f26b2090",
        "capture_finished_at_utc": "2026-11-08T03:00:17Z",
    },
}

# Short contextual patterns from the official pages. Revisions may legitimately
# change the wording; a failure means human/source review, never forced success.
RULES = {
    "GBP_CPI_2026_09": {
        "title": (r"Consumer price inflation, UK",),
        "period": (r"Consumer price inflation, UK:\s*September 2026",),
        "metric": (r"Consumer Prices Index\s*\(CPI\)\s+rose by 3\.5\s*%\s+in the 12 months to September 2026",),
        "release": (r"21 October 2026",),
    },
    "NZD_CPI_2026_Q3": {
        "title": (r"Consumers price index:\s*September 2026 quarter",),
        "period": (r"Consumers price index:\s*September 2026 quarter",),
        "metric": (
            r"3\.7\s+percent increase in the CPI in the 12 months to the September 2026 quarter",
            r"CPI all groups.{0,160}\b3\.7\b",
        ),
        "release": (r"22 October 2026",),
    },
    "GBP_BANK_RATE_2026_11": {
        "title": (r"Bank rate increased to 4\s*%.*November 2026",),
        "period": (r"meeting ending on 4 November 2026",),
        "metric": (r"increase Bank Rate by 0\.25 percentage points,\s*to 4\s*%",),
        "release": (r"Published on 05 November 2026",),
    },
}


class _VisibleText(HTMLParser):
    """Discard scripts/styles so hidden JSON cannot satisfy evidence checks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.visible_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any):
        if self._hidden_depth:
            self._hidden_depth += 1
        elif tag in ("script", "style", "noscript", "svg", "template"):
            self._hidden_depth = 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str):
        if self._hidden_depth:
            self._hidden_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str):
        if self._hidden_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.visible_parts.append(data)


def _clean(parts: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _reject(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "checks": {}, "sha256_matches_checkpoint_pins": False,
        "issuer_authenticity_at_original_release_verified": False,
        "independent_timestamp_authority_verified": False,
        "point_in_time_backtest_approved": False, "operational_bias": "AGUARDAR",
        "directional_probability": None, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def _unique_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate receipt JSON key")
        out[key] = value
    return out


def inspect_pinned_html_semantics_lab(
    document_id: str, *, raw_html: bytes, raw_receipt_json: bytes,
) -> dict[str, Any]:
    """Check source bytes+manifest pins, then visible period/value wording.

    No numeric measurement is exported and even all-green semantic matches
    remain a research-only observation requiring independent attestation.
    """
    out = _reject("UNKNOWN_DOCUMENT_OR_INVALID_BYTES")
    if (not isinstance(document_id, str) or document_id not in PINS
            or not isinstance(raw_html, bytes) or not 128 <= len(raw_html) <= MAX_BYTES
            or not isinstance(raw_receipt_json, bytes)
            or not 128 <= len(raw_receipt_json) <= MAX_RECEIPT_BYTES):
        return out
    pin = PINS[document_id]
    if (sha256(raw_html).hexdigest() != pin["body_sha256"]
            or sha256(raw_receipt_json).hexdigest() != pin["receipt_sha256"]):
        out["reason"] = "CAPTURE_BYTES_OR_RECEIPT_DIFFER_FROM_GITHUB_CHECKPOINT"
        return out
    try:
        receipt = json.loads(raw_receipt_json.decode("utf-8", "strict"),
                             object_pairs_hook=_unique_json_pairs)
        if (not isinstance(receipt, dict) or receipt.get("schema") != CAPTURE_SCHEMA
                or receipt.get("document_id") != document_id
                or receipt.get("source_url") != TARGETS[document_id]
                or receipt.get("snapshot_filename") != pin["filename"]
                or receipt.get("snapshot_sha256") != pin["body_sha256"]
                or receipt.get("snapshot_bytes") != len(raw_html)
                or receipt.get("local_capture_finished_at_utc") != pin["capture_finished_at_utc"]
                or type(receipt.get("http_status")) is not int or receipt["http_status"] != 200
                or receipt.get("http_content_type") != "text/html"):
            out["reason"] = "CAPTURE_RECEIPT_METADATA_INCONSISTENT"
            return out
        parser = _VisibleText()
        parser.feed(raw_html.decode("utf-8", "strict"))
        parser.close()
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
        out["reason"] = "INVALID_UTF8_JSON_OR_HTML"
        return out
    title, visible = _clean(parser.title_parts), _clean(parser.visible_parts)
    checks = {}
    for name, patterns in RULES[document_id].items():
        haystack = title if name == "title" else visible
        checks[name] = any(re.search(pat, haystack, flags=re.IGNORECASE) is not None
                           for pat in patterns)
    complete = all(checks.values())
    out.update({
        "state": ("LAB_VISIBLE_CONTEXT_MATCH_UNATTESTED" if complete
                  else "LAB_SEMANTIC_REVIEW_REQUIRED"),
        "reason": ("PATTERN_MATCH_IS_NOT_HISTORICAL_AUTHENTICITY" if complete
                   else "MISSING_EXPECTED_VISIBLE_PERIOD_VALUE_OR_RELEASE_WORDING"),
        "document_id": document_id, "checks": checks,
        "sha256_matches_checkpoint_pins": True,
    })
    return out


def audit_am12_directory_lab(folder: Path) -> dict[str, Any]:
    """Read three exact captured filenames only; no directory rewrites."""
    folder = Path(folder)
    results = {}
    for key, pin in PINS.items():
        html_file = folder / pin["filename"]
        manifest_file = folder / (pin["filename"] + ".receipt.json")
        if (not folder.is_dir() or html_file.is_symlink() or manifest_file.is_symlink()
                or not html_file.is_file() or not manifest_file.is_file()):
            results[key] = _reject("PINNED_CAPTURE_FILE_MISSING")
            continue
        try:
            results[key] = inspect_pinned_html_semantics_lab(
                key, raw_html=html_file.read_bytes(),
                raw_receipt_json=manifest_file.read_bytes())
        except OSError:
            results[key] = _reject("CAPTURE_FILE_READ_ERROR")
    return {"schema": SCHEMA, "results": results,
            "consistent_sha_pins": sum(x["sha256_matches_checkpoint_pins"] for x in results.values()),
            "visible_context_matches": sum(x["state"] == "LAB_VISIBLE_CONTEXT_MATCH_UNATTESTED"
                                           for x in results.values()),
            "official_documents_expected": len(PINS),
            "historical_backtest_authorized": False,
            "operational_bias": "AGUARDAR"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline SHA-pinned official HTML semantic audit LAB")
    ap.add_argument("--capture-dir", type=Path, required=True)
    ns = ap.parse_args()
    result = audit_am12_directory_lab(ns.capture_dir)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["visible_context_matches"] == len(PINS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
