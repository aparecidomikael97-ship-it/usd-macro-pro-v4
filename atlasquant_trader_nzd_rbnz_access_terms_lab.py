"""RBNZ automated-access terms CURRENT as of 12 Nov 2026 (reconciled).

IMPORTANT: The issuer UPDATED its Terms of Use on 12 Nov 2026.
The old 11 Jul 2025 blanket prior-written-permission wording no longer
governs ordinary automation. The current terms explicitly PERMIT it under:
  * <=120 requests/hour;
  * User-Agent 'RBNZ-Automated-Agent/<organisation>/<application>';
  * reasonable behavior, no excess pre-release requests;
  * issuer may restrict or suspend access.
Prior approval + static outbound public IP is for HIGHER-rate access only.

AtlasQuant previously got HTTP 403 on the RBNZ OCR HTML route. This
repo voluntarily SUSPENDS automatic retrieval on THAT route to respect the
actual access refusal, even though ordinary compliant automation is
permitted elsewhere by the current terms. Do not try alternate paths
merely to evade 403. The issuer expressly offers an XML feed with media
releases (including OCR decisions) and an official B2 Excel dataset; these
are future compliant-INTEGRATION candidates, NOT yet ingested or attested.
No unlicensed third-party market data from B2 may be redistributed.
"""
from __future__ import annotations

TERMS_URL = "https://www.rbnz.govt.nz/about-our-site/terms-of-use"
HIGHER_RATE_ACCESS_REQUEST_URL = (
    "https://www.rbnz.govt.nz/about-our-site/terms-of-use/allow-list-request"
)
DATA_FILE_INDEX_URL = (
    "https://www.rbnz.govt.nz/statistics/series/data-file-index-page"
)
B2_OCR_DATA_SOURCE_URL = (
    "https://rbnz.govt.nz/-/media/project/sites/rbnz/files/"
    "statistics/series/b/b2/hb2-daily-close.xlsx"
)
OCR_MEDIA_RELEASE_XML_FEED_URL = "https://www.rbnz.govt.nz/feeds/news"
TERMS_LAST_UPDATED = "2026-11-12"
MAX_REQUESTS_PER_HOUR = 120
REQUIRED_USER_AGENT_PATTERN = "RBNZ-Automated-Agent/<organisation>/<application>"
RBNZ_AUTOMATED_ACCESS_WRITTEN_PERMISSION_VERIFIED = False
# This is a *route-specific block after observed 403*, not a legal claim
# that all low-volume RBNZ automated HTTP traffic requires written approval.
RBNZ_BLOCK_REASON = "RBNZ_PREVIOUS_HTTP403_NO_AUTOMATED_RETRY_OR_BYPASS"


def inspect_rbnz_automated_access_policy_lab() -> dict:
    """No I/O; explicit distinction between current terms and prior 403."""
    return {
        "state": "LAB_RBNZ_PREVIOUS_403_ROUTE_ACCESS_SUSPENDED_NO_GO",
        "reason": RBNZ_BLOCK_REASON,
        "issuer_terms_url": TERMS_URL,
        "terms_last_updated_claim": TERMS_LAST_UPDATED,
        "issuer_higher_rate_request_url": HIGHER_RATE_ACCESS_REQUEST_URL,
        "official_b2_data_index_url": DATA_FILE_INDEX_URL,
        "official_b2_ocr_xlsx_url_reference_only": B2_OCR_DATA_SOURCE_URL,
        "official_ocr_media_release_xml_feed_url_reference_only":
            OCR_MEDIA_RELEASE_XML_FEED_URL,
        "issuer_ordinary_automation_permitted_under_conditions": True,
        "issuer_automation_hourly_request_limit": MAX_REQUESTS_PER_HOUR,
        "issuer_required_user_agent_format": REQUIRED_USER_AGENT_PATTERN,
        "issuer_written_approval_needed_for_ordinary_rate": False,
        "issuer_approval_required_for_higher_rate": True,
        "higher_rate_static_egress_ip_required": True,
        "issuer_403_may_prohibit_this_route_even_below_quota": True,
        "prior_403_route_suspended_here": True,
        "issuer_public_api_for_ocr_supported": False,
        "issuer_xml_feed_for_ocr_releases_documented": True,
        "official_b2_contains_ocr_and_third_party_market_data": True,
        "automated_access_granted_to_specific_prior_403_route": False,
        "current_atlasquant_endpoint_access_allowed": False,
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
    "TERMS_URL", "HIGHER_RATE_ACCESS_REQUEST_URL", "DATA_FILE_INDEX_URL",
    "B2_OCR_DATA_SOURCE_URL", "OCR_MEDIA_RELEASE_XML_FEED_URL",
    "RBNZ_BLOCK_REASON", "TERMS_LAST_UPDATED", "MAX_REQUESTS_PER_HOUR",
    "REQUIRED_USER_AGENT_PATTERN",
    "RBNZ_AUTOMATED_ACCESS_WRITTEN_PERMISSION_VERIFIED",
    "inspect_rbnz_automated_access_policy_lab",
)
