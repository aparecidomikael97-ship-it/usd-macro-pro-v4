"""Manual, single-shot HTTPS CSV evidence capture for ECB/FRED policy levels.

Network is disabled by default. All observed headers are untrusted claims;
TLS with the default CA store and a ZIP hash do NOT independently establish
the publisher, decision announcement time, pre-event market expectations, or
historical availability. Never used by Radar, workers, orders or schedulers.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener
from zipfile import ZipFile, ZIP_STORED, BadZipFile

from atlasquant_trader_g8_single_https_probe_lab import _RejectRedirect
from atlasquant_trader_eurusd_policy_levels_lab import (
    ECB_SOURCE_URL, FED_SOURCE_URL, MAX_BYTES,
    parse_ecb_dfr_effective_csv_lab, parse_fed_target_range_csv_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EURUSD_POLICY_MANUAL_HTTP_RECEIPT_LAB_V1"
SOURCES = {
    "ECB_EUR_DFR_EFFECTIVE": (ECB_SOURCE_URL, parse_ecb_dfr_effective_csv_lab),
    "FED_USD_TARGET_RANGE_EFFECTIVE": (FED_SOURCE_URL, parse_fed_target_range_csv_lab),
}
CSV_TYPES = frozenset({
    "text/csv", "application/csv", "text/plain",
    "application/vnd.ecb.data+csv", "application/octet-stream",
})


def _blocked(reason: str, *, attempted: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_CAPTURE_BLOCKED", "reason": reason,
        "external_http_requests": int(attempted),
        "http_response_observed": False,
        "raw_snapshot_archive_path": None,
        "source_origin_independently_authenticated": False,
        "publication_instant_independently_verified": False,
        "historical_point_in_time_availability_verified": False,
        "consensus_before_decision_verified": False,
        "market_surprise_bps": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def capture_policy_csv_once_lab(
    source_id: Any, *, manually_authorized: bool = False,
    archive_dir: str | Path | None = None, timeout_seconds: int = 8,
) -> dict[str, Any]:
    """GET one fixed public endpoint only after foreground manual opt-in.

    Even a successfully parsed response is a mutable ex-post *level* and stays
    quarantined. A failed parser still archives bounded raw bytes for audit.
    """
    if manually_authorized is not True:
        return _blocked("MANUAL_OPT_IN_REQUIRED")
    if not isinstance(source_id, str) or source_id not in SOURCES:
        return _blocked("SOURCE_NOT_ALLOWLISTED")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 15:
        return _blocked("HTTP_TIMEOUT_OUT_OF_BOUNDS")
    if archive_dir is None:
        return _blocked("EXPLICIT_EXISTING_ARCHIVE_DIR_REQUIRED")
    try:
        directory = Path(archive_dir)
        if not directory.is_dir() or directory.is_symlink():
            return _blocked("ARCHIVE_DIR_MISSING_OR_SYMLINK")
    except (OSError, TypeError, ValueError):
        return _blocked("ARCHIVE_DIR_INVALID")

    url, parser = SOURCES[source_id]
    request = Request(url, method="GET", headers={
        "Accept": "text/csv,application/vnd.ecb.data+csv",
        "Accept-Encoding": "identity", "Cache-Control": "no-cache",
        "User-Agent": "AtlasQuant-Trader-LAB-manual-policy-level-capture/1.0",
    })
    try:
        opener = build_opener(
            HTTPSHandler(context=ssl.create_default_context()), _RejectRedirect())
        with opener.open(request, timeout=timeout_seconds) as response:
            if response.status != 200 or response.geturl() != url:
                return _blocked("HTTP_STATUS_OR_FINAL_URL_REJECTED", attempted=True)
            content_type = str(response.headers.get("Content-Type", ""))
            media = content_type.split(";", 1)[0].lower().strip()
            encoding = str(response.headers.get("Content-Encoding", "identity")).lower()
            if media not in CSV_TYPES or encoding != "identity":
                return _blocked("HTTP_CONTENT_TYPE_OR_ENCODING_REJECTED", attempted=True)
            raw = response.read(MAX_BYTES + 1)
            # Values in HTTP headers are publisher/proxy claims, never proofs.
            claimed_date = str(response.headers.get("Date", ""))[:120]
            claimed_modified = str(response.headers.get("Last-Modified", ""))[:120]
    except (HTTPError, URLError, OSError, ssl.SSLError, TimeoutError,
            ValueError, TypeError) as exc:
        return _blocked("HTTPS_FAILED_" + type(exc).__name__, attempted=True)

    if not 1 <= len(raw) <= MAX_BYTES or b"\x00" in raw:
        return _blocked("HTTP_CSV_BODY_LENGTH_OR_NUL_REJECTED", attempted=True)
    captured = datetime.now(timezone.utc)
    parsed = parser(raw, observed_at_utc=captured)
    accepted = parsed["state"] != "LAB_BLOCKED"
    receipt = {
        **_blocked("MUTABLE_SOURCE_NO_INDEPENDENT_EXANTE_PROOF", attempted=True),
        "state": ("LAB_CAPTURE_PARSER_ACCEPTED_QUARANTINED" if accepted else
                  "LAB_CAPTURE_RAW_FORMAT_REJECTED_QUARANTINED"),
        "source_id": source_id, "requested_url": url,
        "http_response_observed": True,
        "exact_url_and_status_checked": True,
        "http_status": 200, "http_content_type": media,
        "http_date_header_claim": claimed_date,
        "http_last_modified_header_claim": claimed_modified,
        "observed_at_local_system_utc": captured.isoformat(),
        "default_ca_validation_requested": True,
        "redirects_followed": False,
        "raw_response_bytes": len(raw),
        "raw_response_sha256": sha256(raw).hexdigest(),
        "parser_state": parsed["state"],
        "parser_reason": parsed.get("reason"),
        "parser_receipt": parsed,
    }
    name = (source_id.lower() + "_" + captured.strftime("%Y%m%dT%H%M%S%fZ")
            + "_" + sha256(raw).hexdigest()[:12] + ".zip")
    destination = directory / name
    created = False
    try:
        with ZipFile(destination, mode="x", compression=ZIP_STORED) as archive:
            created = True
            archive.writestr("response.csv", raw)
            archive.writestr("observation_receipt.json", json.dumps(
                receipt, ensure_ascii=False, sort_keys=True, indent=2))
        with ZipFile(destination, mode="r") as archive:
            if (set(archive.namelist()) != {"response.csv", "observation_receipt.json"}
                    or archive.read("response.csv") != raw
                    or json.loads(archive.read("observation_receipt.json")) != receipt):
                raise ValueError("Archive read-back mismatch")
        receipt["raw_snapshot_archive_path"] = str(destination)
        receipt["raw_snapshot_archive_sha256"] = sha256(destination.read_bytes()).hexdigest()
    except (OSError, ValueError, TypeError, RuntimeError, BadZipFile):
        if created:
            try:
                destination.unlink()
            except OSError:
                pass
        return _blocked("ARCHIVE_CREATE_OR_READBACK_FAILED", attempted=True)
    return receipt


__all__ = ["SCHEMA", "SOURCES", "capture_policy_csv_once_lab"]


def main(argv: list[str] | None = None) -> int:
    """Foreground CLI: one source/request per invocation, never implicit opt-in."""
    cli = argparse.ArgumentParser(description="LAB only: manual policy CSV evidence")
    cli.add_argument("--source", required=True, choices=sorted(SOURCES))
    cli.add_argument("--archive-dir", required=True)
    cli.add_argument("--timeout", type=int, default=8)
    cli.add_argument("--confirm-manual-http", action="store_true")
    args = cli.parse_args(argv)
    receipt = capture_policy_csv_once_lab(
        args.source, manually_authorized=args.confirm_manual_http,
        archive_dir=args.archive_dir, timeout_seconds=args.timeout)
    # Keep compact output; detailed parser evidence is in the local ZIP.
    print(json.dumps({key: value for key, value in receipt.items()
                      if key != "parser_receipt"}, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["state"] == "LAB_CAPTURE_PARSER_ACCEPTED_QUARANTINED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
