"""Offline official-body semantic join before CPI/PPI Motor A PIT research.

The prior PIT contract checked only a caller-supplied digest and number.
This wrapper checks a VISIBLE actual's identity/value against its original
candidate BLS HTML using the existing, stricter CPI/PPI document parsers.

This is not publisher provenance: caller-provided HTML, HTTP receipts and
timestamps remain locally self-consistent CLAIMS, never first-seen attestation.
No network, disk, cron, trader, broker I/O, probabilities or operations.
The 672-slot prospective FX28 campaign remains unchanged.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

from atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab import OfficialActual
from atlasquant_trader_us_cpi_ppi_pit_visibility_cutoff_lab import (
    EventVintageClaim, inspect_us_cpi_ppi_pit_cutoff_lab,
)
from atlasquant_trader_us_cpi_source_custody_lab import RELEASE as CPI_RELEASE
from atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import (
    ClaimedBLSHtmlReceipt, URL as CPI_URL,
    inspect_bls_oct2026_release_text_lab,
)
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    ClaimedPostReleaseHTTP, OFFICIAL_URL as PPI_URL,
    RELEASE_UTC as PPI_RELEASE, inspect_ppi_oct2026_first_print_lab,
)

SCHEMA = "ATLASQUANT_US_CPI_PPI_ORIGINAL_BODY_PIT_JOIN_LAB_V1"
_RELEASE = {"CPI": CPI_RELEASE, "PPI": PPI_RELEASE}
_URL = {"CPI": CPI_URL, "PPI": PPI_URL}
_ACCEPT = {
    "CPI": ("LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED",
            "headline_oct2026_sa_mom_pct_body_claim"),
    "PPI": ("LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED",
            "headline_final_demand_sa_mom_pct_body_claim"),
}


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None or value.microsecond:
        return None
    try:
        return value.astimezone(timezone.utc) if value.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _numeric(value: Any) -> Decimal | None:
    if type(value) is not str:
        return None
    try:
        d = Decimal(value)
        return d if d.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _result(*, cutoff: Any, horizon: Any, claims: Any,
            reason: str | None = None) -> dict[str, Any]:
    """Return original fail-closed PIT status, never an operative signal."""
    h = horizon if type(horizon) is str else ""
    base = inspect_us_cpi_ppi_pit_cutoff_lab(
        decision_cutoff_utc=cutoff, research_horizon=h,
        event_claims=claims if reason is None else (),
    )
    base["schema"] = SCHEMA
    base["original_actual_value_checked_against_document_body"] = []
    base["official_body_join_is_publisher_authentication"] = False
    base["consensus_source_values_semantically_parsed_by_this_join"] = False
    base["ppi_and_cpi_issuer_first_seen_witnessed"] = False
    if reason is not None:
        base["reason"] = reason
        base["state"] = "LAB_CPI_PPI_OFFICIAL_BODY_JOIN_BLOCKED_NO_GO"
    return base


def inspect_us_cpi_ppi_official_body_join_lab(
    *, decision_cutoff_utc: Any, research_horizon: Any,
    event_claims: Any, actual_http_receipts: Any,
) -> dict[str, Any]:
    """Validate visible actuals against their supplied HTML, then apply PIT.

    For a historical cutoff earlier than an actual's claimed collection,
    drop the *future* actual before passing the roster to the PIT engine.
    Never look at that HTML or expose the future numeric claim. When visible,
    require strict BLS parse, identity, capture clock, source digest, and exact
    same-series SA MoM headline numeric value. CPI and PPI are separate events.
    """
    cutoff = _utc(decision_cutoff_utc)
    if (cutoff is None or type(research_horizon) is not str
            or research_horizon not in ("D1", "W1", "M1")
            or type(event_claims) not in (tuple, list)
            or len(event_claims) != 2
            or type(actual_http_receipts) is not dict
            or set(actual_http_receipts) != set(_RELEASE)):
        return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                       reason="INVALID_CUTOFF_ROSTER_OR_HTTP_RECEIPT_MAP")

    by_kind: dict[str, EventVintageClaim] = {}
    for row in event_claims:
        if (type(row) is not EventVintageClaim
                or row.kind not in _RELEASE or row.kind in by_kind):
            return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                           reason="INVALID_OR_DUPLICATED_ECONOMIC_EVENT")
        by_kind[row.kind] = row
    if set(by_kind) != set(_RELEASE):
        return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                       reason="MISSING_CPI_OR_PPI")

    checked: list[str] = []
    gated: list[EventVintageClaim] = []
    for kind in ("CPI", "PPI"):
        row = by_kind[kind]
        rec = actual_http_receipts[kind]
        actual = row.actual
        if actual is not None and type(actual) is not OfficialActual:
            return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                           reason=f"{kind}_INVALID_ACTUAL_OBJECT_TYPE")
        if actual is None:
            if row.actual_source_bytes is not None or rec is not None:
                return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                               reason=f"{kind}_UNPAIRED_ACTUAL_SOURCE_OR_RECEIPT")
            gated.append(row)
            continue

        captured = _utc(actual.locally_captured_at_utc)
        if captured is None:
            return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                           reason=f"{kind}_INVALID_ACTUAL_CAPTURE_CLOCK")
        if cutoff < _RELEASE[kind] or captured > cutoff:
            # Historical replay: future actuals must not enter either parser.
            gated.append(replace(row, actual=None, actual_source_bytes=None))
            continue
        if type(row.actual_source_bytes) is not bytes:
            return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                           reason=f"{kind}_MISSING_ACTUAL_BYTES")

        if kind == "CPI":
            if (type(rec) is not ClaimedBLSHtmlReceipt
                    or _utc(rec.captured_at_utc) != captured
                    or rec.source_url != CPI_URL):
                return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                               reason="CPI_HTTP_RECEIPT_CLOCK_OR_ORIGIN_MISMATCH")
            doc = inspect_bls_oct2026_release_text_lab(
                raw_html=row.actual_source_bytes, receipt=rec, as_of_utc=cutoff)
        else:
            if (type(rec) is not ClaimedPostReleaseHTTP
                    or _utc(rec.finished_utc) != captured
                    or rec.source_url != PPI_URL):
                return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                               reason="PPI_HTTP_RECEIPT_CLOCK_OR_ORIGIN_MISMATCH")
            doc = inspect_ppi_oct2026_first_print_lab(
                raw_html=row.actual_source_bytes, receipt=rec, as_of_utc=cutoff)

        accepted_state, metric_field = _ACCEPT[kind]
        extracted = _numeric(doc.get(metric_field)) if type(doc) is dict else None
        declared = _numeric(actual.numeric_value)
        if (type(doc) is not dict
                or doc.get("state") != accepted_state
                or extracted is None or declared is None
                or extracted != declared
                or actual.official_source_url != _URL[kind]
                or actual.original_sha256_claim != sha256(row.actual_source_bytes).hexdigest()
                or actual.scheduled_release_at_utc != _RELEASE[kind]):
            return _result(cutoff=cutoff, horizon=research_horizon, claims=(),
                           reason=f"{kind}_OFFICIAL_BODY_METRIC_OR_DIGEST_MISMATCH")
        checked.append(kind)
        gated.append(row)

    out = _result(cutoff=cutoff, horizon=research_horizon, claims=tuple(gated))
    if out["economic_events_reconciled"] != 2:
        # The pre-existing PIT engine still enforces period, consensus and
        # release semantics even after our additional original-body checks.
        out["state"] = "LAB_CPI_PPI_OFFICIAL_BODY_JOIN_BLOCKED_NO_GO"
        out["reason"] = "UPSTREAM_PIT_VINTAGE_VALIDATION_FAILED"
        return out
    out["original_actual_value_checked_against_document_body"] = checked
    out["reason"] = "VISIBLE_BLS_BODY_SEMANTICS_MATCH_LOCAL_CLAIMS_NOT_ISSUER_ATTESTATION"
    out["state"] = "LAB_CPI_PPI_OFFICIAL_BODY_JOIN_UNATTESTED_NO_GO"
    return out


__all__ = ("SCHEMA", "inspect_us_cpi_ppi_official_body_join_lab")
