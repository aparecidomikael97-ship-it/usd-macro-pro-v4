"""Pure LAB audit of timezone hypotheses for EODHD economic-event timestamps.

Only accepts caller-provided, source-attributed comparison samples. Performs
NO network access, no provider calls, no file writes, no scheduler, no Worker,
no secret lookup, and NO automatic timezone attestation. Official schedules
are planned times, not proof that a release actually occurred.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SCHEMA = "ATLASQUANT_EODHD_CLOCK_AUDIT_LAB_V1"
BRT = ZoneInfo("America/Sao_Paulo")
OFFICIAL_HOSTS = (
    "bls.gov", "bea.gov", "ibge.gov.br", "bcb.gov.br",
    "federalreserve.gov",
)
MIN_SAMPLES = 3
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{3,100}$")
MAX_REFERENCE_AGE = timedelta(days=7)
MAX_CLOCK_DIFFERENCE = timedelta(minutes=5)


def _aware(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 45:
        return None
    try:
        stamp = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo else None


def _official_host(raw: Any) -> str:
    if not isinstance(raw, str) or len(raw) > 300:
        return ""
    try:
        url = urlsplit(raw)
        host = (url.hostname or "").lower()
        if (url.scheme != "https" or url.username or url.password or
                url.port not in (None, 443)):
            return ""
    except ValueError:
        return ""
    if any(host == known or host.endswith("." + known)
           for known in OFFICIAL_HOSTS):
        return host
    return ""


def _provider_naive(raw: Any) -> datetime | None:
    # Match only the documented no-offset format; no silent timezone coercion.
    if not isinstance(raw, str) or len(raw) != 19:
        return None
    try:
        stamp = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return stamp if stamp.strftime("%Y-%m-%d %H:%M:%S") == raw else None


def audit_timezone_hypotheses(
    samples: Sequence[Mapping[str, Any]] | None, *,
    at: datetime, minimum: int = MIN_SAMPLES
) -> dict[str, Any]:
    """Compare hypothetical UTC/BRT interpretations against official references.

    Results are CANDIDATES FOR HUMAN REVIEW, not evidence sufficient to toggle
    a production source flag or infer that an indicator was just published.
    """
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Timezone-aware audit instant required")
    if isinstance(minimum, bool) or not isinstance(minimum, int) or not 3 <= minimum <= 20:
        raise ValueError("Three to twenty independent samples required")
    now = at.astimezone(timezone.utc)
    rows = []
    seen: set[str] = set()
    if not isinstance(samples, (list, tuple)):
        samples = []
    if len(samples) > 100:
        rows.append({"state": "INVALID_SAMPLE"})
    for item in samples[:100]:
        if not isinstance(item, Mapping):
            rows.append({"state": "INVALID_SAMPLE"})
            continue
        event_id = item.get("event_id")
        source = _official_host(item.get("official_source_url"))
        source_checked = _aware(item.get("source_checked_at_utc"))
        official_release = _aware(item.get("official_release_utc"))
        provider_naive = _provider_naive(item.get("eodhd_raw_date"))
        reference_type = item.get("reference_type")
        if (not isinstance(event_id, str) or not EVENT_ID_RE.fullmatch(event_id) or
                event_id in seen or not source or source_checked is None or
                official_release is None or provider_naive is None or
                reference_type not in ("OFFICIAL_SCHEDULE", "OFFICIAL_PUBLICATION")):
            rows.append({"state": "INVALID_SAMPLE"})
            continue
        seen.add(event_id)
        age = now - source_checked
        if age < -timedelta(minutes=5) or age > MAX_REFERENCE_AGE:
            rows.append({"state": "STALE_OR_FUTURE_REFERENCE"})
            continue
        utc_candidate = provider_naive.replace(tzinfo=timezone.utc)
        brt_candidate = provider_naive.replace(tzinfo=BRT).astimezone(timezone.utc)
        utc_match = abs(utc_candidate - official_release) <= MAX_CLOCK_DIFFERENCE
        brt_match = abs(brt_candidate - official_release) <= MAX_CLOCK_DIFFERENCE
        if utc_match and not brt_match:
            match = "UTC_CANDIDATE"
        elif brt_match and not utc_match:
            match = "BRT_CANDIDATE"
        elif utc_match and brt_match:
            match = "AMBIGUOUS"
        else:
            match = "CONFLICT"
        rows.append({
            "state": match, "event_id": event_id,
            "official_host": source, "official_day_utc": official_release.date().isoformat(),
            "reference_type": reference_type,
        })
    verified = [r for r in rows
                if r["state"] in ("UTC_CANDIDATE", "BRT_CANDIDATE")]
    hosts = {r["official_host"] for r in verified}
    days = {r["official_day_utc"] for r in verified}
    states = {r["state"] for r in verified}
    if any(r["state"] in ("INVALID_SAMPLE", "STALE_OR_FUTURE_REFERENCE", "CONFLICT",
                         "AMBIGUOUS") for r in rows):
        state = "REJECTED_OR_CONFLICTING_EVIDENCE"
    elif len(verified) < minimum or len(hosts) < 2 or len(days) < 2:
        state = "INSUFFICIENT_INDEPENDENT_SAMPLES"
    elif len(states) != 1:
        state = "INCONSISTENT_TIMEZONE_HYPOTHESES"
    else:
        state = "UTC_CANDIDATE_REVIEW" if states == {"UTC_CANDIDATE"} else "BRT_CANDIDATE_REVIEW"
    return {
        "schema": SCHEMA, "state": state, "sample_count": len(rows),
        "matched_count": len(verified), "source_hosts_count": len(hosts),
        "distinct_reference_days": len(days),
        "rows": rows, "provider_request_count": 0,
        "timezone_attested": False, "auto_config_allowed": False,
        "new_economic_release_confirmed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "why_not": "Referências fornecidas precisam de verificação independente; "
                   "correspondência de agenda não comprova divulgação real.",
    }


__all__ = ["SCHEMA", "OFFICIAL_HOSTS", "audit_timezone_hypotheses"]
