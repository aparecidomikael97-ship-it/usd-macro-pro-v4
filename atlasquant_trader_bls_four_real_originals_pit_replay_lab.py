"""Read-only PIT visibility of four ACTUAL archived BLS originals (September/October).

Use the user-preserved nested GitHub Actions ZIP, never download or fabricate
source data. These are POST-release captures and never constitute forecasts,
pre-event consensus, independently attested first-seen or broker evidence.
The four SHA-256 pins are published in earlier AtlasQuant research PRs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile, BadZipFile
import json

SCHEMA = "ATLASQUANT_BLS_FOUR_REAL_ORIGINALS_PIT_VISIBILITY_LAB_V1"
MANIFEST_SCHEMA = "ATLASQUANT_BLS_4_DOCUMENT_ORIGINALS_PRESERVATION_COPY_V1"
# Independent literals: trusting hashes copied from the same untrusted manifest
# would make tampered contents appear validated. None prove publisher first-seen.
ARCHIVES = {
    "sep": ("arquivos_actions_originais/atlasquant_bls_set2026_originais_actions.zip",
            "867c884d107cb53ebbea96d3da5f929c167701cd7a1415f429400b2b1eebeb3e"),
    "oct_cpi": ("arquivos_actions_originais/atlasquant_bls_out2026_cpi_original_actions.zip",
                "bd6d076685576816745332107ed2a7dd9879d7364b1bb3ae577fc1c901d1a58f"),
    "oct_ppi": ("arquivos_actions_originais/atlasquant_bls_out2026_ppi_original_actions.zip",
                "fcc9847c80ff9508b093f78696cfd1c01783ceebb3ec225912f4d735150d9c08"),
}
# id: (archive, HTML path, receipt path, HTML SHA, receipt SHA,
#      capture end UTC, scheduled BLS release UTC claim, original URL, reference period)
PINS = {
    "US_CPI_SEP2026": (
        "sep", "US_BLS_SEP2026_CPI_PPI_20261116T022027Z_fbee392360ea/cpi_original.html",
        "US_BLS_SEP2026_CPI_PPI_20261116T022027Z_fbee392360ea/receipt.json",
        "b9f981390c08f4a530d839495fce582124015b979bac0398bfcc35ffde0544e4",
        "247fe38075fc9e65d4c6aab2b8bb45699a949866eae54f59b03eccef85aaeaaf",
        "2026-11-16T02:20:27+00:00", "2026-10-14T12:30:00+00:00",
        "https://www.bls.gov/news.release/archives/cpi_10142026.htm", "2026-09"),
    "US_PPI_SEP2026": (
        "sep", "US_BLS_SEP2026_CPI_PPI_20261116T022027Z_fbee392360ea/ppi_original.html",
        "US_BLS_SEP2026_CPI_PPI_20261116T022027Z_fbee392360ea/receipt.json",
        "3ea265ba342320909d625ebbe4bfc55f4a988346593d751d0b02a23c606524c5",
        "247fe38075fc9e65d4c6aab2b8bb45699a949866eae54f59b03eccef85aaeaaf",
        "2026-11-16T02:20:27+00:00", "2026-10-15T12:30:00+00:00",
        "https://www.bls.gov/news.release/archives/ppi_10152026.htm", "2026-09"),
    "US_CPI_OCT2026": (
        "oct_cpi", "US_BLS_CPI_OCT2026_20261116T011545Z_ee0bffd2cfb1/original.html",
        "US_BLS_CPI_OCT2026_20261116T011545Z_ee0bffd2cfb1/receipt.json",
        "ee0bffd2cfb13f9faf79b5b23e5b74d87d67f61888dfd34346f81dee9182a320",
        "e0956565021ee7b3394fd1d44e32e11156c98fcd0d6ef5bf94cc7c1bc54eefd0",
        "2026-11-16T01:15:45+00:00", "2026-11-10T13:30:00+00:00",
        "https://www.bls.gov/news.release/archives/cpi_11102026.htm", "2026-10"),
    "US_PPI_OCT2026": (
        "oct_ppi", "US_BLS_PPI_OCT2026_20261114T160053Z_5115165ee0d2/original.html",
        "US_BLS_PPI_OCT2026_20261114T160053Z_5115165ee0d2/receipt.json",
        "5115165ee0d2c8b006fc24d01cb913df5d8e7bbe169b11ee6193df628387385a",
        "d2708919e7784333a6d06a52b7e8d1538a979fdb7057a18224fac68af20ddfda",
        "2026-11-14T16:00:53+00:00", "2026-11-13T13:30:00+00:00",
        "https://www.bls.gov/news.release/archives/ppi_11132026.htm", "2026-10"),
}


def _blocked(reason: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "state": "LAB_BLS_REAL_ORIGINALS_BLOCKED_HARD_NO_GO",
            "reason": reason, "event_denominator": 4,
            "visible_postrelease_originals": 0, "not_yet_visible_originals": 4,
            "events": [], "forecast_count_verified": 0,
            "independent_out_of_sample_prediction_trials": 0,
            "consensus_pre_event_authenticated": False,
            "publisher_first_seen_independently_attested": False,
            "broker_prices_authenticated": False,
            "accuracy": None, "usd_bias": None,
            "operational_bias": "AGUARDAR", "trade_authorized": False,
            "publishable": False, "http_requests": 0, "file_writes": 0,
            "mt5_calls": 0, "changes_to_fx28_672_slots": False}


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _receipt_record(receipt: dict, event_id: str) -> dict | None:
    if event_id.endswith("SEP2026"):
        src = receipt.get("sources")
        if type(src) is not dict:
            return None
        return src.get("CPI" if "_CPI_" in event_id else "PPI")
    return receipt


def inspect_four_real_bls_originals_lab(*, package_path: Any,
                                        as_of_utc: Any) -> dict[str, Any]:
    """At a cutoff, reveal only locally archived bytes already captured.

    The cutoff is a caller claim. Even positive results remain documentary;
    there are no ex-ante forecast, first-seen, consensus or FX claims here.
    """
    now = _utc(as_of_utc)
    result = _blocked("INVALID_CUTOFF_OR_MISSING_PRESERVED_ARCHIVE")
    if now is None or not isinstance(package_path, (str, Path)):
        return result
    try:
        path = Path(package_path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            return result
        with ZipFile(path) as outer:
            outer_names = set(outer.namelist())
            expected = {"manifesto_sha256.json", "LEIA_ME_PTBR.md", "verificar_pacote.py"}
            expected.update(a[0] for a in ARCHIVES.values())
            if outer_names != expected:
                return _blocked("UNKNOWN_OR_MISSING_ARCHIVE_MEMBER")
            if outer.getinfo("manifesto_sha256.json").file_size > 20_000:
                return _blocked("MANIFEST_SIZE_INVALID")
            m = json.loads(outer.read("manifesto_sha256.json").decode("utf-8"))
            if (type(m) is not dict or m.get("schema") != MANIFEST_SCHEMA
                    or m.get("independent_publisher_first_seen_attested") is not False
                    or m.get("price_or_forex_forecast_verified") is not False
                    or type(m.get("economic_originals")) is not dict
                    or len(m["economic_originals"]) != 4
                    or type(m.get("actions_archives")) is not list
                    or len(m["actions_archives"]) != 3):
                return _blocked("MANIFEST_SCHEMA_OR_AUTHORITY_INVALID")
            per_archive = {x["zip_path"]: x for x in m["actions_archives"]}
            if set(per_archive) != {x[0] for x in ARCHIVES.values()}:
                return _blocked("UNKNOWN_OR_MISSING_ACTIONS_ARCHIVE")
            for key,(zip_path,zip_sha) in ARCHIVES.items():
                x = per_archive[zip_path]
                if x.get("zip_sha256") != zip_sha:
                    return _blocked("MANIFEST_ARCHIVE_HASH_CHANGED")
            visible = []
            hidden = []
            for event_id, pin in PINS.items():
                archive_id, body_name, receipt_name, body_sha, receipt_sha, when, release, url, period = pin
                capture = datetime.fromisoformat(when)
                scheduled = datetime.fromisoformat(release)
                if capture <= scheduled:
                    return _blocked("RECEIPT_NOT_POST_EVENT_OR_RELEASE_CLOCK_INVALID")
                if now < capture:
                    hidden.append({"event_root": event_id, "reference_period": period,
                                   "scheduled_release_utc_calendar_claim": release,
                                   "state": "POST_RELEASE_ORIGINAL_NOT_VISIBLE_AT_CUTOFF",
                                   "capture_at_utc": None, "original_sha256": None,
                                   "document_original_verified": False})
                    continue
                zip_path, zip_sha = ARCHIVES[archive_id]
                info = outer.getinfo(zip_path)
                if info.file_size > 350_000:
                    return _blocked("NESTED_ZIP_SIZE_INVALID")
                zbytes = outer.read(zip_path)
                if _sha(zbytes) != zip_sha:
                    return _blocked("ARCHIVE_ZIP_BYTES_CHANGED")
                with ZipFile(BytesIO(zbytes)) as nested:
                    if (body_name not in nested.namelist() or receipt_name not in nested.namelist()
                            or nested.getinfo(body_name).file_size > 2_000_000
                            or nested.getinfo(receipt_name).file_size > 8_192):
                        return _blocked("SOURCE_ARCHIVE_MEMBERS_MISSING_OR_OVERSIZED")
                    body = nested.read(body_name)
                    raw_receipt = nested.read(receipt_name)
                if _sha(body) != body_sha or _sha(raw_receipt) != receipt_sha:
                    return _blocked("SOURCE_HTML_OR_RECEIPT_BYTES_CHANGED")
                receipt = json.loads(raw_receipt.decode("utf-8"))
                item = _receipt_record(receipt,event_id)
                if type(item) is not dict:
                    return _blocked("SOURCE_RECEIPT_ROW_INVALID")
                received_sha = item.get("raw_sha256",item.get("body_sha256"))
                received_bytes = item.get("raw_bytes",item.get("body_bytes"))
                received_url = item.get("url",item.get("source_url"))
                received_finished = item.get("finished_utc",item.get("finished_at_utc"))
                received_status = item.get("http_status",item.get("status_code"))
                if (received_sha != body_sha or received_bytes != len(body)
                        or received_url != url or received_status != 200
                        or _utc(datetime.fromisoformat(received_finished.replace("Z","+00:00"))) != capture):
                    return _blocked("RECEIPT_SOURCE_IDENTITY_OR_CAPTURE_INVALID")
                # Cross-check manifest by the documented reference-period key,
                # never treat the manifest as independent proof of itself.
                doc_key = period+"_"+("CPI" if "_CPI_" in event_id else "PPI")
                meta = m["economic_originals"].get(doc_key)
                if (type(meta) is not dict
                        or meta.get("html_sha256") != body_sha
                        or meta.get("html_bytes") != len(body)
                        or meta.get("original_archive") != zip_path
                        or meta.get("original_zip_inside_path") != body_name
                        or meta.get("source_url") != url
                        or meta.get("captured_after_release") is not True):
                    return _blocked("MANIFEST_DOCUMENT_IDENTITY_CHANGED")
                visible.append({"event_root": event_id, "reference_period": period,
                                "scheduled_release_utc_calendar_claim": release,
                                "state": "POST_RELEASE_ARCHIVED_ORIGINAL_REPLAYED_NO_FORECAST",
                                "capture_at_utc": when, "original_sha256": body_sha,
                                "document_original_verified": True,
                                "source_first_seen_independently_attested": False,
                                "numeric_consensus_verified_pre_event": False,
                                "trade_authorized": False})
            # Caller-visible event order is invariant, never selected by outcome.
            indexed = {e["event_root"]: e for e in visible+hidden}
            result.update({"state": "LAB_BLS_FOUR_REAL_POSTRELEASE_ORIGINALS_PIT_DOCUMENTARY_NO_GO",
                           "reason": "CAPTURE_TIME_LOCAL_CLAIM_ONLY_NOT_PUBLISHER_FIRST_SEEN",
                           "event_denominator": 4,
                           "visible_postrelease_originals": len(visible),
                           "not_yet_visible_originals": len(hidden),
                           "events": [indexed[k] for k in PINS]})
            return result
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            BadZipFile, json.JSONDecodeError, RuntimeError, OverflowError,
            AttributeError):
        return _blocked("PRESERVED_ARCHIVE_OR_RECEIPT_CANNOT_BE_REPLAYED")


__all__ = ["SCHEMA", "inspect_four_real_bls_originals_lab"]
