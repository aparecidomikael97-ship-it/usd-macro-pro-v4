"""One-shot manual original Federal Reserve Board target-range HTML capture.

Run explicitly with --capture. Stores only public issuer HTML + local HTTP/
SHA-256 clock receipt under LOCALAPPDATA/AtlasQuant/LAB. The validation
remains NO-GO: HTML received now is not the original FOMC release time.
No broker, account, trading, jobs, external service or paid subscription.
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

from atlasquant_trader_us_fed_board_target_range_receipt_lab import (
    MAX_BYTES, URL, inspect_fed_board_policy_target_range_receipt_lab,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_fed_board_range_once_lab(
    *, open_url: Callable[..., Any] = urlopen,
    now_utc: Callable[[], str] = _now,
) -> tuple[bytes, dict[str, Any]]:
    start = now_utc()
    request = Request(URL, headers={
        "Accept": "text/html",
        "User-Agent": "AtlasQuantTrader-LAB-Research/1.0",
    })
    with open_url(request, timeout=12) as response:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("FED_HTML_BODY_TOO_LARGE")
        receipt = {
            "source_url": URL,
            "final_url": response.geturl(),
            "http_status": response.status,
            "content_type": response.headers.get("Content-Type", ""),
            "body_sha256": sha256(raw).hexdigest(),
            "started_at_utc": start,
            "finished_at_utc": now_utc(),
            "https_validation_claim": True,
            "redirects_followed": response.geturl() != URL,
        }
    return raw, receipt


def save_fed_board_range_lab(
    *, body: bytes, receipt: dict[str, Any], local_appdata: str,
) -> tuple[Path, Path]:
    if not local_appdata or not Path(local_appdata).is_absolute():
        raise ValueError("LOCALAPPDATA_NOT_ABSOLUTE")
    root = (Path(local_appdata) / "AtlasQuant" / "LAB").resolve()
    folder = (root / "official_macro_receipts").resolve()
    if not folder.is_relative_to(root) or folder.is_symlink():
        raise ValueError("NOT_ISOLATED_LAB")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = receipt["finished_at_utc"].replace("-", "").replace(":", "")
    stem = f"USD_FED_BOARD_TARGET_RANGE_{stamp}_{receipt['body_sha256'][:12]}"
    original_path = folder / (stem + ".html")
    receipt_path = folder / (stem + ".receipt.json")
    if original_path.exists() or receipt_path.exists():
        raise FileExistsError("PREEXISTING_RECORD_NO_OVERWRITE")
    with original_path.open("xb") as f:
        f.write(body)
    with receipt_path.open("xb") as f:
        f.write(
            (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    return original_path, receipt_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    if not args.capture:
        print("LAB_NO_NETWORK_OR_FILES: use --capture for one deliberate source query")
        return 2
    try:
        body, receipt = collect_fed_board_range_once_lab()
        decision = datetime.strptime(
            receipt["finished_at_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        check = inspect_fed_board_policy_target_range_receipt_lab(
            original_html=body, receipt=receipt, decision_at_utc=decision)
        if check["state"] != "LAB_USD_FED_BOARD_ORIGINAL_HTML_LOCALLY_CHECKED_NO_GO":
            print("FED_LAB_BLOCKED: " + check["reason"])
            return 2
        original, meta = save_fed_board_range_lab(
            body=body, receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA", ""))
        print(json.dumps({
            "state": check["state"],
            "local_original_html": str(original),
            "local_http_receipt": str(meta),
            "source_sha256": receipt["body_sha256"],
            "range_lower_percent": check["target_lower_pct_claim"],
            "range_upper_percent": check["target_upper_pct_claim"],
            "last_board_table_effective_date":
                check["most_recent_effective_date_claim"],
            "fomc_announcement_time_independently_authenticated": False,
            "historic_source_vintage_independently_authenticated": False,
            "calibrated_probability": None,
            "operational_bias": "AGUARDAR",
            "trade_authorized": False,
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        print("LAB_FED_HTML_CAPTURE_FAILED_NO_TRADE")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
