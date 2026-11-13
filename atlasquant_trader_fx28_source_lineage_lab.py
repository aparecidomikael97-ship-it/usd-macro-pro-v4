"""Local source-byte SHA lineage for FX28; documentary, NOT PIT, NO-GO.

The real eight-issuer archive verifier already SHA-checks original files
AND parses issuer-specific economic meaning before it produces its report.
This module consumes ONLY those accepted per-currency records and binds
their byte digests + local UTC capture CLAIMS to a pair-specific digest.

The same validated BLS October 2026 PPI SHA may be bound as ONE external
US catalyst, at most to seven USD-leg pairs. It is not seven independent
economic events and not a signed currency impact. A pair without two
accepted policy sources has NO complete two-policy digest, even if PPI
is locally present.

No network, file I/O, rates, trade orders, forecasts, broker data,
calibrated probabilities or independent publisher timestamp proof.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_FX28_LOCAL_SOURCE_LINEAGE_LAB_V1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_STAMP = re.compile(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_ACCEPTED_STATUS = "LOCALLY_CHECKED_ONLY_NOT_SOURCE_ATTESTATION"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def _time(value: Any) -> datetime | None:
    if type(value) is not str or _STAMP.fullmatch(value) is None:
        return None
    try:
        got = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        if got.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
            return None
        return got.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def extract_checked_policy_source_lineage_lab(
    *, archive_report: Any, inspected_at_utc: Any,
) -> dict[str, dict[str, str]]:
    """Strict SUBSET of issuer-originals validated by existing replay.

    Invalid/missing SHA or future/incoherent capture => omitted; caller
    must show omissions and never infer that bytes had been attested.
    """
    at = _utc(inspected_at_utc)
    if (at is None or type(archive_report) is not dict
            or archive_report.get("state") not in (
                "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO",
                "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO")
            or archive_report.get("trade_authorized") is not False
            or archive_report.get("publishable") is not False
            or archive_report.get("source_current_issuer_identity_independently_verified")
                is not False
            or archive_report.get("true_first_seen_time_independently_attested")
                is not False):
        return {}
    status = archive_report.get("currency_archive_status")
    checked = archive_report.get("currencies_locally_checked")
    if (type(status) is not dict or type(checked) is not list
            or len(checked) != len(set(checked))
            or any(c not in CURRENCIES for c in checked)):
        return {}
    ledger = {}
    for currency in sorted(checked):
        entry = status.get(currency)
        if type(entry) is not dict or entry.get("status") != _ACCEPTED_STATUS:
            continue
        digest, stamp = (
            entry.get("original_file_sha256"),
            entry.get("selected_local_capture_utc_claim"),
        )
        captured = _time(stamp)
        if (type(digest) is not str or _SHA.fullmatch(digest) is None
                or digest == "0" * 64 or captured is None or captured > at
                or type(entry.get("original_file_bytes")) is not int
                or entry["original_file_bytes"] <= 0):
            continue
        ledger[currency] = {
            "source_original_sha256_local_claim": digest,
            "selected_capture_utc_local_claim": stamp,
            "origin_pit_authenticated": "false",
        }
    return ledger


def build_pair_source_lineage_lab(
    *, pair: Any, policy_ledger: Any, ppi_original_sha256: Any = None,
) -> dict[str, Any]:
    """Deterministic 2-policy + optional ONE US-PPI original digest.

    Empty policy ledger does not get magically promoted to a complete
    manifest. No actual forecast model has used this hash yet.
    """
    result = {
        "schema": SCHEMA,
        "pair": pair if type(pair) is str and pair in OFFICIAL_PAIRS else None,
        "base_policy_original_sha256_local_claim": None,
        "quote_policy_original_sha256_local_claim": None,
        "both_policy_original_hashes_available": False,
        "direct_usd_ppi_context_sha256_local_claim": None,
        "ppi_is_one_shared_US_event_across_USD_pairs": True,
        "complete_policy_pair_source_digest_local_only": None,
        "source_document_bundle_sha256_local_only": None,
        "source_bundle_contains_predictive_signal": False,
        "issuer_origin_and_first_seen_independently_authenticated": False,
        "model_inputs_point_in_time_authenticated": False,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "calibrated_probability": None,
        "research_only": True,
    }
    if result["pair"] is None or type(policy_ledger) is not dict:
        return result
    base, quote = split_pair(pair)
    docs = []
    for currency in (base, quote):
        row = policy_ledger.get(currency)
        if type(row) is not dict:
            return result
        sha = row.get("source_original_sha256_local_claim")
        stamp = row.get("selected_capture_utc_local_claim")
        if (type(sha) is not str or _SHA.fullmatch(sha) is None
                or sha == "0" * 64 or _time(stamp) is None
                or row.get("origin_pit_authenticated") != "false"):
            return result
        docs.append({"currency":currency, "body_sha256":sha,
                     "selected_capture_utc_local_claim":stamp})
    result["base_policy_original_sha256_local_claim"] = docs[0]["body_sha256"]
    result["quote_policy_original_sha256_local_claim"] = docs[1]["body_sha256"]
    result["both_policy_original_hashes_available"] = True
    policy_sha = sha256(_canon({
        "kind":"ATLASQUANT_PAIR_POLICY_DOCUMENTS_V1",
        "pair":pair, "policy_originals":docs,
    })).hexdigest()
    result["complete_policy_pair_source_digest_local_only"] = policy_sha
    ppi = (ppi_original_sha256
           if "USD" in (base, quote)
           and type(ppi_original_sha256) is str
           and _SHA.fullmatch(ppi_original_sha256) is not None
           else None)
    result["direct_usd_ppi_context_sha256_local_claim"] = ppi
    result["source_document_bundle_sha256_local_only"] = sha256(_canon({
        "kind":"ATLASQUANT_PAIR_SOURCE_DOCUMENTS_V1",
        "pair":pair, "policy_document_digest":policy_sha,
        "single_shared_us_oct2026_ppi_document_sha256":ppi,
        "post_release_ppi_not_predictive":True,
    })).hexdigest()
    return result


__all__ = ("SCHEMA", "extract_checked_policy_source_lineage_lab",
           "build_pair_source_lineage_lab")
