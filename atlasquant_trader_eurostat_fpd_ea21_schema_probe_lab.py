"""Offline, metadata-only probe of a *supplied* Eurostat FPD JSON-stat shape.

The caller can fabricate the JSON and the claimed URL. Even a matching shape
has NO value as evidence of Eurostat HTTP delivery, vintages, or FX direction.
This probe never returns values/status, and never performs network requests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from atlasquant_trader_eurostat_fpd_ea21_metadata_gate_lab import (
    SEPTEMBER_FULL_DOC_GATE, inspect_eurostat_fpd_ea21_metadata_gate_lab,
)
from atlasquant_trader_eurostat_fpd_ea21_payload_envelope_lab import (
    EXPECTED_HOST, EXPECTED_PATH, MAX_BYTES, _blocked, _unique, _utc,
)

SCHEMA = "ATLASQUANT_TRADER_EUROSTAT_FPD_EA21_SUPPLIED_SCHEMA_PROBE_LAB_V1"
BASE_QUERY_KEYS = frozenset((
    "format", "lang", "freq", "unit", "release", "geo", "time",
))
CLASSIFICATION_CANDIDATES = frozenset(("coicop", "coicop18"))
CODE_PATTERN = re.compile(r"[A-Za-z0-9_\-.]{1,32}\Z")
DIM_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")


def _initial(reason: str) -> dict[str, Any]:
    out = _blocked(reason)
    out.update({
        "schema": SCHEMA,
        "supplied_dimension_ids_untrusted": [],
        "supplied_category_codes_untrusted": {},
        "supplied_classification_dimension_candidate": None,
        "claimed_url_classification_field": None,
        "dimension_codes_confirmed_from_official_api": False,
        "real_hicp_value_inspected_or_returned": False,
        "real_release_type_confirmed": False,
        "is_comparable_eurusd_inflation_observation": False,
    })
    return out


def _claimed_url(value: Any) -> tuple[dict[str, str], str] | None:
    if not isinstance(value, str) or len(value) > 1200:
        return None
    try:
        p = urlsplit(value)
        if (p.scheme != "https" or p.hostname != EXPECTED_HOST
                or p.username is not None or p.password is not None
                or p.port is not None or p.path != EXPECTED_PATH
                or p.fragment or not p.query):
            return None
        pairs = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True)
        names = [k for k, _ in pairs]
        chosen = CLASSIFICATION_CANDIDATES.intersection(names)
        if (len(pairs) != 8 or len(set(names)) != 8
                or len(chosen) != 1
                or set(names) != BASE_QUERY_KEYS.union(chosen)):
            return None
        q = dict(pairs)
        if (q["format"] != "JSON" or q["lang"] != "EN"
                or q["freq"] != "M" or q["geo"] != "EA21"
                or q["time"] != "2026-09"
                or not all(CODE_PATTERN.fullmatch(q[k])
                           for k in ("unit", "release", next(iter(chosen))))):
            return None
        return q, next(iter(chosen))
    except (TypeError, ValueError):
        return None


def inspect_supplied_eurostat_fpd_ea21_schema_probe_lab(
    raw: Any, *, request_url_claim: Any, observed_at_utc: Any, as_of_utc: Any,
    metadata_casebook_raw: Any, eurusd_casebook_raw: Any,
) -> dict[str, Any]:
    """Check one bounded claimed shape, leaving all economic signals blocked."""
    out = _initial("INVALID_CLAIMED_SCHEMA_OR_CLOCK_OR_DOCUMENTARY_CONTEXT")
    observed, now = _utc(observed_at_utc), _utc(as_of_utc)
    claim = _claimed_url(request_url_claim)
    if (observed is None or now is None or observed > now
            or observed < SEPTEMBER_FULL_DOC_GATE
            or not isinstance(raw, bytes) or not 100 <= len(raw) <= MAX_BYTES
            or claim is None):
        return out
    q, classification = claim
    meta = inspect_eurostat_fpd_ea21_metadata_gate_lab(
        metadata_casebook_raw, eurusd_casebook_raw=eurusd_casebook_raw,
        as_of_utc=now,
    )
    if (meta["state"] != "LAB_EUROSTAT_EA21_FPD_METADATA_ONLY_NOT_API_PAYLOAD"
            or not meta["sep2026_full_dataset_metadata_reference_visible_asof"]):
        return out
    try:
        obj = json.loads(
            raw.decode("utf-8", "strict"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        ids, sizes, dims = obj["id"], obj["size"], obj["dimension"]
        if (obj["class"] != "dataset" or obj["version"] != "2.0"
                or obj["source"] != "ESTAT"
                or not isinstance(ids, list) or len(ids) != 6
                or any(not isinstance(k, str) or not DIM_PATTERN.fullmatch(k)
                       for k in ids) or len(set(ids)) != 6
                or set(ids) != {"freq", "unit", classification,
                                "release", "geo", "time"}
                or not isinstance(sizes, list) or len(sizes) != len(ids)
                or any(type(n) is not int or n != 1 for n in sizes)
                or not isinstance(dims, dict) or set(dims) != set(ids)
                or not isinstance(obj["value"], dict)
                or set(obj["value"]).difference({"0"})):
            return out
        codes: dict[str, str] = {}
        for k in ids:
            index = dims[k]["category"]["index"]
            if (not isinstance(index, dict) or set(index) != {q[k]}
                    or type(index[q[k]]) is not int or index[q[k]] != 0):
                return out
            codes[k] = q[k]
        update = datetime.fromisoformat(obj["updated"].replace("Z", "+00:00"))
        if (update.tzinfo is None or update.utcoffset() is None
                or update.astimezone(timezone.utc) > observed):
            return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError,
            OverflowError, RecursionError):
        return out
    out.update({
        "state": "LAB_SUPPLIED_SCHEMA_PROBE_QUARANTINED_NOT_VERIFIED",
        "reason": "DOCUMENTED_FAMILY_DOES_NOT_PROVE_ACTUAL_FPD_DIMENSION_CODES_OR_HTTP_ORIGIN",
        "submitted_payload_sha256": sha256(raw).hexdigest(),
        "submitted_payload_byte_count": len(raw),
        "submitted_jsonstat_dataset_id": "prc_hicp_fpd",
        "submitted_dataset_updated_at_utc": update.astimezone(timezone.utc).isoformat(),
        "submitted_capture_clock_utc": observed.isoformat(),
        "supplied_dimension_ids_untrusted": ids,
        "supplied_category_codes_untrusted": codes,
        "supplied_classification_dimension_candidate": classification,
        "claimed_url_classification_field": classification,
        "jsonstat_structure_checked": True,
    })
    return out


__all__ = ["SCHEMA", "inspect_supplied_eurostat_fpd_ea21_schema_probe_lab"]
