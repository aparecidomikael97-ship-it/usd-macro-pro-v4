"""LAB-only documentary PPI / CAD same-minute guard for the frozen 28 FX pairs.

Checks exact archived TD Economics HTML SHA before interpreting event tables.
Two PPI rows = ONE US economic root; CAD manufacturing sales = another root
scheduled at the same minute. A partial calendar NEVER makes any other pair
causally clean, proves first publication, or authorizes trading.

Pure/read-only: no network, MT5, price data, orders, accounts or file writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    TD_PRE_EVENT_HTML_SHA256, EVENT_UTC,
)
from atlasquant_trader_us_ppi_pre_event_preview_lab import (
    _Tables, EXPECTED_HEADER, MAX_HTML_BYTES,
)

SCHEMA = "ATLASQUANT_PPI_TD_US_CAD_SAME_MINUTE_FX28_GUARD_LAB_V1"
PASS = "LAB_PPI_TD_CAD_SAME_MINUTE_DOCUMENTARY_CONFOUNDER_NO_GO"
BLOCKED = "LAB_PPI_TD_CO_RELEASE_SOURCE_BLOCKED_NO_GO"

def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": BLOCKED, "reason": reason,
        "td_original_sha256_verified": False,
        "td_publisher_and_first_seen_independently_attested": False,
        "scheduled_minute_utc_claim": EVENT_UTC.isoformat(),
        "same_minute_economic_roots_documentary": None,
        "usd_cad_directly_exposed_to_two_roots": False,
        "cad_pairs_exposed_to_cad_release": [],
        "usd_pairs_exposed_to_ppi": [],
        "all_28_pairs_causally_clean": False,
        "all_28_pairs_eligible_for_direction": False,
        "ppi_exclusive_causality_for_usdcad": False,
        "incomplete_calendar_cannot_certify_other_21_pairs": True,
        "independent_macro_event_count_verified": 0,
        "validated_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "http_requests": 0, "mt5_calls": 0, "file_writes": 0,
        "research_only": True,
    }

def _extract_from_parsed_rows(rows: Any) -> tuple[str, ...] | None:
    """Strictly parse the source table's SECTION context, not row text alone.

    Return a tuple of confirmed root names or None. For unit testing only,
    this helper does NOT attest any source; the public gate checks exact SHA.
    """
    if not isinstance(rows, (tuple, list)) or not 15 <= len(rows) <= 80:
        return None
    if tuple(EXPECTED_HEADER) not in rows:
        return None
    sections = {"United States": 0, "Canada": 0, "International": 0}
    country = None
    by_name: dict[tuple[str, str], list[tuple[str, ...]]] = {}
    est_footer = False
    for raw in rows:
        if not isinstance(raw, tuple) or any(type(v) is not str for v in raw):
            return None
        if len(raw) == 1 and raw[0] in sections:
            sections[raw[0]] += 1
            if sections[raw[0]] != 1:
                return None
            country = raw[0]
            continue
        if len(raw) == 1 and "*Eastern Standard Time." in raw[0]:
            est_footer = True
            continue
        if len(raw) < 5:
            continue
        if raw[0] == "Nov 13" and raw[1] == "8:30":
            if country not in sections or country == "International":
                return None
            key = (country, raw[3])
            by_name.setdefault(key, []).append(raw)
    if set(k for k, n in sections.items() if n == 1) != set(sections) or not est_footer:
        return None
    expected = {
        ("United States", "PPI Final Demand"): ("Oct", "0.4"),
        ("United States", "PPI Ex Food and Energy"): ("Oct", "0.3"),
        ("Canada", "Manufacturing Sales"): ("Sep", "0.1"),
    }
    if set(by_name) != set(expected):
        return None
    for key, (period, consensus) in expected.items():
        matches = by_name[key]
        if len(matches) != 1 or len(matches[0]) != 8:
            return None
        row = matches[0]
        if (row[0], row[1], row[2], row[4], row[6]) != (
                "Nov 13", "8:30", "", period, consensus):
            return None
    return ("US_PPI_OCT2026", "CAD_MANUFACTURING_SALES_SEP2026")

def inspect_ppi_td_same_minute_fx28_lab(*, td_original_html: Any) -> dict[str, Any]:
    out = _blocked("TD_ORIGINAL_BYTES_SHA_OR_SIZE_NOT_VALID")
    if (type(td_original_html) is not bytes
            or not 2000 <= len(td_original_html) <= MAX_HTML_BYTES
            or sha256(td_original_html).hexdigest() != TD_PRE_EVENT_HTML_SHA256):
        return out
    try:
        doc = _Tables()
        doc.feed(td_original_html.decode("cp1252", "strict"))
        doc.close()
        if doc.row is not None or doc.cell is not None:
            return _blocked("UNFINISHED_TD_HTML_TABLE")
        roots = _extract_from_parsed_rows(doc.rows)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        return _blocked("TD_HTML_TABLE_PARSING_FAILED")
    if roots is None:
        return _blocked("FROZEN_TD_EVENT_SECTION_OR_830_CALENDAR_MISMATCH")
    if (EVENT_UTC != datetime(2026, 11, 13, 13, 30, tzinfo=timezone.utc)
            or len(OFFICIAL_PAIRS) != 28):
        return _blocked("FROZEN_EVENT_TIME_OR_FX28_ROSTER_DRIFT")
    cad = tuple(pair for pair in OFFICIAL_PAIRS if "CAD" in split_pair(pair))
    usd = tuple(pair for pair in OFFICIAL_PAIRS if "USD" in split_pair(pair))
    overlap = tuple(pair for pair in cad if pair in usd)
    if len(cad) != 7 or len(usd) != 7 or len(overlap) != 1:
        return _blocked("G8_PAIR_EXPOSURE_ROSTER_INCOHERENT")
    out.update({
        "state": PASS,
        "reason": "SOURCE_PIN_MATCHES_TWO_SCHEDULED_ROOTS_NOT_CAUSAL_OR_TRADE_PROOF",
        "td_original_sha256_verified": True,
        "same_minute_economic_roots_documentary": list(roots),
        "usd_cad_directly_exposed_to_two_roots": overlap[0] in ("USD/CAD", "CAD/USD"),
        "cad_pairs_exposed_to_cad_release": list(cad),
        "usd_pairs_exposed_to_ppi": list(usd),
        "independent_macro_event_count_verified": 0,
    })
    return out

__all__ = ("SCHEMA", "PASS", "BLOCKED", "inspect_ppi_td_same_minute_fx28_lab")
