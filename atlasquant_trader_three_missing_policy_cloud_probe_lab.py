"""One bounded first-party HTTPS check for JPY/CHF; NZD blocked by terms.

Offline on CI by default; explicit manual probe permits at most 2 GETs.
Reuse EXISTING issuer-specific collectors and original-byte validators.
RBNZ automated access requires prior written issuer permission; never
attempt the NZD URL while blocked, even if a fake synthetic collector exists.
No retries, mirror, challenges bypass, browser impersonation, fallbacks,
source HTML logging, file writing, upload, MT5, trades, API subscriptions,
model direction or archive recency claim on the user's disconnected AM12.

SNB HTML may include third-party licensed market data (SARON/BFIX):
never print/rehost the raw HTML. Every downloaded page is used ephemerally
only to check the official policy instrument; only an audit summary is shown.

A successful local SHA check of downloaded bytes is NOT independent
issuer first-seen, historical point-in-time, or signed FX effect.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
import json
from urllib.error import HTTPError, URLError
from atlasquant_trader_nzd_rbnz_access_terms_lab import RBNZ_BLOCK_REASON

from atlasquant_trader_jpy_boj_guideline_manual_capture_lab import (
    collect_boj_home_once_lab,
)
from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    inspect_boj_home_guideline_receipt_lab,
)
from atlasquant_trader_chf_snb_current_policy_manual_capture_lab import (
    collect_snb_current_policy_once_lab,
)
from atlasquant_trader_chf_snb_current_policy_receipt_lab import (
    inspect_snb_current_policy_receipt_lab,
)
from atlasquant_trader_nzd_rbnz_ocr_manual_capture_lab import (
    collect_rbnz_ocr_once_lab,
)
from atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    inspect_rbnz_official_ocr_receipt_lab,
)

SCHEMA = "ATLASQUANT_TRADER_THREE_MISSING_G8_ONE_SHOT_CLOUD_PROBE_LAB_V1"
ORDER = ("JPY", "CHF", "NZD")
VALIDATED = {
    "JPY": "LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO",
    "CHF": "LAB_CHF_SNB_CURRENT_POLICY_HTML_LOCALLY_CHECKED_NO_GO",
    "NZD": "LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO",
}
STEPS = {
    "JPY": (collect_boj_home_once_lab, inspect_boj_home_guideline_receipt_lab,
            "policy_guideline_target_pct_claim"),
    "CHF": (collect_snb_current_policy_once_lab,
            inspect_snb_current_policy_receipt_lab,
            "current_snb_policy_rate_pct_claim"),
    "NZD": (collect_rbnz_ocr_once_lab, inspect_rbnz_official_ocr_receipt_lab,
            "official_cash_rate_pct_claim"),
}
HASH_KEYS = {
    "JPY": "html_sha256_matches_local_receipt",
    "CHF": "original_html_sha256_locally_matching",
    "NZD": "original_html_sha256_matches_local_receipt",
}
TRANSPORT_KEYS = {
    "JPY": "transport_claim_structurally_consistent",
    "CHF": "http_transport_claim_locally_consistent",
    "NZD": "http_transport_claim_structurally_coherent",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_THREE_ISSUER_CLOUD_PROBE_NO_REQUEST",
        "reason": reason,
        "planned_official_https_get_max": 2,
        "rbnz_automated_access_permission_verified": False,
        "rbnz_automated_get_skipped_by_terms": True,
        "requests_started_claim": 0,
        "source_results": {},
        "valid_ephemeral_original_checks": 0,
        "missing_on_am12_resolved": False,
        "source_original_bytes_retained": False,
        "source_receipt_locally_archived_on_am12": False,
        "independent_issuer_origin_verified": False,
        "historical_first_seen_authenticated": False,
        "policy_decided_rate_is_not_market_expectation": True,
        "pre_event_consensus_verified": False,
        "signed_fx_impact_calibrated": False,
        "out_of_sample_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "new_cost_brl": 0,
        "files_written": 0,
        "research_only": True,
    }


def probe_three_missing_policy_sources_once_lab(
    *, explicit_probe: Any,
    clock: Callable[[], datetime] = _now,
    steps: Any = None,
) -> dict[str, Any]:
    """One call/issuer max, no retries; injectable collectors for offline tests.

    The real CLI does not provide injection. On denied HTTP access, report
    coarse error classification, do not weaken validators or retry.
    """
    out = _base("EXPLICIT_PROBE_FLAG_REQUIRED")
    if explicit_probe is not True:
        return out
    out["reason"] = "INVALID_CLOCK_OR_STEP_MAPPING"
    if not callable(clock):
        return out
    try:
        first = _utc(clock())
    except (OSError, TypeError, RuntimeError, ValueError, OverflowError):
        return out
    if first is None:
        return out
    steps = STEPS if steps is None else steps
    if (type(steps) is not dict or set(steps) != set(ORDER)
            or any(type(steps[c]) is not tuple or len(steps[c]) != 3
                   or not callable(steps[c][0])
                   or not callable(steps[c][1])
                   or type(steps[c][2]) is not str
                   for c in ORDER)):
        return out

    out["state"] = "LAB_THREE_ISSUER_CLOUD_PROBE_COMPLETED_NO_GO"
    out["reason"] = "EPHEMERAL_POLICY_CHECKS_NO_LOCAL_AM12_ARCHIVE_OR_TRADE"
    for currency in ORDER:
        if currency == "NZD":
            # RBNZ written authorization has not been verified. Never GET
            # this issuer through the cloud probe, even via injected steps.
            out["source_results"][currency] = {
                "status": "RBNZ_WRITTEN_PERMISSION_REQUIRED_NO_HTTP_NO_GO",
                "reason": RBNZ_BLOCK_REASON,
                "official_policy_pct_claim": None,
            }
            continue
        collector, validator, rate_field = steps[currency]
        phase = "HTTPS_GET"
        out["requests_started_claim"] += 1
        try:
            body, receipt = collector()
            phase = "VALIDATOR"
            cutoff = _utc(clock())
            if cutoff is None or cutoff < first or cutoff-first > timedelta(minutes=3):
                out["source_results"][currency] = {
                    "status": "INVALID_POST_GET_CLOCK_NO_GO",
                    "official_policy_pct_claim": None,
                }
                continue
            source_key = "original_html"
            check = validator(
                **{source_key: body},
                receipt=receipt,
                decision_at_utc=cutoff,
            )
            if (type(check) is not dict
                    or check.get("state") != VALIDATED[currency]
                    or check.get(HASH_KEYS[currency]) is not True
                    or check.get(TRANSPORT_KEYS[currency]) is not True
                    or check.get("operational_bias") != "AGUARDAR"
                    or check.get("trade_authorized") is not False
                    or check.get("publishable") is not False
                    or type(receipt) is not dict
                    or type(receipt.get("body_sha256")) is not str):
                code = (check.get("reason")
                        if type(check) is dict else "INVALID_VALIDATOR_RESPONSE")
                out["source_results"][currency] = {
                    "status": "SOURCE_VALIDATOR_REJECTED_NO_GO",
                    "validation_reason_code": (
                        code if type(code) is str and code.isascii()
                        and len(code) <= 100 and code.replace("_", "").isalnum()
                        else "UNSAFE_VALIDATOR_REASON"),
                    "official_policy_pct_claim": None,
                }
                continue
            out["valid_ephemeral_original_checks"] += 1
            out["source_results"][currency] = {
                "status": "VALIDATED_EPHEMERAL_BYTES_NOT_ARCHIVED_NO_GO",
                "body_sha256_ephemeral_claim": receipt["body_sha256"],
                "original_page_received_utc_local_claim":
                    receipt.get("finished_at_utc"),
                "official_policy_pct_claim": check.get(rate_field),
                "source_first_seen_independently_authenticated": False,
            }
        except HTTPError as exc:
            out["source_results"][currency] = {
                "status": "OFFICIAL_HTTPS_REQUEST_REJECTED_NO_GO",
                "http_status": (
                    exc.code if type(exc.code) is int
                    and 400 <= exc.code <= 599 else None),
                "official_policy_pct_claim": None,
            }
        except URLError:
            out["source_results"][currency] = {
                "status": "OFFICIAL_TLS_OR_NETWORK_UNAVAILABLE_NO_GO",
                "official_policy_pct_claim": None,
            }
        except (OSError, ValueError, KeyError, TypeError, RuntimeError,
                UnicodeError, OverflowError, RecursionError):
            out["source_results"][currency] = {
                "status": ("OFFICIAL_SOURCE_HTTP_OR_RESPONSE_FAILED_NO_GO"
                           if phase == "HTTPS_GET"
                           else "SOURCE_VALIDATOR_EXCEPTION_NO_GO"),
                "official_policy_pct_claim": None,
            }
    return out


def main(argv: list[str] | None = None) -> int:
    arg = argparse.ArgumentParser(
        description="Three one-shot first-party HTTPS policy source probes")
    arg.add_argument("--probe-official", action="store_true")
    args = arg.parse_args(argv)
    report = probe_three_missing_policy_sources_once_lab(
        explicit_probe=args.probe_official)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    # BLOCKED issuers are an honest, complete diagnostic, not a CI failure or GO.
    return 0 if report["state"] == (
        "LAB_THREE_ISSUER_CLOUD_PROBE_COMPLETED_NO_GO") else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("SCHEMA", "probe_three_missing_policy_sources_once_lab", "main")
