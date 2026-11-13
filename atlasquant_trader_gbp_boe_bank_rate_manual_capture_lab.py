"""Explicit one-shot official BoE Bank Rate HTML source capture (LAB).

Never runs without --capture. Stores raw public bytes and independent
local receipt under LOCALAPPDATA/AtlasQuant/LAB/official_macro_receipts;
does not touch MetaTrader, accounts, positions, GitHub issues or products.
A local current-page receipt never authenticates historical MPC release time.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from atlasquant_trader_gbp_boe_bank_rate_history_receipt_lab import (
    MAX_BYTES, URL, inspect_boe_bank_rate_history_receipt_lab,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_boe_rate_once_lab(
    *, open_url: Callable[..., Any] = urlopen,
    now_utc: Callable[[], str] = _now,
) -> tuple[bytes, dict[str, Any]]:
    start = now_utc()
    request = Request(URL, headers={
        "Accept": "text/html",
        "User-Agent": "AtlasQuantTrader-LAB-Research/1.0",
    })
    with open_url(request, timeout=12) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("BOE_HTML_RESPONSE_EXCEEDS_LIMIT")
        receipt = {
            "source_url": URL,
            "final_url": response.geturl(),
            "http_status": response.status,
            "content_type": response.headers.get("Content-Type", ""),
            "body_sha256": sha256(body).hexdigest(),
            "started_at_utc": start,
            "finished_at_utc": now_utc(),
            "https_validation_claim": True,
            "redirects_followed": response.geturl() != URL,
        }
    return body, receipt


def save_boe_source_in_lab(
    *, body: bytes, receipt: dict[str, Any], local_appdata: str,
) -> tuple[Path, Path]:
    if not local_appdata or not Path(local_appdata).is_absolute():
        raise ValueError("LAB_LOCALAPPDATA_MISSING")
    root = (Path(local_appdata) / "AtlasQuant" / "LAB").resolve()
    folder = (root / "official_macro_receipts").resolve()
    if folder.is_symlink() or not folder.is_relative_to(root):
        raise ValueError("LAB_SOURCE_FOLDER_UNSAFE")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = receipt["finished_at_utc"].replace("-", "").replace(":", "")
    stem = f"GBP_BOE_BANK_RATE_{stamp}_{receipt['body_sha256'][:12]}"
    orig = folder / (stem + ".html")
    meta = folder / (stem + ".receipt.json")
    if orig.exists() or meta.exists():
        raise FileExistsError("SOURCE_RECEIPT_ALREADY_EXISTS_NO_OVERWRITE")
    with orig.open("xb") as f:
        f.write(body)
    with meta.open("xb") as f:
        f.write((json.dumps(receipt, sort_keys=True, indent=2)
                 + "\n").encode("utf-8"))
    return orig, meta


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read official Bank Rate HTML once; LAB, no trading")
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    if not args.capture:
        print("LAB_NO_NETWORK_NO_FILES: explicit --capture required")
        return 2
    try:
        body, receipt = collect_boe_rate_once_lab()
        cutoff = datetime.strptime(
            receipt["finished_at_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        checked = inspect_boe_bank_rate_history_receipt_lab(
            original_html=body, receipt=receipt, decision_at_utc=cutoff)
        if checked["state"] != (
            "LAB_GBP_BOE_ORIGINAL_HISTORY_HTML_LOCALLY_CHECKED_NO_GO"):
            print("LAB_BOE_CAPTURE_REJECTED: " + checked["reason"])
            return 2
        raw, rec = save_boe_source_in_lab(
            body=body, receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA", ""))
        print(json.dumps({
            "state": checked["state"],
            "original_html_local_only": str(raw),
            "receipt_local_only": str(rec),
            "body_sha256": receipt["body_sha256"],
            "latest_bank_rate_pct_claim":
                checked["latest_bank_rate_pct_claim"],
            "effective_date_claim":
                checked["last_change_effective_date_claim"],
            "original_mpc_publication_time_attested": False,
            "macro_bilateral_complete": False,
            "operational_bias": "AGUARDAR",
            "trade_authorized": False,
        }, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        print("LAB_BOE_CAPTURE_FAILED_NO_TRADE")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
