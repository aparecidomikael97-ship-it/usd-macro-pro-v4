"""Opt-in one-shot ECB XML capture, LAB / HARD NO-GO.

Executed only from CLI --manual-one-shot or an explicitly opted-in call.
Never runs on import. No schedules, worker, trading, market inference or costs.
A local receipt and TLS client do NOT independently attest publisher origin,
historic publication time, vintage, licensing, or tradeable M15 prices.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import ssl
import sys
from typing import Any
from urllib import request, error
from xml.etree import ElementTree as ET

SCHEMA = "ATLASQUANT_TRADER_ECB_MANUAL_HTTP_SNAPSHOT_LAB_V1"
SOURCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
ECB_NS = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"
GESMES_NS = "{http://www.gesmes.org/xml/2002-08-01}"
MAX_BYTES = 400_000
MIN_BYTES = 250
ACCEPTED_CONTENT_TYPES = frozenset(("text/xml", "application/xml"))


class _RejectRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "source_url": SOURCE_URL, "final_url": None, "http_status": None,
        "content_type": None, "content_encoding": None,
        "requested_at_local_utc": None, "completed_at_local_utc": None,
        "body_sha256": None, "body_bytes": None, "snapshot_filename": None,
        "receipt_filename": None, "http_request_count": 0,
        "automated_schedule": False, "explicit_manual_invocation": False,
        "default_tls_certificate_validation_requested": False,
        "source_origin_independently_attested": False,
        "historical_publication_instant_attested": False,
        "archive_vintage_point_in_time_verified": False,
        "source_licensing_for_commercial_use_verified": False,
        "broker_m15_execution_prices_verified": False,
        "historical_accuracy_verified": False, "trade_authorized": False,
        "can_feed_live_radar": False, "worker_enabled": False,
        "scheduler_enabled": False, "publishable": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "new_cost_brl": 0,
    }


def _looks_like_ecb_xml(raw: bytes) -> bool:
    """Cheap structural guard, NOT authenticity; full reader validates dates."""
    if not MIN_BYTES <= len(raw) <= MAX_BYTES:
        return False
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper() or b"\x00" in raw:
        return False
    try:
        root = ET.fromstring(raw)
        if root.tag != GESMES_NS + "Envelope":
            return False
        subject = root.find(GESMES_NS + "subject")
        sender = root.find(GESMES_NS + "Sender/" + GESMES_NS + "name")
        days = root.findall(".//" + ECB_NS + "Cube")
        return bool(
            subject is not None and (subject.text or "").strip() == "Reference rates"
            and sender is not None and (sender.text or "").strip() == "European Central Bank"
            and any(node.get("time") for node in days)
        )
    except (ET.ParseError, ValueError, TypeError):
        return False


def capture_ecb_xml_manual_lab(
    *, output_dir: Any, manual_one_shot: bool = False, opener: Any = None,
) -> dict[str, Any]:
    """Opt-in fetch and locally snapshot the exact response body, never overwrite.

    The injected opener exists for offline tests only. It can forge metadata;
    all independence and historical verification flags remain False.
    """
    out = _result("EXPLICIT_MANUAL_ONE_SHOT_OPT_IN_REQUIRED")
    if manual_one_shot is not True:
        return out
    out["explicit_manual_invocation"] = True
    if not isinstance(output_dir, (str, Path)) or not str(output_dir).strip():
        out["reason"] = "INVALID_DESTINATION_DIRECTORY"
        return out
    root = Path(output_dir)
    if root.is_symlink() or not root.is_dir():
        out["reason"] = "DESTINATION_MUST_BE_EXISTING_REAL_DIRECTORY"
        return out
    # No cookies, bearer credentials, HTTP upgrade, redirect or retry.
    # For real use stdlib HTTPS with the OS certificate store, never verify=False.
    real_transport = opener is None
    if real_transport:
        opener = request.build_opener(
            _RejectRedirects(),
            request.HTTPSHandler(context=ssl.create_default_context()),
        )
    start = datetime.now(timezone.utc)
    out["requested_at_local_utc"] = start.isoformat()
    out["default_tls_certificate_validation_requested"] = real_transport
    out["http_request_count"] = 1
    try:
        req = request.Request(SOURCE_URL, headers={
            "Accept": "application/xml, text/xml",
            "Accept-Encoding": "identity",
            "User-Agent": "AtlasQuantTrader-LAB-ManualSnapshot/1.0",
        }, method="GET")
        with opener.open(req, timeout=15) as response:
            status = response.status
            final = response.geturl()
            headers = response.headers
            ct = str(headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            encoding = str(headers.get("Content-Encoding", "identity")).lower().strip()
            length = headers.get("Content-Length")
            out.update(http_status=status, final_url=final,
                       content_type=ct, content_encoding=encoding)
            if (type(status) is not int or status != 200 or final != SOURCE_URL
                    or ct not in ACCEPTED_CONTENT_TYPES
                    or encoding != "identity"
                    or length is not None and (
                        re.fullmatch(r"[0-9]+", str(length)) is None
                        or int(length) > MAX_BYTES)):
                out["reason"] = "HTTP_STATUS_OR_ORIGIN_OR_BODY_HEADERS_REJECTED"
                return out
            body = response.read(MAX_BYTES + 1)
        out["completed_at_local_utc"] = datetime.now(timezone.utc).isoformat()
        if not isinstance(body, bytes) or not _looks_like_ecb_xml(body):
            out["reason"] = "INVALID_ECB_XML_BODY_OR_EXCESS_SIZE"
            return out
        body_hash = sha256(body).hexdigest()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        base = f"ecb_hist90d_{stamp}_{body_hash[:12]}"
        data_name = base + ".xml"
        receipt_name = base + ".receipt.json"
        receipt = dict(out)
        receipt.update({
            "state": "LAB_MANUAL_HTTP_SNAPSHOT_LOCAL_UNATTESTED",
            "reason": "LOCAL_SNAPSHOT_NOT_INDEPENDENT_HISTORICAL_SOURCE_PROOF",
            "body_sha256": body_hash,
            "body_bytes": len(body),
            "snapshot_filename": data_name,
            "receipt_filename": receipt_name,
        })
        data_path, receipt_path = root / data_name, root / receipt_name
        # Exclusive creation: never replace or rewrite an existing snapshot.
        with data_path.open("xb") as f:
            f.write(body)
            f.flush()
        try:
            with receipt_path.open("xb") as f:
                f.write((json.dumps(receipt, indent=2, sort_keys=True)
                         + "\n").encode("utf-8"))
                f.flush()
        except (OSError, ValueError):
            data_path.unlink(missing_ok=True)
            raise
        return receipt
    except (error.HTTPError, error.URLError, OSError, TimeoutError,
            ValueError, TypeError, AttributeError):
        out["reason"] = "MANUAL_HTTP_OR_FILESYSTEM_FAILURE"
        return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LAB: fetch ECB XML exactly once, only with explicit opt-in")
    parser.add_argument("--output-dir", required=True, help="existing folder")
    parser.add_argument("--manual-one-shot", action="store_true",
                        help="explicitly authorize ONE HTTPS GET now; no scheduler")
    args = parser.parse_args(argv)
    result = capture_ecb_xml_manual_lab(
        output_dir=args.output_dir, manual_one_shot=args.manual_one_shot)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "LAB_MANUAL_HTTP_SNAPSHOT_LOCAL_UNATTESTED" else 2


if __name__ == "__main__":
    sys.exit(main())
