"""One explicit manual command for five still-unconfirmed G8 policy sources.

Only with --capture-missing and a valid LOCALAPPDATA may this make UP TO FIVE
independent bounded HTTPS GETs (GBP, JPY, CHF, AUD, NZD), preserving original
public HTML bytes and local receipts using EXISTING collectors/validators.
A source already locally checked by the 8-bank replay is skipped. A blocked
single bank never triggers browser imitation, retries or a fallback provider.

No import-side effects, background execution, MT5, orders, alerts, CPI, macro
direction, percentage calibration, main/deploy, subscriptions, or costs.
Local checks do not independently attest first-seen, issuer identity or PIT.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable

from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    inspect_fx28_official_policy_archive_replay_lab as replay,
)
from atlasquant_trader_gbp_boe_bank_rate_manual_capture_lab import (
    collect_boe_rate_once_lab, save_boe_source_in_lab,
)
from atlasquant_trader_gbp_boe_bank_rate_history_receipt_lab import (
    inspect_boe_bank_rate_history_receipt_lab,
)
from atlasquant_trader_jpy_boj_guideline_manual_capture_lab import (
    collect_boj_home_once_lab, save_boj_home_in_lab,
)
from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    inspect_boj_home_guideline_receipt_lab,
)
from atlasquant_trader_chf_snb_current_policy_manual_capture_lab import (
    collect_snb_current_policy_once_lab, save_snb_policy_public_bytes_lab,
)
from atlasquant_trader_chf_snb_current_policy_receipt_lab import (
    inspect_snb_current_policy_receipt_lab,
)
from atlasquant_trader_aud_rba_cash_target_manual_capture_lab import (
    collect_rba_cash_target_once_lab, save_rba_target_public_receipt_lab,
)
from atlasquant_trader_aud_rba_cash_target_receipt_lab import (
    inspect_rba_cash_target_current_receipt_lab,
)
from atlasquant_trader_nzd_rbnz_ocr_manual_capture_lab import (
    collect_rbnz_ocr_once_lab, save_rbnz_ocr_public_lab,
)
from atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    inspect_rbnz_official_ocr_receipt_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_FIVE_G8_POLICY_MANUAL_CAPTURE_ONCE_LAB_V1"
# Explicit known exact original state per existing validator; no weak "PASS".
# Layout: collector, validator, saver, keyword for original bytes, exact state.
_STEPS = {
    "GBP": (collect_boe_rate_once_lab, inspect_boe_bank_rate_history_receipt_lab,
            save_boe_source_in_lab, "original_html",
            "LAB_GBP_BOE_ORIGINAL_HISTORY_HTML_LOCALLY_CHECKED_NO_GO"),
    "JPY": (collect_boj_home_once_lab, inspect_boj_home_guideline_receipt_lab,
            save_boj_home_in_lab, "original_html",
            "LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO"),
    "CHF": (collect_snb_current_policy_once_lab, inspect_snb_current_policy_receipt_lab,
            save_snb_policy_public_bytes_lab, "original_html",
            "LAB_CHF_SNB_CURRENT_POLICY_HTML_LOCALLY_CHECKED_NO_GO"),
    "AUD": (collect_rba_cash_target_once_lab, inspect_rba_cash_target_current_receipt_lab,
            save_rba_target_public_receipt_lab, "original_html",
            "LAB_AUD_RBA_CASH_TARGET_HTML_LOCALLY_CHECKED_NO_GO"),
    "NZD": (collect_rbnz_ocr_once_lab, inspect_rbnz_official_ocr_receipt_lab,
            save_rbnz_ocr_public_lab, "original_html",
            "LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO"),
}
_ORDER = ("GBP", "JPY", "CHF", "AUD", "NZD")


def _clock() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FX28_FIVE_SOURCE_CAPTURE_NO_ACTION",
        "reason": reason,
        "eligible_currency_codes": list(_ORDER),
        "planned_https_get_limit": 5,
        "https_gets_attempted_or_started": 0,
        "currency_results": {},
        "replayed_source_codes_after_run": [],
        "replayed_currency_count_after_run": 0,
        "pairs_with_both_policy_originals_locally_checked_after_run": 0,
        "first_seen_independently_authenticated": False,
        "issuer_origin_independently_authenticated": False,
        "historical_pit_cpi_bilateral_verified": False,
        "fx_direction_admissible": False,
        "directional_bias": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


def collect_five_missing_policy_sources_once_lab(
    *, capture_missing: Any, local_appdata: Any,
    decision_clock: Callable[[], datetime] = _clock,
    steps: Any = None,
) -> dict[str, Any]:
    """No access at all unless caller explicitly sets capture_missing=True.

    Dependency injection is restricted to research tests; the real CLI has
    no injected HTTP provider and uses only the five hardcoded official URLs.
    """
    out = _base("EXPLICIT_CAPTURE_MISSING_FLAG_REQUIRED")
    if capture_missing is not True:
        return out
    out["reason"] = "UNSAFE_LOCAL_LAB_ROOT_OR_CLOCK"
    if (type(local_appdata) is not str or not local_appdata
            or not callable(decision_clock)):
        return out
    try:
        now = decision_clock()
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None or now.microsecond):
            return out
        now = now.astimezone(timezone.utc)
        base = Path(local_appdata)
        if not base.is_absolute() or base.is_symlink():
            return out
        atlas = base / "AtlasQuant"
        lab = atlas / "LAB"
        folder = lab / "official_macro_receipts"
        if any(x.is_symlink() for x in (atlas, lab, folder)):
            return out
        if not folder.resolve(strict=False).is_relative_to(lab.resolve(strict=False)):
            return out
        if any(x.exists() and not x.is_dir() for x in (base, atlas, lab, folder)):
            return out
    except (OSError, TypeError, ValueError, OverflowError, RuntimeError):
        return out

    # Reuse the existing 8-bank replay to select per-issuer most recent
    # current archive. Never believe mere presence of a filename.
    before = replay(local_appdata=local_appdata, decision_at_utc=now)
    if (before["state"] not in (
            "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO",
            "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO")
            and before["reason"] != "LOCAL_ISSUER_ARCHIVE_FOLDER_MISSING"):
        out["reason"] = "PRECHECK_ARCHIVE_REPLAY_BLOCKED"
        return out

    already = set(before["currencies_locally_checked"])
    if steps is None:
        steps = _STEPS
    if (type(steps) is not dict or set(steps) != set(_ORDER)):
        out["reason"] = "INVALID_ISSUER_COLLECTOR_MAPPING"
        return out

    out["state"] = "LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO"
    out["reason"] = "COLLECTION_MAY_FAIL_INDIVIDUALLY_NO_TRADING"
    for currency in _ORDER:
        if currency in already:
            out["currency_results"][currency] = "SKIPPED_ALREADY_LOCALLY_CHECKED"
            continue
        collector, validator, saver, source_key, expected = steps[currency]
        try:
            out["https_gets_attempted_or_started"] += 1
            body, receipt = collector()
            finish = datetime.strptime(
                receipt["finished_at_utc"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            # Do NOT let a caller's future or fabricated capture time
            # pass by moving the decision cutoff forward.
            if finish > now or finish.tzinfo is None:
                out["currency_results"][currency] = "CAPTURE_CLAIMED_FUTURE_OF_DECISION"
                continue
            checked = validator(
                **{source_key: body}, receipt=receipt, decision_at_utc=now)
            if (type(checked) is not dict or checked.get("state") != expected
                    or checked.get("trade_authorized") is not False
                    or checked.get("publishable") is not False):
                out["currency_results"][currency] = "ISSUER_BYTES_OR_RECEIPT_REJECTED"
                continue
            saver(body=body, receipt=receipt, local_appdata=local_appdata)
            out["currency_results"][currency] = "WRITTEN_RECHECK_PENDING"
        except (OSError, TypeError, ValueError, KeyError, OverflowError,
                RuntimeError, UnicodeError):
            out["currency_results"][currency] = "FETCH_VALIDATE_OR_SAVE_FAILED"

    after = replay(local_appdata=local_appdata, decision_at_utc=now)
    postchecked = set(after.get("currencies_locally_checked", []))
    out["replayed_source_codes_after_run"] = sorted(postchecked)
    out["replayed_currency_count_after_run"] = len(postchecked)
    out["pairs_with_both_policy_originals_locally_checked_after_run"] = (
        after.get("pairs_with_both_policy_originals_locally_checked", 0))
    for currency in _ORDER:
        if out["currency_results"][currency] == "WRITTEN_RECHECK_PENDING":
            out["currency_results"][currency] = (
                "SAVED_AND_LOCALLY_REPLAYED_ONLY_NO_GO"
                if currency in postchecked
                else "SAVED_BUT_REPLAY_DID_NOT_ACCEPT")
    out["state"] = (
        "LAB_FX28_FIVE_SOURCE_CAPTURE_LOCAL_REPLAY_ONLY_NO_GO"
        if all(out["currency_results"][c] in (
            "SKIPPED_ALREADY_LOCALLY_CHECKED",
            "SAVED_AND_LOCALLY_REPLAYED_ONLY_NO_GO") for c in _ORDER)
        else "LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")
    out["reason"] = (
        "LOCAL_RECEIPTS_NEVER_FIRST_SEEN_OR_BIAS_ATTESTATION"
        if out["state"] == "LAB_FX28_FIVE_SOURCE_CAPTURE_LOCAL_REPLAY_ONLY_NO_GO"
        else "ONE_OR_MORE_ISSUER_CAPTURES_UNAVAILABLE_OR_NOT_REPLAYED")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-shot five-bank original-source LAB research capture")
    parser.add_argument("--capture-missing", action="store_true")
    args = parser.parse_args()
    report = collect_five_missing_policy_sources_once_lab(
        capture_missing=args.capture_missing,
        local_appdata=os.environ.get("LOCALAPPDATA", ""),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["state"] == (
        "LAB_FX28_FIVE_SOURCE_CAPTURE_LOCAL_REPLAY_ONLY_NO_GO") else 2


if __name__ == "__main__":
    raise SystemExit(main())
