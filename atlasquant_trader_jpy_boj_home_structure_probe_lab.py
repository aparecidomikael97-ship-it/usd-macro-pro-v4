"""BoJ homepage HTML structural triage, exactly ONE explicit issuer GET.

The previous cloud probe fetched a BoJ HTML page but the STRICT policy
validator rejected its structure. This read-only triage reports only
counts/booleans for public-source policy text and HTML anchors, never raw
HTML or body excerpts, no fallback, retries, browser bypass, archive,
broker, signals or trading. A diagnostic match is NOT an accepted policy
original or a retrospectively authenticated publication timestamp.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError

from atlasquant_trader_jpy_boj_guideline_manual_capture_lab import (
    collect_boj_home_once_lab,
)
from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    _Text, TARGET_RE, DEPOSIT_RE, LOAN_RE,
    inspect_boj_home_guideline_receipt_lab,
)

SCHEMA = "ATLASQUANT_JPY_BOJ_ONE_SHOT_HTML_STRUCTURE_DIAGNOSTIC_LAB_V1"
MARKET = "The Bank's Market Operations"
GUIDELINE = "Guideline"
FOOTER = "Bank of Japan Operations"


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BOJ_STRUCTURE_DIAGNOSTIC_NO_REQUEST",
        "reason": reason,
        "official_https_get_attempts": 0,
        "document_bytes_available_ephemerally": False,
        "html_utf8_parsed": False,
        "visible_text_length": 0,
        "market_heading_occurrences": 0,
        "guideline_occurrences": 0,
        "footer_occurrences": 0,
        "whole_page_exact_policy_guideline_occurrences": 0,
        "whole_page_exact_deposit_occurrences": 0,
        "whole_page_exact_loan_occurrences": 0,
        "last_market_section_guideline_found": False,
        "last_market_section_footer_found": False,
        "last_market_section_policy_occurrences": 0,
        "last_market_section_deposit_occurrences": 0,
        "last_market_section_loan_occurrences": 0,
        "earlier_market_sections_with_three_distinct_measures": 0,
        "strict_validator_state": "NOT_ATTEMPTED",
        "strict_validator_reason_code": None,
        "validated_policy_original_retained": False,
        "issuer_first_seen_authenticated": False,
        "economic_policy_expected_rate_or_macro_bias": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_boj_home_structure_lab(
    *, original_html: Any, receipt: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    """Pure string-count triage: flags cannot make a source admissible."""
    out = _base("INVALID_OR_UNPARSABLE_ORIGINAL_HTML")
    if type(original_html) is not bytes or len(original_html) < 300:
        return out
    try:
        parser = _Text()
        parser.feed(original_html.decode("utf-8-sig", "strict"))
        parser.close()
        text = " ".join(" ".join(parser.parts).split())
    except (UnicodeError, TypeError, ValueError, OverflowError):
        return out

    out["document_bytes_available_ephemerally"] = True
    out["html_utf8_parsed"] = True
    out["visible_text_length"] = len(text)
    out["market_heading_occurrences"] = text.count(MARKET)
    out["guideline_occurrences"] = text.count(GUIDELINE)
    out["footer_occurrences"] = text.count(FOOTER)
    out["whole_page_exact_policy_guideline_occurrences"] = len(TARGET_RE.findall(text))
    out["whole_page_exact_deposit_occurrences"] = len(DEPOSIT_RE.findall(text))
    out["whole_page_exact_loan_occurrences"] = len(LOAN_RE.findall(text))

    market = text.rfind(MARKET)
    if market >= 0:
        guide = text.find(GUIDELINE, market)
        out["last_market_section_guideline_found"] = guide >= 0
        if guide >= 0:
            footer = text.find(FOOTER, guide)
            out["last_market_section_footer_found"] = footer >= 0
            if footer > guide:
                section = text[market:footer]
                out["last_market_section_policy_occurrences"] = len(
                    TARGET_RE.findall(section))
                out["last_market_section_deposit_occurrences"] = len(
                    DEPOSIT_RE.findall(section))
                out["last_market_section_loan_occurrences"] = len(
                    LOAN_RE.findall(section))

    # Distinguish repeated section headings/footers without outputting page
    # text or changing strict parser. A duplicate marker is not a second
    # genuine policy event or automatically valid page.
    off = 0
    matched = 0
    while True:
        start = text.find(MARKET, off)
        if start < 0:
            break
        off = start + len(MARKET)
        next_market = text.find(MARKET, off)
        end = len(text) if next_market < 0 else next_market
        section = text[start:end]
        if (GUIDELINE in section and FOOTER in section
                and len(TARGET_RE.findall(section)) == 1
                and len(DEPOSIT_RE.findall(section)) == 1
                and len(LOAN_RE.findall(section)) == 1):
            matched += 1
    out["earlier_market_sections_with_three_distinct_measures"] = matched

    try:
        strict = inspect_boj_home_guideline_receipt_lab(
            original_html=original_html,
            receipt=receipt,
            decision_at_utc=decision_at_utc,
        )
        state = strict.get("state") if type(strict) is dict else None
        reason = strict.get("reason") if type(strict) is dict else None
        out["strict_validator_state"] = (
            state if type(state) is str and state.isascii()
            and len(state) <= 100 else "MALFORMED_VALIDATOR_STATE"
        )
        out["strict_validator_reason_code"] = (
            reason if type(reason) is str and reason.isascii()
            and len(reason) <= 100 else "MALFORMED_REASON"
        )
    except (TypeError, ValueError, KeyError, OverflowError, RuntimeError):
        out["strict_validator_state"] = "STRICT_VALIDATOR_RAISED"
    out["state"] = "LAB_BOJ_HTML_STRUCTURE_COUNTED_NO_GO"
    out["reason"] = "STRUCTURE_COUNTS_NOT_ORIGINAL_ISSUER_OR_PIT_AUTHENTICATION"
    return out


def collect_boj_structure_once_lab(
    *, explicit_probe: Any,
    collector: Callable[[], tuple[bytes, dict[str, Any]]] = collect_boj_home_once_lab,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    out = _base("EXPLICIT_BoJ_PROBE_FLAG_REQUIRED")
    if explicit_probe is not True:
        return out
    if clock is None:
        clock = lambda: datetime.now(timezone.utc).replace(microsecond=0)
    if not callable(collector) or not callable(clock):
        out["reason"] = "INVALID_CLOCK_OR_COLLECTOR"
        return out
    out["official_https_get_attempts"] = 1
    try:
        body, receipt = collector()
        result = inspect_boj_home_structure_lab(
            original_html=body,
            receipt=receipt,
            decision_at_utc=clock(),
        )
        result["official_https_get_attempts"] = 1
        return result
    except HTTPError as exc:
        out["state"] = "LAB_BOJ_HTTP_DENIED_NO_GO"
        out["reason"] = (
            "OFFICIAL_HTTPS_HTTP_" + str(exc.code)
            if type(exc.code) is int and 400 <= exc.code <= 599
            else "OFFICIAL_HTTP_STATUS_UNUSABLE"
        )
        return out
    except (URLError, OSError, TypeError, ValueError, KeyError,
            OverflowError, RuntimeError, UnicodeError):
        out["state"] = "LAB_BOJ_HTTPS_OR_FORMAT_DENIED_NO_GO"
        out["reason"] = "ONE_OFFICIAL_HTTPS_ATTEMPT_OR_VALIDATION_FAILED"
        return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--diagnose-official-once", action="store_true")
    args = p.parse_args(argv)
    report = collect_boj_structure_once_lab(
        explicit_probe=args.diagnose_official_once)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["state"] == "LAB_BOJ_HTML_STRUCTURE_COUNTED_NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("SCHEMA", "inspect_boj_home_structure_lab", "collect_boj_structure_once_lab")
