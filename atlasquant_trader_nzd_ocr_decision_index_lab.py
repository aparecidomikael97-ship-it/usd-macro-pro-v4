"""RBNZ policy decision index: retrospective link discovery, not P-I-T data.

On 2026-11-08 the official RBNZ history page was inspected. It lists OCR
decisions since 1999, with media release links, and explicitly warns that its
index is updated with a 24-hour lag. The 2025-26 rows below were transcribed
from that present-day index for a small *research-only* coverage pilot.

This present-day table is NOT evidence of the exact historical announcement
second or a contemporaneously saved/unrevised decision document. Do not pass
values from this module to the macro bias/backtest execution pipeline.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "ATLASQUANT_TRADER_NZD_OCR_DECISION_INDEX_LAB_V1"
REVIEWED_DATE_UTC = "2026-11-08"
INDEX_URL = "https://www.rbnz.govt.nz/monetary-policy/monetary-policy-decisions"
OCT2026_MEDIA_RELEASE_URL = (
    "https://www.rbnz.govt.nz/news-and-events/news/2026/10/"
    "ocr-held-at-2-75-percent"
)
RELEASE_PRACTICE_URL = "https://www.rbnz.govt.nz/news-and-events/how-we-release-information"

# An intentionally bounded manually checked subset of the current OCR index.
# Decision date is not publication timestamp or data-availability timestamp.
INDEX_RESEARCH_ROWS: tuple[tuple[str, str], ...] = (
    ("2025-02-19", "3.75"),
    ("2025-04-09", "3.50"),
    ("2025-05-28", "3.25"),
    ("2025-07-09", "3.25"),
    ("2025-08-20", "3.00"),
    ("2025-10-08", "2.50"),
    ("2025-11-26", "2.25"),
    ("2026-02-18", "2.25"),
    ("2026-04-08", "2.25"),
    ("2026-05-27", "2.25"),
    ("2026-07-08", "2.50"),
    ("2026-09-02", "2.75"),
    ("2026-10-28", "2.75"),
)


def inspect_nzd_ocr_decision_index_lab() -> dict[str, Any]:
    """Expose a static research inventory, without decision-time replay API."""
    rows = [
        {
            "decision_date_nz": date,
            "ocr_pct_on_current_index": rate,
            "reviewed_index_on_date_utc": REVIEWED_DATE_UTC,
            "original_decision_issue_time_attested": False,
            "issuer_document_bytes_as_of_decision_archived": False,
            "eligible_for_historical_backtest": False,
        }
        for date, rate in INDEX_RESEARCH_ROWS
    ]
    return {
        "schema": SCHEMA,
        "state": "LAB_RBNZ_DECISION_INDEX_RETROSPECTIVE_RESEARCH_ONLY",
        "reviewed_on_utc_date": REVIEWED_DATE_UTC,
        "currency": "NZD", "family": "POLICY",
        "source_url": INDEX_URL,
        "2026_october_media_release_url": OCT2026_MEDIA_RELEASE_URL,
        "release_practice_url": RELEASE_PRACTICE_URL,
        "history_page_lists_decisions_since_year": 1999,
        "index_update_delay_notice_hours": 24,
        "index_updated_later_than_original_announcements": True,
        "issuer_original_release_second_proved": False,
        "historic_bytes_captured_during_release": False,
        "index_rows_research_only": rows,
        "index_rows_count": len(rows),
        "original_point_in_time_vintage_attested": False,
        "historical_backtest_approved": False,
        "cross_currency_strength_comparison_approved": False,
        "forecast_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests_at_runtime": 0, "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "INDEX_URL", "INDEX_RESEARCH_ROWS", "inspect_nzd_ocr_decision_index_lab"]
