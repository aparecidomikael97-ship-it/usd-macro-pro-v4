"""ECB FM.B.U2.EUR.4F.KR.DFR.LEV SDMX CSV raw-byte receipt validator (LAB).

This key is the ECB deposit facility rate on **dates of changes** at
businessweek frequency, not every daily rate, refinancing rate, overnight
actual rate, forward guidance, or a Forex signal.

Consumes supplied raw CSV bytes and locally asserted TLS/clock receipt.
No HTTP, files, broker, account, orders or signals in this module.
A locally matching body/digest NEVER proves the time of first issuer
publication, independently authenticated source vintage, nor that EUR
and CAD policy rates are economically interchangeable.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import re
from typing import Any

SCHEMA = "ATLASQUANT_EUR_ECB_DFR_CHANGE_DATE_SDMX_CSV_LAB_V1"
URL = ("https://data-api.ecb.europa.eu/service/data/FM/"
       "B.U2.EUR.4F.KR.DFR.LEV?lastNObservations=3&format=csvdata")
KEY = "FM.B.U2.EUR.4F.KR.DFR.LEV"
MAX_BYTES = 48_000
RATE = re.compile(r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,7})?\Z")
DATE = re.compile(r"20\d\d-\d\d-\d\d\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
COLUMNS = (
    "KEY", "FREQ", "REF_AREA", "CURRENCY", "PROVIDER_FM",
    "INSTRUMENT_FM", "PROVIDER_FM_ID", "DATA_TYPE_FM",
    "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS", "OBS_CONF",
    "OBS_PRE_BREAK", "OBS_COM", "TIME_FORMAT", "BREAKS",
    "COLLECTION", "COMPILING_ORG", "DISS_ORG", "DOM_SER_IDS",
    "FM_CONTRACT_TIME", "FM_COUPON_RATE", "FM_IDENTIFIER",
    "FM_LOT_SIZE", "FM_MATURITY", "FM_OUTS_AMOUNT",
    "FM_PUT_CALL", "FM_STRIKE_PRICE", "PUBL_MU", "PUBL_PUBLIC",
    "UNIT_INDEX_BASE", "COMPILATION", "COVERAGE", "DECIMALS",
    "SOURCE_AGENCY", "SOURCE_PUB", "TITLE", "TITLE_COMPL",
    "UNIT", "UNIT_MULT",
)
IDENTITY = {
    "KEY": KEY, "FREQ": "B", "REF_AREA": "U2", "CURRENCY": "EUR",
    "PROVIDER_FM": "4F", "INSTRUMENT_FM": "KR",
    "PROVIDER_FM_ID": "DFR", "DATA_TYPE_FM": "LEV",
    "OBS_STATUS": "A", "UNIT": "PCPA", "UNIT_MULT": "0",
    "DECIMALS": "7", "COLLECTION": "E",
    "TITLE": "Deposit facility - date of changes (raw data) - Level",
}
RECEIPT_FIELDS = frozenset((
    "source_url", "final_url", "http_status", "content_type",
    "body_sha256", "started_at_utc", "finished_at_utc",
    "https_validation_claim", "redirects_followed",
))


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_EUR_ECB_SDMX_RECEIPT_BLOCKED",
        "reason": reason, "currency": "EUR",
        "measure": "ECB_DEPOSIT_FACILITY_RATE",
        "api_series_key": KEY, "issuer_url": URL,
        "raw_source_sha256_locally_matching": False,
        "transport_claim_structurally_consistent": False,
        "source_series_identity_consistent": False,
        "rate_change_event_count": 0,
        "last_effective_change_date_claim": None,
        "latest_deposit_rate_pct_claim": None,
        "capture_finished_at_utc_claim": None,
        "issuer_first_publication_time_independently_verified": False,
        "historical_point_in_time_vintage_authenticated": False,
        "issuer_rate_for_past_decision_authenticated": False,
        "all_eight_currencies_macro_complete": False,
        "fx28_bilateral_macro_authenticated": False,
        "central_bank_rate_measures_harmonized": False,
        "validated_directional_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "live_alert_allowed": False, "http_requests": 0,
        "files_written": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _time(raw: Any) -> datetime | None:
    if type(raw) is not str or len(raw) != 20 or not raw.endswith("Z"):
        return None
    try:
        t = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return t if t.year >= 2020 else None
    except ValueError:
        return None


def _decision(raw: Any) -> datetime | None:
    if not isinstance(raw, datetime) or raw.tzinfo is None:
        return None
    try:
        if raw.utcoffset() is None or raw.microsecond:
            return None
        return raw.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _rate(raw: Any) -> Decimal | None:
    if type(raw) is not str or RATE.fullmatch(raw) is None:
        return None
    try:
        v=Decimal(raw)
        return v if v.is_finite() and Decimal("-25") <= v <= Decimal("100") else None
    except InvalidOperation:
        return None


def inspect_ecb_dfr_change_date_csv_receipt_lab(
    *, original_csv: Any, receipt: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    out=_base("INVALID_RAW_CSV_RECEIPT_OR_DECISION")
    decision=_decision(decision_at_utc)
    if (type(original_csv) is not bytes
            or not 80 <= len(original_csv) <= MAX_BYTES
            or type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS
            or decision is None):
        return out
    if (receipt["source_url"] != URL or receipt["final_url"] != URL
            or type(receipt["http_status"]) is not int
            or receipt["http_status"] != 200
            or type(receipt["content_type"]) is not str
            or receipt["content_type"].split(";")[0].strip().lower() != "text/csv"
            or receipt["https_validation_claim"] is not True
            or receipt["redirects_followed"] is not False
            or type(receipt["body_sha256"]) is not str
            or HEX64.fullmatch(receipt["body_sha256"]) is None):
        out["reason"]="BAD_ECB_API_URL_CONTENT_TYPE_OR_TRANSPORT_CLAIM"
        return out
    begin=_time(receipt["started_at_utc"])
    end=_time(receipt["finished_at_utc"])
    if (begin is None or end is None or not begin <= end <= decision
            or end-begin > timedelta(seconds=30)):
        out["reason"]="ECBSOURCE_RECEIVED_AFTER_DECISION_OR_CLOCK_INVALID"
        return out
    if sha256(original_csv).hexdigest() != receipt["body_sha256"]:
        out["reason"]="ECBSOURCE_ORIGINAL_BODY_SHA256_MISMATCH"
        return out
    out["raw_source_sha256_locally_matching"]=True
    out["transport_claim_structurally_consistent"]=True
    try:
        txt=original_csv.decode("utf-8-sig")
        rows_reader=csv.DictReader(StringIO(txt,newline=""),strict=True)
        if rows_reader.fieldnames != list(COLUMNS):
            out["reason"]="ECBSOURCE_SDMX_CSV_HEADER_CHANGED"
            return out
        rows=list(rows_reader)
    except (UnicodeError,csv.Error,ValueError,TypeError):
        out["reason"]="ECBSOURCE_CSV_PARSE_FAILED"
        return out
    if not 1 <= len(rows) <= 3:
        out["reason"]="ECBSOURCE_CSV_EVENT_ROW_COUNT_INVALID"
        return out

    by_date={}
    for row in rows:
        if (type(row) is not dict or set(row) != set(COLUMNS)
                or any(type(v) is not str for v in row.values())
                or any(row.get(k) != v for k,v in IDENTITY.items())
                or type(row.get("TIME_PERIOD")) is not str
                or DATE.fullmatch(row["TIME_PERIOD"]) is None):
            out["reason"]="ECBSOURCE_SDMX_SERIES_IDENTITY_OR_UNIT_INVALID"
            return out
        try:
            day=date.fromisoformat(row["TIME_PERIOD"])
        except ValueError:
            out["reason"]="ECBSOURCE_EVENT_DATE_INVALID"
            return out
        value=_rate(row["OBS_VALUE"])
        # An effective date that is *today* is still a date-only claim
        # without independently verified intraday first-release time.
        if (value is None or day >= end.date() or day in by_date):
            out["reason"]="ECBSOURCE_EVENT_FUTURE_DUPLICATE_OR_BAD_RATE"
            return out
        by_date[day]=value
    if list(by_date) != sorted(by_date):
        out["reason"]="ECBSOURCE_EVENTS_NOT_MONOTONIC"
        return out
    last=max(by_date)
    out.update({
        "state":"LAB_EUR_ECB_SDMX_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO",
        "reason":"LOCAL_HTTPS_CAPTURE_AND_CSV_SCHEMA_NOT_HISTORIC_ISSUER_VINTAGE",
        "source_series_identity_consistent":True,
        "rate_change_event_count":len(by_date),
        "last_effective_change_date_claim":last.isoformat(),
        "latest_deposit_rate_pct_claim":str(by_date[last]),
        "capture_finished_at_utc_claim":end.isoformat(),
    })
    return out


__all__=("SCHEMA","URL","KEY","COLUMNS","MAX_BYTES",
         "inspect_ecb_dfr_change_date_csv_receipt_lab")
