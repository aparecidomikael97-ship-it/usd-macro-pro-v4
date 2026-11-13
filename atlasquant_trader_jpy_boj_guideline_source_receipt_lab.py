"""BoJ current policy guideline (NOT actual call rate) source gate, LAB.

Only validate raw HTML bytes received through a separate explicit manual
HTTPS capture. The official BoJ landing page states a *guideline* for the
uncollateralized overnight call rate, while the realized average call
market rate, complementary deposit interest and basic loan rate are
distinct monetary instruments. Never treat a defeated proposal or an
observed market rate as the decision.

Reference: Oct 30 2026 original Bank of Japan monetary policy statement
https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf
It documents a guideline around 1.25 percent, a rejected 1.5 percent
dissent and issuer-reported release at 12:02 JST (NO independently
authenticated first-seen receipt). The homepage is CURRENT and may
change. No historical retrospective PIT certification of rate/vintage.

This pure gate has no requests, file writes, account, broker, trades,
orders, forecasts, or calibrated probabilities.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA = "ATLASQUANT_JPY_BOJ_CURRENT_POLICY_GUIDELINE_HTML_LAB_V1"
URL = "https://www.boj.or.jp/en/"
STATEMENT_URL = "https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf"
MAX_BYTES = 300_000
SHA = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL = re.compile(r"(?:0|[1-9]\d{0,1})(?:\.\d{1,3})?\Z")
TARGET_RE = re.compile(
    r"The Bank will encourage the uncollateralized overnight call rate"
    r" to remain at around ([0-9]{1,2}(?:\.[0-9]{1,3})?) percent\."
)
DEPOSIT_RE = re.compile(
    r"Interest Rate Applied to the Complementary Deposit Facility"
    r" ([0-9]{1,2}(?:\.[0-9]{1,3})?)% since "
    r"([A-Za-z]+ [0-9]{1,2}, 20[0-9]{2})"
)
LOAN_RE = re.compile(
    r"Basic Loan Rate ([0-9]{1,2}(?:\.[0-9]{1,3})?)% since "
    r"([A-Za-z]+ [0-9]{1,2}, 20[0-9]{2})"
)
RECEIPT_KEYS = frozenset((
    "source_url", "final_url", "http_status", "content_type",
    "body_sha256", "started_at_utc", "finished_at_utc",
    "https_validation_claim", "redirects_followed",
))


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.ignored_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data):
        if not self.ignored_depth:
            self.parts.append(data)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_JPY_BOJ_GUIDELINE_SOURCE_BLOCKED",
        "reason": reason,
        "currency": "JPY",
        "issuer": "Bank of Japan",
        "policy_instrument": "BOJ_UNCOLLATERALIZED_OVERNIGHT_CALL_RATE_GUIDELINE",
        "source_url": URL,
        "official_statement_reference_url": STATEMENT_URL,
        "html_sha256_matches_local_receipt": False,
        "transport_claim_structurally_consistent": False,
        "visible_market_operations_guideline_parsed": False,
        "policy_guideline_target_pct_claim": None,
        "complementary_deposit_pct_claim": None,
        "basic_loan_rate_pct_claim": None,
        "supplementary_rates_separately_typed": False,
        "realized_overnight_call_rate_used_as_policy_guideline": False,
        "dissent_or_rejected_proposal_used_as_policy": False,
        "fomc_or_other_central_bank_rate_conflated": False,
        "capture_finished_at_utc_claim": None,
        "boJ_current_policy_source_current_only": True,
        "original_oct30_policy_pdf_bytes_captured": False,
        "oct30_issuer_release_time_independently_attested": False,
        "historic_first_seen_source_vintage_authenticated": False,
        "historical_boj_decision_cutoff_authenticated": False,
        "g8_policy_sources_complete": False,
        "fx28_bilateral_macro_authenticated": False,
        "calibrated_directional_probability": None,
        "validated_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "live_alert_allowed": False,
        "network_calls": 0,
        "files_written": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _utc(raw: Any) -> datetime | None:
    if type(raw) is not str or not re.fullmatch(
            r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", raw):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def _decision(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.microsecond:
        return None
    try:
        return value.astimezone(timezone.utc) if value.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _rate(text: Any) -> Decimal | None:
    if type(text) is not str or DECIMAL.fullmatch(text) is None:
        return None
    try:
        value = Decimal(text)
        return value if value.is_finite() and Decimal("0") <= value <= Decimal("30") else None
    except InvalidOperation:
        return None


def inspect_boj_home_guideline_receipt_lab(
    *, original_html: Any, receipt: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    result = _base("HTML_RECEIPT_OR_DECISION_CLOCK_INVALID")
    now = _decision(decision_at_utc)
    if (type(original_html) is not bytes
            or not 300 <= len(original_html) <= MAX_BYTES
            or type(receipt) is not dict or set(receipt) != RECEIPT_KEYS
            or now is None):
        return result
    if (receipt["source_url"] != URL or receipt["final_url"] != URL
            or type(receipt["http_status"]) is not int or receipt["http_status"] != 200
            or type(receipt["content_type"]) is not str
            or receipt["content_type"].split(";")[0].strip().lower() != "text/html"
            or receipt["https_validation_claim"] is not True
            or receipt["redirects_followed"] is not False
            or type(receipt["body_sha256"]) is not str
            or SHA.fullmatch(receipt["body_sha256"]) is None):
        result["reason"] = "NONOFFICIAL_BOJ_URL_OR_UNSAFE_TRANSPORT_CLAIM"
        return result
    before = _utc(receipt["started_at_utc"])
    after = _utc(receipt["finished_at_utc"])
    if (before is None or after is None
            or not before <= after <= now
            or after - before > timedelta(seconds=30)):
        result["reason"] = "BOJ_CAPTURE_CLOCK_AFTER_DECISION_OR_INVALID"
        return result
    if sha256(original_html).hexdigest() != receipt["body_sha256"]:
        result["reason"] = "BOJ_ORIGINAL_HTML_SHA256_MISMATCH"
        return result
    result["html_sha256_matches_local_receipt"] = True
    result["transport_claim_structurally_consistent"] = True

    try:
        parser = _Text()
        parser.feed(original_html.decode("utf-8-sig"))
        parser.close()
        text = " ".join(" ".join(parser.parts).split())
        market = text.rfind("The Bank's Market Operations")
        if market < 0:
            raise ValueError("market section absent")
        guide = text.find("Guideline", market)
        footer = text.find("Bank of Japan Operations", guide)
        if guide < 0 or footer < 0 or footer <= guide:
            raise ValueError("market guideline/terminal section absent")
        section = text[market:footer]
        target = TARGET_RE.findall(section)
        deposit = DEPOSIT_RE.findall(section)
        loan = LOAN_RE.findall(section)
        if len(target) != 1 or len(deposit) != 1 or len(loan) != 1:
            raise ValueError("ambiguous or missing policy/loan/deposit measure")
        policy_rate = _rate(target[0])
        deposit_rate = _rate(deposit[0][0])
        loan_rate = _rate(loan[0][0])
        if any(x is None for x in (policy_rate, deposit_rate, loan_rate)):
            raise ValueError("invalid policy/loan/deposit rate")
        # We do not presume that the realized call-money rate equals the
        # policy GUIDELINE, or that the deposit rate is the chosen target.
        if not (market < guide < footer and deposit_rate <= loan_rate):
            raise ValueError("incoherent market operations section")
    except (UnicodeError, ValueError, TypeError, OverflowError):
        result["reason"] = "BOJ_POLICY_GUIDELINE_INSTRUMENT_OR_HTML_STRUCTURE_INVALID"
        return result

    result.update({
        "state": "LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO",
        "reason": "CURRENT_BOJ_HTML_NOT_OCT30_FIRST_RELEASE_OR_PIT_EVIDENCE",
        "visible_market_operations_guideline_parsed": True,
        "policy_guideline_target_pct_claim": str(policy_rate),
        "complementary_deposit_pct_claim": str(deposit_rate),
        "basic_loan_rate_pct_claim": str(loan_rate),
        "supplementary_rates_separately_typed": True,
        "capture_finished_at_utc_claim": after.isoformat(),
    })
    return result


__all__ = ("SCHEMA", "URL", "STATEMENT_URL", "MAX_BYTES",
           "inspect_boj_home_guideline_receipt_lab")
