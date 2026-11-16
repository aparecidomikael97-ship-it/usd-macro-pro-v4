"""REAL-BYTE BLS PPI September 2026 *revision-vintage* comparison (LAB).

Two DIFFERENT official news-release editions may describe the SAME
September 2026 monthly seasonally adjusted (SA) measurement:
- September's report, 15 October, says September headline 1.3 / core 0.7.
- October's report, 13 November, revises September to headline 1.4 /
  core 0.8, alongside OCTOBER's separate new values 0.3 / 0.3.

Both protected original HTMLs were captured AFTER the releases and only
become visible to local research at their actual preserved capture times:
Sep release document captured 16 Nov; Oct release document 14 Nov.
No retrospective proof of the source's first printing, publisher first-seen,
market consensus, user access on original release dates, or any Forex result.

This is a strict, zero-I/O documentary comparator; it never replaces the
original vintage with the revision when answering historical questions.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any
import re

from atlasquant_trader_us_bls_sep2026_original_pair_once_lab import (
    inspect_sep2026_bls_release_body_lab,
)
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    _BlsTables, _extract_table_value, ClaimedPostReleaseHTTP,
    inspect_ppi_oct2026_first_print_lab,
)
from atlasquant_trader_bls_four_real_originals_pit_replay_lab import PINS

SCHEMA = "ATLASQUANT_BLS_PPI_SEP2026_REAL_TWO_RELEASE_VINTAGES_LAB_V1"
SEP_PIN = PINS["US_PPI_SEP2026"]
OCT_PIN = PINS["US_PPI_OCT2026"]
SEP_CAPTURE = datetime.fromisoformat(SEP_PIN[5])
OCT_CAPTURE = datetime.fromisoformat(OCT_PIN[5])
SEP_RELEASE = datetime.fromisoformat(SEP_PIN[6])
OCT_RELEASE = datetime.fromisoformat(OCT_PIN[6])
SEP_HASH = SEP_PIN[3]
OCT_HASH = OCT_PIN[3]

# The full header *shape* is fixed: BLS implicit Table-1 grammar, not a guess
# that "the last numerical column" is the right period after a revision.
TOP = ("grouping", "commodity code", "relative importance",
       "unadjusted 12-month percent change",
       "seasonally adjusted 1-month percent change")
LOWER = {
    "sep": ("Apr. to May", "May to June", "June to July",
            "July to Aug.", "Aug. to Sept."),
    "oct": ("May to June", "June to July", "July to Aug.",
            "Aug. to Sept.", "Sept. to Oct."),
}
TARGET = {"headline": ("Final demand", "4"),
          "core_ex_food_energy": ("Final demand less foods and energy", "49104")}


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        return value.astimezone(timezone.utc) if value.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str, *, visible: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_PPI_SEP2026_REAL_RELEASE_VINTAGE_REPLAY_HARD_NO_GO",
        "reason": reason,
        "documentary_source_denominator": 2,
        "originals_visible_at_local_cutoff": visible,
        "original_sep_release_visible": False,
        "oct_release_with_sep_revision_visible": False,
        "sep_reported_sep2026_sa_mom_headline_pct": None,
        "sep_reported_sep2026_sa_mom_core_ex_food_energy_pct": None,
        "oct_reported_revised_sep2026_sa_mom_headline_pct": None,
        "oct_reported_revised_sep2026_sa_mom_core_ex_food_energy_pct": None,
        "later_revision_minus_first_release_headline_pp": None,
        "later_revision_minus_first_release_core_pp": None,
        "oct2026_actual_headline_sa_mom_pct": None,
        "oct2026_actual_core_ex_food_energy_sa_mom_pct": None,
        "original_sep_release_html_sha256": None,
        "oct_release_html_sha256": None,
        "local_capture_time_claims_not_publisher_first_seen": True,
        "original_first_print_time_independently_authenticated": False,
        "economic_consensus_pre_event_authenticated": False,
        "independent_directional_fx_predictions": 0,
        "out_of_sample_forex_trials": 0,
        "accuracy": None,
        "bias_usd": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "fx28_672_slots_changed": False,
        "http_requests": 0,
        "file_writes": 0,
        "broker_or_mt5_calls": 0,
        "new_cost_brl": 0,
    }


def _clean_month_header(raw: str) -> str:
    text = " ".join(raw.split())
    text = re.sub(r"\s*\(\s*p\s*\)\s*$", "", text, flags=re.I)
    return text.casefold()


def _ppi_table1_sep_2026_values(raw_html: bytes, *, edition: str) -> dict[str, Decimal] | None:
    """Extract fixed September SA-MoM columns from two distinct official editions.

    Pure parsing works with synthetic fixtures, but the PUBLIC comparator
    demands exact independently pinned SHA-256 of both preserved real HTMLs.
    """
    if edition not in ("sep", "oct") or type(raw_html) is not bytes:
        return None
    try:
        decoded = raw_html.decode("utf-8", "surrogateescape")
        if sum("\udc80" <= c <= "\udcff" for c in decoded) > 32:
            return None
        doc = _BlsTables()
        doc.feed(decoded)
        doc.close()
        if doc._active is not None or doc._cell is not None or doc._row is not None:
            return None
    except (UnicodeError, ValueError, TypeError, RecursionError, OverflowError):
        return None
    period = "September 2026" if edition == "sep" else "October 2026"
    selection = [
        (rows, doc.table_layouts[i])
        for i, (scope, rows) in enumerate(doc.tables)
        if "Table 1." in scope and period in scope
        and "seasonally adjusted" in scope.lower()
    ]
    if len(selection) != 1:
        return None
    rows, layout_rows = selection[0]
    if len(layout_rows) < 4:
        return None
    first, second = layout_rows[:2]
    if len(first) != 5 or len(second) != 8:
        return None
    # The REAL two BLS pages use HTML rowspan/colspan for the top
    # five headings. The existing issuer parser also permits the known
    # implicit (all 1x1) layout. Accept ONLY these two fixed grammars;
    # never silently flatten arbitrary spans into a guessed month.
    if any(kind != "th" for cells in (first, second)
           for _, kind, _, _ in cells):
        return None
    top_spans = tuple((row_span, col_span)
                      for _, _, row_span, col_span in first)
    observed_bls_spans = ((2, 1), (1, 2), (2, 1), (1, 1), (1, 5))
    implicit_spans = ((1, 1),) * 5
    if (top_spans not in (observed_bls_spans, implicit_spans)
            or any((row_span, col_span) != (1, 1)
                   for _, _, row_span, col_span in second)):
        return None
    top = tuple(" ".join(x.split()).casefold() for x, _, _, _ in first)
    if top[0] != TOP[0] or top[1] != TOP[1]:
        return None
    if any(TOP[i] not in top[i] for i in (2, 3, 4)):
        return None
    lower = tuple(_clean_month_header(x) for x, _, _, _ in second)
    if (lower[:2] != ("group code", "item code")
            or ("2025" not in lower[2] or "2026" not in lower[2])
            or lower[3:] != tuple(x.casefold() for x in LOWER[edition])):
        return None
    # BLS Table 1 has an extra "Grouping" physical TH before the FD code
    # and all lower-header cells. Therefore lower-column index + 2.
    month_header_index = 3 + LOWER[edition].index("Aug. to Sept.")
    month_column = month_header_index + 2
    if month_column >= 10:
        return None
    values = {}
    for kind, (label, code) in TARGET.items():
        number = _extract_table_value(rows, label, code, month_column, 10)
        if number is None:
            return None
        values[kind] = number
    return values


def inspect_real_ppi_sep2026_release_vintages_lab(
    *, sep_original_html: Any, oct_original_html: Any,
    research_cutoff_utc: Any,
) -> dict[str, Any]:
    """Conservative replay: data captured after cutoff remains invisible."""
    now = _utc(research_cutoff_utc)
    out = _blocked("INVALID_CUTOFF_OR_MISSING_RELEASE_ORIGINALS")
    if now is None:
        return out
    # A timestamp makes an original TIME-ELIGIBLE, not actually present.
    # Only count a document after checking its physical bytes, pinned SHA
    # and strict source/metric identity. Future originals are not even
    # inspected before their own local capture cutoff.
    sep_eligible = now >= SEP_CAPTURE
    oct_eligible = now >= OCT_CAPTURE
    verified = 0
    if oct_eligible:
        if (type(oct_original_html) is not bytes
                or sha256(oct_original_html).hexdigest() != OCT_HASH):
            return _blocked("LOCALLY_ELIGIBLE_OCT_ORIGINAL_MISSING_OR_SHA256_INVALID")
        actual = inspect_ppi_oct2026_first_print_lab(
            raw_html=oct_original_html,
            receipt=ClaimedPostReleaseHTTP(
                OCT_PIN[7], 200, "text/html",
                OCT_CAPTURE - timedelta(seconds=1), OCT_CAPTURE, OCT_HASH,
            ),
            as_of_utc=now,
        )
        if (actual["state"] != "LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED"
                or actual.get("source_sha256") != OCT_HASH
                or actual.get("headline_final_demand_sa_mom_pct_body_claim") != "0.3"
                or actual.get("core_ex_food_energy_sa_mom_pct_body_claim") != "0.3"):
            return _blocked("OCTOBER_BLS_SOURCE_OR_ID_NOT_CONFIRMED")
        verified += 1
    if sep_eligible:
        if (type(sep_original_html) is not bytes
                or sha256(sep_original_html).hexdigest() != SEP_HASH):
            return _blocked("LOCALLY_ELIGIBLE_SEP_ORIGINAL_MISSING_OR_SHA256_INVALID")
        sep_checked = inspect_sep2026_bls_release_body_lab(
            kind="PPI", raw_html=sep_original_html)
        if (sep_checked is None
                or sep_checked.get("sa_mom_pct_body_claim") != "1.3"
                or sep_checked.get("original_sha256") != SEP_HASH):
            return _blocked("SEPTEMBER_BLS_RELEASE_ID_OR_HEADLINE_MISMATCH")
        verified += 1
    if not (sep_eligible and oct_eligible):
        # Document without an actual pinned source is NOT counted merely
        # because its alleged capture timestamp has elapsed.
        out.update({
            "reason": "ONE_OR_BOTH_ORIGINALS_NOT_YET_CAPTURED_AT_LOCAL_CUTOFF",
            "originals_visible_at_local_cutoff": verified,
            "original_sep_release_visible": sep_eligible and verified >= 1,
            "oct_release_with_sep_revision_visible": oct_eligible,
        })
        return out
    if sep_original_html == oct_original_html:
        return _blocked("REUSED_ORIGINAL_FOR_TWO_EDITION_IDENTITIES")
    first = _ppi_table1_sep_2026_values(sep_original_html, edition="sep")
    later = _ppi_table1_sep_2026_values(oct_original_html, edition="oct")
    if (first is None or later is None
            or first != {"headline": Decimal("1.3"),
                         "core_ex_food_energy": Decimal("0.7")}
            or later != {"headline": Decimal("1.4"),
                          "core_ex_food_energy": Decimal("0.8")}):
        return _blocked("BLS_TABLE1_SEPTEMBER_VINTAGES_OR_COLUMN_MISMATCH", visible=2)
    out.update({
        "state": "LAB_PPI_SEP2026_TWO_REAL_VINTAGES_RECONCILED_NO_GO",
        "reason": "REAL_POSTRELEASE_ORIGINALS_SHOW_PRIOR_MONTH_REVISION_NOT_FORECAST",
        "originals_visible_at_local_cutoff": 2,
        "original_sep_release_visible": True,
        "oct_release_with_sep_revision_visible": True,
        "sep_reported_sep2026_sa_mom_headline_pct": "1.3",
        "sep_reported_sep2026_sa_mom_core_ex_food_energy_pct": "0.7",
        "oct_reported_revised_sep2026_sa_mom_headline_pct": "1.4",
        "oct_reported_revised_sep2026_sa_mom_core_ex_food_energy_pct": "0.8",
        "later_revision_minus_first_release_headline_pp": "0.1",
        "later_revision_minus_first_release_core_pp": "0.1",
        "oct2026_actual_headline_sa_mom_pct": "0.3",
        "oct2026_actual_core_ex_food_energy_sa_mom_pct": "0.3",
        "original_sep_release_html_sha256": SEP_HASH,
        "oct_release_html_sha256": OCT_HASH,
    })
    return out


__all__ = ("SCHEMA", "SEP_HASH", "OCT_HASH", "SEP_CAPTURE", "OCT_CAPTURE",
           "inspect_real_ppi_sep2026_release_vintages_lab")
