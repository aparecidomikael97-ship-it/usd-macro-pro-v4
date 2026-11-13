"""One-shot manual BoC V39079 original-byte capture to isolated local LAB.

NEVER imported by a scheduled worker. Run explicitly with --capture.
Fetch one exact issuer API URL using Python's usual certificate checks.
No retries, redirected content accepted, cookies, authentication, broker,
trades, account, email, paid subscriptions, or user-profile uploads.

Public JSON and a JSON receipt are stored in Windows LOCALAPPDATA under
AtlasQuant/LAB/official_macro_receipts, NEVER in the repo or main app.
This is locally observed evidence, NOT a notarized publisher vintage.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from typing import Any, Callable

from atlasquant_trader_cad_boc_valet_policy_receipt_lab import (
    MAX_BYTES, URL, inspect_boc_valet_policy_receipt_lab,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_boc_valet_once_lab(
    *, open_url: Callable[..., Any] = urlopen,
    now_utc: Callable[[], str] = _utc_now,
) -> tuple[bytes, dict[str, Any]]:
    """Return the exact HTTP response bytes and local receipt; no file IO."""
    start = now_utc()
    request = Request(URL, headers={
        "User-Agent": "AtlasQuantTraderLAB/1.0",
        "Accept": "application/json",
    })
    # HTTPS certificate and hostname validation are handled by the
    # standard Python urllib platform trust store; no bypass.
    with open_url(request, timeout=12) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("BOC_BODY_TOO_LARGE")
        result = {
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
    return body, result


def save_boc_receipt_in_isolated_lab(
    *, body: bytes, receipt: dict[str, Any],
    local_appdata: str,
) -> tuple[Path, Path]:
    """Only permitted local root is LOCALAPPDATA/AtlasQuant/LAB."""
    if not local_appdata or not Path(local_appdata).is_absolute():
        raise ValueError("LAB_LOCALAPPDATA_NOT_ABSOLUTE")
    root = (Path(local_appdata) / "AtlasQuant" / "LAB").resolve()
    folder = (root / "official_macro_receipts").resolve()
    if not folder.is_relative_to(root):
        raise ValueError("OUTSIDE_LAB")
    # Refuse a symlinked folder to ensure writes stay in the LAB tree.
    if folder.is_symlink():
        raise ValueError("SYMLINKED_SOURCE_FOLDER")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = receipt["finished_at_utc"].replace("-", "").replace(":", "")
    stem = f"CAD_BOC_V39079_{stamp}_{receipt['body_sha256'][:12]}"
    orig_path = folder / (stem + ".json")
    meta_path = folder / (stem + ".receipt.json")
    if orig_path.exists() or meta_path.exists():
        raise FileExistsError("CAPTURE_ALREADY_EXISTS_NO_OVERWRITE")
    # Never silently rewrite history. The two public records are coupled
    # by SHA-256 in the receipt and can be replayed offline.
    with orig_path.open("xb") as fd:
        fd.write(body)
    try:
        with meta_path.open("xb") as fd:
            fd.write((json.dumps(receipt,sort_keys=True,indent=2)
                      + "\n").encode("utf-8"))
    except Exception:
        # Incomplete local pair does not qualify as a valid capture.
        # Do not delete original evidence on a metadata write failure.
        raise
    return orig_path, meta_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Manual BoC V39079 raw capture in isolated LAB")
    ap.add_argument("--capture", action="store_true",
                    help="Required to make one HTTPS request and write local public evidence")
    args = ap.parse_args()
    if not args.capture:
        print("LAB_NO_NETWORK_NO_FILES: supply --capture only for a deliberate one-shot")
        return 2
    try:
        body, receipt = collect_boc_valet_once_lab()
        end_clock = datetime.strptime(receipt["finished_at_utc"],
                                      "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        check = inspect_boc_valet_policy_receipt_lab(
            original_body=body,receipt=receipt,decision_at_utc=end_clock)
        if check["state"] != "LAB_CAD_BOC_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO":
            print("LAB_CAPTURE_REJECTED: " + check["reason"])
            return 2
        source, meta = save_boc_receipt_in_isolated_lab(
            body=body, receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA", ""))
        print(json.dumps({
            "state":check["state"], "source_path_local_only":str(source),
            "receipt_path_local_only":str(meta),
            "source_sha256":receipt["body_sha256"],
            "observation_date":check["latest_observation_date_claim"],
            "target_rate_percent_observed":check["latest_target_rate_pct_claim"],
            "source_first_release_authenticated":False,
            "original_broker_or_macro_pit_attested":False,
            "operational_bias":"AGUARDAR", "trade_authorized":False,
        },indent=2,ensure_ascii=False))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print("LAB_CAPTURE_FAILED_NO_TRADE: "+type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
