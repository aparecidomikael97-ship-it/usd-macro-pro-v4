"""Offline ALFRED two-vintage CSV inspection for one BLS CPI LAB case.

A *caller supplied* CSV (not downloaded here) must identify each requested
historical vintage in its actual header. Never silently accept today's
values, swapped series, a misspelled vintage, or an unrelated observation.

The CSV is UNTRUSTED and provides no proof of acquisition time,
authenticity, rights to redistribute, pre-release consensus, or real OOS.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_TRADER_ALFRED_TWO_VINTAGE_CSV_LAB_V1"
EXPECTED_HEADER = (
    "observation_date", "CPIAUCNS_20260113", "CPIAUCNS_20260213",
)
TARGET_PERIOD = "2025-12-01"
MAX_CSV_CHARACTERS = 150_000
MAX_ROWS = 1800


def _refused(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_ALFRED_CSV_QUARANTINED",
        "reason": reason, "jan13_dec2025_value": None,
        "feb13_dec2025_value": None,
        "source_content_authenticated": False,
        "real_historical_custody_verified": False,
        "exact_intraday_availability_verified": False,
        "event_consensus_verified": False,
        "real_oos_authorized": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def _level(value: Any) -> Decimal | None:
    if not isinstance(value, str):
        return None
    if not value or len(value) > 25:
        return None
    try:
        n = Decimal(value)
    except InvalidOperation:
        return None
    if not n.is_finite() or not Decimal("0") < n < Decimal("1000000"):
        return None
    return n


def inspect_alfred_cpi_vintages_csv_lab(
    csv_text: Any, bls_case_manifest: Any,
) -> dict[str, Any]:
    """Inspect exact 2026-01-13, 2026-02-13 CPIAUCNS columns.

    Caller-supplied bytes and timestamps never prove external provenance.
    """
    if (not isinstance(bls_case_manifest, Mapping) or
            bls_case_manifest.get("schema") !=
            "ATLASQUANT_TRADER_BLS_CPI_ALFRED_CASE_LAB_V1"):
        return _refused("This probe requires the isolated documented BLS CPI case")
    case_alfred = bls_case_manifest.get("alfred")
    sources = bls_case_manifest.get("sources")
    if (not isinstance(case_alfred, Mapping) or
            case_alfred.get("series") != "CPIAUCNS" or
            case_alfred.get("requested_vintages") !=
            ["2026-01-13", "2026-02-13"] or
            not isinstance(sources, list) or len(sources) != 2 or
            not all(isinstance(x, Mapping) for x in sources) or
            sources[0].get("reference_month") != "2025-12" or
            sources[0].get("cpi_u_nsa_index") != 324.054 or
            sources[1].get("table1_dec2025_nsa_index") != 324.054):
        return _refused("BLS comparison source or requested ALFRED series changed")
    if (not isinstance(csv_text, str) or
            len(csv_text) > MAX_CSV_CHARACTERS or not csv_text.strip()):
        return _refused("Missing or oversized plain text CSV")
    if "\x00" in csv_text:
        return _refused("Invalid binary or null byte")
    try:
        reader = csv.reader(StringIO(csv_text, newline=""), strict=True)
        header = next(reader, None)
        if header != list(EXPECTED_HEADER):
            return _refused("Vintage CSV headers are not EXACT requested dates")
        count = 0
        dates = set()
        selected = None
        for row in reader:
            count += 1
            if count > MAX_ROWS or len(row) != len(EXPECTED_HEADER):
                return _refused("Unexpected number of rows or columns")
            recorded = row[0]
            try:
                dt = date.fromisoformat(recorded)
            except (ValueError, TypeError):
                return _refused("Observation date is not ISO yyyy-mm-dd")
            if dt.isoformat() != recorded or recorded in dates:
                return _refused("Malformed or repeated observation date")
            dates.add(recorded)
            if dt > date(2026, 2, 13):
                return _refused("Future data exists in historic series export")
            if recorded == TARGET_PERIOD:
                initial, later = _level(row[1]), _level(row[2])
                if initial is None or later is None:
                    return _refused("Target observation absent in one vintage")
                selected = (initial, later)
    except (csv.Error, UnicodeError, ValueError):
        return _refused("Unreadable or malformed CSV")
    if selected is None:
        return _refused("December 2025 observation row not in export")
    first, second = selected
    expected = Decimal("324.054")
    same = first == expected and second == expected
    return {
        "schema": SCHEMA,
        "state": ("LAB_ALFRED_TWO_VINTAGE_CANDIDATE_MATCH"
                  if same else "LAB_ALFRED_BLS_DISAGREEMENT_REVIEW"),
        "series": "CPIAUCNS", "observation_date": TARGET_PERIOD,
        "requested_vintages": ["2026-01-13", "2026-02-13"],
        "jan13_dec2025_value": str(first),
        "feb13_dec2025_value": str(second),
        "bls_original_nsa_value": str(expected),
        "candidate_values_match_bls": same,
        "csv_rows_seen": count,
        "source_content_authenticated": False,
        "real_historical_custody_verified": False,
        "exact_intraday_availability_verified": False,
        "event_consensus_verified": False,
        "real_oos_authorized": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "warning": "Caller-supplied CSV may be forged or mislabelled: "
                   "capture raw file/hash from official source and verify "
                   "licence and historical custody before any real OOS.",
    }


__all__ = ["SCHEMA", "EXPECTED_HEADER", "inspect_alfred_cpi_vintages_csv_lab"]
