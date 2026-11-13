"""Explicit one-shot current BoJ policy-guideline homepage collector (LAB).

Run only with --capture. A standard TLS request may download public BoJ
homepage bytes and write raw HTML + SHA/UTC local receipt into
%LOCALAPPDATA%/AtlasQuant/LAB/official_macro_receipts.

Never fetch official PDF automatically, touch MetaTrader5, accounts,
orders, positions, GitHub PRs, scheduled jobs or production. This is
the *current* homepage, NOT the original MPC release-time receipt.
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

from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    URL, MAX_BYTES, inspect_boj_home_guideline_receipt_lab,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_boj_home_once_lab(
    *, open_url: Callable[..., Any] = urlopen,
    now_utc: Callable[[], str] = _now,
) -> tuple[bytes, dict[str, Any]]:
    start = now_utc()
    req = Request(URL, headers={
        "User-Agent": "AtlasQuantTrader-LAB-Research/1.0",
        "Accept": "text/html",
    })
    with open_url(req, timeout=12) as resp:
        body = resp.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("BOJ_HOME_RESPONSE_TOO_LARGE")
        receipt = {
            "source_url": URL,
            "final_url": resp.geturl(),
            "http_status": resp.status,
            "content_type": resp.headers.get("Content-Type", ""),
            "body_sha256": sha256(body).hexdigest(),
            "started_at_utc": start,
            "finished_at_utc": now_utc(),
            "https_validation_claim": True,
            "redirects_followed": resp.geturl() != URL,
        }
    return body, receipt


def save_boj_home_in_lab(
    *, body: bytes, receipt: dict[str, Any], local_appdata: str,
) -> tuple[Path, Path]:
    if not local_appdata or not Path(local_appdata).is_absolute():
        raise ValueError("LOCALAPPDATA_IS_NOT_ABSOLUTE")
    root = (Path(local_appdata) / "AtlasQuant" / "LAB").resolve()
    out = (root / "official_macro_receipts").resolve()
    if out.is_symlink() or not out.is_relative_to(root):
        raise ValueError("OUTPUT_OUTSIDE_ISOLATED_LAB")
    out.mkdir(parents=True, exist_ok=True)
    stamp = receipt["finished_at_utc"].replace("-", "").replace(":", "")
    name = f"JPY_BOJ_CURRENT_GUIDELINE_{stamp}_{receipt['body_sha256'][:12]}"
    html_path = out / (name + ".html")
    rec_path = out / (name + ".receipt.json")
    if html_path.exists() or rec_path.exists():
        raise FileExistsError("EXISTING_CAPTURE_REFUSED_NO_OVERWRITE")
    with html_path.open("xb") as fp:
        fp.write(body)
    with rec_path.open("xb") as fp:
        fp.write(
            (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    return html_path, rec_path


def main() -> int:
    arg = argparse.ArgumentParser(
        description="BoJ current official guideline, manual LAB capture only")
    arg.add_argument("--capture", action="store_true")
    parsed = arg.parse_args()
    if not parsed.capture:
        print("LAB_NO_REQUEST_OR_FILES: requires explicit --capture")
        return 2
    try:
        body, receipt = collect_boj_home_once_lab()
        cutoff = datetime.strptime(
            receipt["finished_at_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        report = inspect_boj_home_guideline_receipt_lab(
            original_html=body, receipt=receipt, decision_at_utc=cutoff)
        if report["state"] != "LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO":
            print("LAB_BOJ_CAPTURE_BLOCKED: " + report["reason"])
            return 2
        original, meta = save_boj_home_in_lab(
            body=body, receipt=receipt,
            local_appdata=os.environ.get("LOCALAPPDATA", ""))
        print(json.dumps({
            "state": report["state"],
            "original_html_local_only": str(original),
            "receipt_local_only": str(meta),
            "source_sha256": receipt["body_sha256"],
            "policy_guideline_percent_claim": report["policy_guideline_target_pct_claim"],
            "market_observed_call_rate_verified": False,
            "oct30_statement_pdf_original_captured": False,
            "issuer_release_first_seen_verified": False,
            "operational_bias": "AGUARDAR",
            "trade_authorized": False,
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, TypeError, ValueError, KeyError, OverflowError):
        print("LAB_BOJ_SOURCE_CAPTURE_FAILED_NO_TRADE")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
