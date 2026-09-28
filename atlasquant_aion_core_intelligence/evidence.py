"""Strict evidence ingress over the existing AION truth/freshness assessor."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re

from atlasquant_aion_observability import redact_text, sanitize_metadata
from atlasquant_aion_truth import assess_truth


class Origin(str, Enum):
    USER_APPROVED = "USER_APPROVED"
    SYSTEM_OBSERVED = "SYSTEM_OBSERVED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")
    return utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def digest(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def safe_text(value: str, limit: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("non-empty bounded text required")
    # Extend the shared redactor for multiline private keys and URL passwords.
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
                  "[REDACTED]", value, flags=re.S)
    text = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
    return redact_text(text)


@dataclass(frozen=True)
class Evidence:
    claim: str
    value: str
    origin: Origin = Origin.UNKNOWN
    source: str = "UNKNOWN"
    source_ref: str = "UNKNOWN"
    observed_at: str | None = None
    ttl_seconds: int | None = None
    time_sensitive: bool = True
    uncertainty: str = "Source supplied by caller; not independently authenticated."

    def __post_init__(self):
        if not isinstance(self.origin, Origin) or type(self.time_sensitive) is not bool:
            raise ValueError("invalid evidence classification")
        # Approval records are handled by the approval gate, never by research.
        if self.origin == Origin.USER_APPROVED:
            raise ValueError("human approval is not factual evidence")
        for name in ("claim", "value", "source", "source_ref", "uncertainty"):
            object.__setattr__(self, name, safe_text(getattr(self, name)))
        if self.observed_at is not None:
            timestamp(self.observed_at)
        if self.ttl_seconds is not None and (type(self.ttl_seconds) is not int or self.ttl_seconds < 1):
            raise ValueError("TTL must be a positive exact integer")

    def row(self, now: datetime) -> dict:
        current = utc(now)
        missing = {"UNKNOWN", "UNAVAILABLE", "NONE", "N/A", "[REDACTED]"}
        sourced = all(x.strip().upper() not in missing and "[REDACTED]" not in x
                      for x in (self.source, self.source_ref))
        future = self.observed_at is not None and timestamp(self.observed_at) > current
        truth = {Origin.SYSTEM_OBSERVED: "CONFIRMED", Origin.INFERRED: "INFERENCE",
                 Origin.UNKNOWN: "UNKNOWN"}[self.origin]
        if not sourced or future:
            truth = "UNKNOWN"
        return {
            "claim": self.claim, "value": self.value, "truth_state": truth,
            "source": self.source if sourced else "", "source_ref": self.source_ref,
            "timestamp": self.observed_at, "ttl_seconds": self.ttl_seconds,
            "time_sensitive": self.time_sensitive, "source_tier": "UNKNOWN",
        }

    def as_dict(self) -> dict:
        return {**asdict(self), "origin": self.origin.value}


def assess(records: tuple[Evidence, ...] | list[Evidence], now: datetime) -> dict:
    if len(records) > 200 or any(not isinstance(x, Evidence) for x in records):
        raise ValueError("bounded typed evidence required")
    return assess_truth([x.row(now) for x in records], now=utc(now))
