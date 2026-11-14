"""RBNZ automated access restriction — current project policy, 14 Nov 2026.

The RBNZ published Terms of Use (last updated 11 Jul 2025) prohibit
automated access except public search engines following robots.txt or with
RBNZ's prior WRITTEN permission. Max bot request rates do NOT themselves
give blanket permission. A 403 was observed in the AtlasQuant GitHub
runner. The issuer offers an official allow-list access request form.

This module expresses the current FACT: AtlasQuant has no verified written
authorization. It never generates, presumes or solicits a credential.
An official public reference (and first-party B2 download link) may be
studied manually, but cannot be turned into an automated collector until
genuine permission has been received and reviewed explicitly.
"""
from __future__ import annotations

TERMS_URL = "https://www.rbnz.govt.nz/about-our-site/terms-of-use"
ALLOW_LIST_REQUEST_URL = (
    "https://www.rbnz.govt.nz/about-our-site/terms-of-use/allow-list-request"
)
DATA_FILE_INDEX_URL = (
    "https://www.rbnz.govt.nz/statistics/series/data-file-index-page"
)
B2_OCR_DATA_SOURCE_URL = (
    "https://rbnz.govt.nz/-/media/project/sites/rbnz/files/"
    "statistics/series/b/b2/hb2-daily-close.xlsx"
)
TERMS_LAST_UPDATED = "2025-07-11"
RBNZ_AUTOMATED_ACCESS_WRITTEN_PERMISSION_VERIFIED = False
RBNZ_BLOCK_REASON = (
    "RBNZ_PRIOR_WRITTEN_PERMISSION_REQUIRED_NO_AUTOMATED_GET"
)


def inspect_rbnz_automated_access_policy_lab() -> dict:
    """No external I/O, never an API credential or rate-forecast assertion."""
    return {
        "state": "LAB_RBNZ_AUTOMATED_ACCESS_TERMS_GATE_BLOCKED_NO_GO",
        "reason": RBNZ_BLOCK_REASON,
        "issuer_terms_url": TERMS_URL,
        "terms_last_updated_claim": TERMS_LAST_UPDATED,
        "issuer_allow_list_request_url": ALLOW_LIST_REQUEST_URL,
        "official_b2_data_index_url": DATA_FILE_INDEX_URL,
        "official_b2_ocr_xlsx_url_reference_only": B2_OCR_DATA_SOURCE_URL,
        "official_b2_contains_ocr_and_third_party_market_data": True,
        "automated_collection_permission_verified": False,
        "bot_quota_does_not_grant_permission": True,
        "issuer_html_403_seen_in_prior_cloud_run": True,
        "automatic_rbnz_collection_allowed": False,
        "current_nzd_ocr_raw_source_persisted_on_am12": False,
        "public_web_search_value_is_not_reproducible_source_receipt": True,
        "pre_event_consensus_or_signed_effect_validated": False,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


__all__ = (
    "TERMS_URL", "ALLOW_LIST_REQUEST_URL", "DATA_FILE_INDEX_URL",
    "B2_OCR_DATA_SOURCE_URL", "RBNZ_BLOCK_REASON",
    "RBNZ_AUTOMATED_ACCESS_WRITTEN_PERMISSION_VERIFIED",
    "inspect_rbnz_automated_access_policy_lab",
)
