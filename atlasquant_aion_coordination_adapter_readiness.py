"""Read-only readiness diagnostic for a future shared coordination adapter.

The descriptor and the probe receipt are data. This module does not connect a
provider, run a probe, persist a checkpoint, start the Global Worker, change a
feature flag, or install a second kill switch. Lease ownership and fencing
remain in the current Global Worker.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_COORDINATION_ADAPTER_READINESS_V1"
RECEIPT_SCHEMA = "ATLASQUANT_AION_COORDINATION_ADAPTER_PROBE_RECEIPT_V1"
RECEIPT_VERSION = 1
MAX_PROBE_TTL_SECONDS = 900

NOT_CONFIGURED = "NOT_CONFIGURED"
DESCRIPTOR_INVALID = "DESCRIPTOR_INVALID"
DESCRIPTOR_READY = "DESCRIPTOR_READY"
PROBE_REQUIRED = "PROBE_REQUIRED"
PROBE_EVIDENCE_READY = "PROBE_EVIDENCE_READY"
BLOCKED = "BLOCKED"

_DESCRIPTOR_KEYS = (
    "adapter_id",
    "adapter_version",
    "provider",
    "backend_kind",
    "paid_service",
    "shared_across_instances",
    "atomic_compare_and_swap",
    "monotonic_versions",
    "atomic_monotonic_fencing_token",
    "ttl_expiry",
    "atomic_delete",
    "durable_outside_browser",
)
_REQUIRED_CAPABILITIES = (
    "shared_across_instances",
    "atomic_compare_and_swap",
    "monotonic_versions",
    "atomic_monotonic_fencing_token",
    "ttl_expiry",
    "atomic_delete",
    "durable_outside_browser",
)
_ABSENT_BACKENDS = frozenset({
    "",
    "none",
    "unconfigured",
    "unavailable",
    "browser",
    "memory",
    "local",
})
_SECRET_EXACT = frozenset({
    "secret",
    "token",
    "credential",
    "credentials",
    "password",
    "api_key",
    "apikey",
    "api_token",
    "access_token",
    "auth_token",
})
_RECEIPT_KEYS = (
    "schema",
    "receipt_version",
    "adapter_identity_digest",
    "scope_digest",
    "issued_at",
    "expires_at",
    "evidence_digest",
    "observed_capabilities",
    "mutation_count",
    "read_only_validation",
    "receipt_digest",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or text != value.strip() or len(text) > limit:
        return None
    if any(ord(char) < 32 for char in text):
        return None
    return text


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _secret_key(name: str) -> bool:
    token = name.casefold().replace("-", "_")
    if token in _SECRET_EXACT:
        return True
    parts = set(token.split("_"))
    if parts & {"secret", "credential", "credentials", "password"}:
        return True
    return "api" in parts and bool(parts & {"key", "token"})


def _closed(document: Mapping[str, Any], allowed: tuple[str, ...], label: str) -> str | None:
    unknown = sorted(set(document) - set(allowed))
    if unknown:
        return f"{label}_UNKNOWN_FIELD:{unknown[0]}"
    missing = [name for name in allowed if name not in document]
    if missing:
        return f"{label}_MISSING:{missing[0]}"
    return None


def adapter_identity_digest(descriptor: Mapping[str, Any]) -> str:
    """Digest the closed descriptor. The digest is not a live provider identity."""
    payload = {key: descriptor.get(key) for key in _DESCRIPTOR_KEYS}
    return _digest(payload)


def _capability_view(descriptor: Mapping[str, Any]) -> dict[str, bool]:
    return {key: descriptor.get(key) is True for key in _REQUIRED_CAPABILITIES}


def normalize_coordination_adapter_descriptor(
    descriptor: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return a closed descriptor, or blockers. Absence stays unconfigured."""
    if descriptor is None:
        return None, ["ADAPTER_NOT_CONFIGURED"]
    if not isinstance(descriptor, Mapping):
        return None, ["DESCRIPTOR_INVALID"]
    secret = sorted(key for key in descriptor if _secret_key(str(key)))
    if secret:
        return None, [f"DESCRIPTOR_SECRET_FIELD:{secret[0]}"]
    closed = _closed(descriptor, _DESCRIPTOR_KEYS, "DESCRIPTOR")
    if closed:
        return None, [closed]
    adapter_id = _text(descriptor.get("adapter_id"), 80)
    adapter_version = _text(descriptor.get("adapter_version"), 40)
    provider = _text(descriptor.get("provider"), 80)
    backend_kind = _text(descriptor.get("backend_kind"), 40)
    if not all((adapter_id, adapter_version, provider, backend_kind)):
        return None, ["DESCRIPTOR_INCOMPLETE"]
    if type(descriptor.get("paid_service")) is not bool:
        return None, ["DESCRIPTOR_INVALID"]
    blockers: list[str] = []
    if str(backend_kind).casefold() in _ABSENT_BACKENDS:
        blockers.append("BACKEND_NOT_CONFIGURED")
    for name in _REQUIRED_CAPABILITIES:
        if descriptor.get(name) is not True:
            blockers.append(f"CAPABILITY_NOT_SATISFIED:{name}")
    if blockers:
        return None, blockers
    normalized = {
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "provider": provider,
        "backend_kind": backend_kind,
        "paid_service": descriptor.get("paid_service") is True,
        **_capability_view(descriptor),
    }
    return normalized, []


def probe_receipt_digest(receipt: Mapping[str, Any]) -> str:
    """Digest every receipt field except the stored digest itself."""
    payload = {key: receipt.get(key) for key in _RECEIPT_KEYS if key != "receipt_digest"}
    return _digest(payload)


def seal_probe_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Attach the canonical digest. This does not call a provider or persist."""
    sealed = {key: receipt.get(key) for key in _RECEIPT_KEYS if key != "receipt_digest"}
    sealed["receipt_digest"] = probe_receipt_digest(sealed)
    return sealed


def build_probe_receipt_fixture(
    descriptor: Mapping[str, Any],
    *,
    scope_digest: str,
    now: datetime,
    ttl_seconds: int = 300,
    evidence_digest: str = "ab" * 32,
) -> dict[str, Any]:
    """Build an in-memory validation receipt for tests. Nothing is stored."""
    normalized, blockers = normalize_coordination_adapter_descriptor(descriptor)
    if normalized is None:
        raise ValueError(blockers[0] if blockers else "DESCRIPTOR_INVALID")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    if type(ttl_seconds) is not int or ttl_seconds < 1 or ttl_seconds > MAX_PROBE_TTL_SECONDS:
        raise ValueError("probe ttl exceeds the allowed window")
    scope = _text(scope_digest, 128)
    evidence = _text(evidence_digest, 128)
    if not scope or not evidence:
        raise ValueError("scope_digest and evidence_digest are required")
    issued = now.astimezone(timezone.utc)
    expires = issued + timedelta(seconds=ttl_seconds)
    return seal_probe_receipt({
        "schema": RECEIPT_SCHEMA,
        "receipt_version": RECEIPT_VERSION,
        "adapter_identity_digest": adapter_identity_digest(normalized),
        "scope_digest": scope,
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
        "evidence_digest": evidence,
        "observed_capabilities": _capability_view(normalized),
        "mutation_count": 0,
        "read_only_validation": True,
    })


def _validate_receipt(
    receipt: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    expected_scope_digest: str,
    now: datetime,
) -> list[str]:
    if not isinstance(receipt, Mapping):
        return ["PROBE_RECEIPT_INVALID"]
    secret = sorted(key for key in receipt if _secret_key(str(key)))
    if secret:
        return [f"PROBE_SECRET_FIELD:{secret[0]}"]
    closed = _closed(receipt, _RECEIPT_KEYS, "PROBE")
    if closed:
        return [closed]
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("receipt_version") != RECEIPT_VERSION:
        return ["PROBE_RECEIPT_INVALID"]
    if receipt.get("receipt_digest") != probe_receipt_digest(receipt):
        return ["PROBE_DIGEST_MISMATCH"]
    if receipt.get("adapter_identity_digest") != adapter_identity_digest(descriptor):
        return ["PROBE_ADAPTER_MISMATCH"]
    scope = receipt.get("scope_digest")
    expected = _text(expected_scope_digest, 128)
    if not isinstance(scope, str) or not scope.strip():
        return ["PROBE_SCOPE_DIGEST_MISSING"]
    if expected is None or scope != expected:
        return ["PROBE_SCOPE_MISMATCH"]
    issued = _aware(receipt.get("issued_at"))
    expires = _aware(receipt.get("expires_at"))
    if issued is None or expires is None:
        return ["PROBE_TIMESTAMP_INVALID"]
    window = (expires - issued).total_seconds()
    if window <= 0 or window > MAX_PROBE_TTL_SECONDS:
        return ["PROBE_TTL_EXCEEDED"]
    current = now.astimezone(timezone.utc)
    if issued > current or current >= expires:
        return ["PROBE_EXPIRED"] if current >= expires else ["PROBE_TIMESTAMP_INVALID"]
    if receipt.get("read_only_validation") is not True:
        return ["PROBE_NOT_READ_ONLY"]
    if type(receipt.get("mutation_count")) is not int or receipt.get("mutation_count") != 0:
        return ["PROBE_MUTATED"]
    evidence = _text(receipt.get("evidence_digest"), 128)
    if not evidence:
        return ["PROBE_EVIDENCE_MISSING"]
    observed = receipt.get("observed_capabilities")
    if not isinstance(observed, Mapping) or dict(observed) != _capability_view(descriptor):
        return ["PROBE_CAPABILITY_MISMATCH"]
    return []


def _safety(descriptor: Mapping[str, Any] | None) -> dict[str, Any]:
    paid = bool(descriptor and descriptor.get("paid_service") is True)
    return {
        "global_worker_started": False,
        "execution_authorized": False,
        "real_trading_enabled": False,
        "paid_service_declared": paid,
        "paid_service_approved": False,
        "feature_flag_changed": False,
        "worker_changed": False,
        "probe_executed": False,
    }


def coordination_adapter_readiness(
    descriptor: Mapping[str, Any] | None,
    *,
    probe_receipt: Mapping[str, Any] | None = None,
    expected_scope_digest: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify a future adapter. A matching receipt is evidence, not activation."""
    if now is None:
        current = datetime.now(timezone.utc)
    elif not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        normalized, _ignored = normalize_coordination_adapter_descriptor(descriptor)
        return {
            "schema": SCHEMA,
            "state": BLOCKED,
            "descriptor_state": DESCRIPTOR_INVALID if normalized is None else DESCRIPTOR_READY,
            "blockers": ["INVALID_CLOCK"],
            "adapter_id": "",
            "provider": "",
            "backend_kind": "",
            "backend_configured": False,
            "adapter_configured": False,
            "probe_evidence_accepted": False,
            "adapter_identity_digest": "",
            **_safety(normalized),
        }
    else:
        current = now.astimezone(timezone.utc)

    normalized, blockers = normalize_coordination_adapter_descriptor(descriptor)
    if normalized is None and blockers == ["ADAPTER_NOT_CONFIGURED"]:
        return {
            "schema": SCHEMA,
            "state": NOT_CONFIGURED,
            "descriptor_state": NOT_CONFIGURED,
            "blockers": blockers,
            "adapter_id": "",
            "provider": "",
            "backend_kind": "",
            "backend_configured": False,
            "adapter_configured": False,
            "probe_evidence_accepted": False,
            "adapter_identity_digest": "",
            **_safety(None),
        }
    if normalized is None:
        return {
            "schema": SCHEMA,
            "state": BLOCKED,
            "descriptor_state": DESCRIPTOR_INVALID,
            "blockers": blockers,
            "adapter_id": "",
            "provider": "",
            "backend_kind": "",
            "backend_configured": False,
            "adapter_configured": False,
            "probe_evidence_accepted": False,
            "adapter_identity_digest": "",
            **_safety(None),
        }

    identity = adapter_identity_digest(normalized)
    base = {
        "schema": SCHEMA,
        "descriptor_state": DESCRIPTOR_READY,
        "adapter_id": normalized["adapter_id"],
        "provider": normalized["provider"],
        "backend_kind": normalized["backend_kind"],
        "backend_configured": True,
        "adapter_configured": True,
        "adapter_identity_digest": identity,
        **_safety(normalized),
    }
    if probe_receipt is None:
        return {
            **base,
            "state": PROBE_REQUIRED,
            "blockers": [],
            "probe_evidence_accepted": False,
        }
    receipt_blockers = _validate_receipt(
        probe_receipt,
        normalized,
        expected_scope_digest,
        current,
    )
    if receipt_blockers:
        return {
            **base,
            "state": BLOCKED,
            "blockers": receipt_blockers,
            "probe_evidence_accepted": False,
        }
    return {
        **base,
        "state": PROBE_EVIDENCE_READY,
        "blockers": [],
        "probe_evidence_accepted": True,
    }


def format_coordination_adapter_caption(report: Mapping[str, Any]) -> str:
    """Compact admin lines. The worker and the feature flag stay unchanged."""
    backend = "CONFIGURADO" if report.get("backend_configured") is True else "NÃO CONFIGURADO"
    if report.get("adapter_configured") is True:
        adapter = str(report.get("adapter_id") or "CONFIGURADO")
    else:
        adapter = "NÃO CONFIGURADO"
    probe = "EVIDÊNCIA ACEITA" if report.get("state") == PROBE_EVIDENCE_READY else "NÃO EXECUTADO"
    return (
        "Backend compartilhado: " + backend + "\n"
        "Adapter: " + adapter + "\n"
        "Probe: " + probe + "\n"
        "Worker alterado: NÃO\n"
        "Feature flag alterada: NÃO"
    )
