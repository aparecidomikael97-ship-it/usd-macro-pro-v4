"""Shared coordination contract for future multi-instance AION workers.

This module deliberately ships without a production backend adapter. It defines
the atomic CAS/fencing/kill-switch contract, a destructive-but-bounded probe
that requires explicit ADMIN confirmation, and a fail-closed activation gate.

No network client, database driver, provider credential, paid service, or
background process is activated by importing this module.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import secrets
from typing import Any, Mapping, Protocol, runtime_checkable

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, safe_text, utc
from atlasquant_aion_core_runtime_bridge import authenticated_context


SCHEMA = "ATLASQUANT_AION_SHARED_COORDINATION_GATE_V1"
CHECKPOINT_NAMESPACE = "aion_shared_coordination_v1"
CHECKPOINT_SCHEMA = "AION_SHARED_COORDINATION_CHECKPOINT_V1"
PROBE_SCHEMA = "AION_SHARED_COORDINATION_PROBE_V1"
LEASE_SCHEMA = "AION_SHARED_COORDINATION_LEASE_V1"
MAX_PROBE_AGE_SECONDS = 900
PROBE_TTL_SECONDS = 120
MIN_LEASE_SECONDS = 90
MAX_LEASE_SECONDS = 1800

REQUIRED_CAPABILITIES = (
    "shared_across_instances",
    "atomic_compare_and_swap",
    "monotonic_versions",
    "atomic_monotonic_fencing_token",
    "ttl_expiry",
    "atomic_delete",
    "durable_outside_browser",
    "global_kill_switch_namespace",
)

BUDGET_FIELDS = (
    "max_workers",
    "max_claims_per_minute",
    "max_lease_seconds",
    "max_probe_writes",
)


@runtime_checkable
class SharedCoordinationAdapter(Protocol):
    """Provider-neutral atomic coordination adapter contract."""

    def describe(self) -> Mapping[str, Any]:
        ...

    def read(self, key: str) -> Mapping[str, Any]:
        ...

    def compare_and_swap(
        self,
        key: str,
        *,
        expected_version: int | None,
        value: Mapping[str, Any],
        ttl_seconds: int,
    ) -> Mapping[str, Any]:
        ...

    def delete(
        self,
        key: str,
        *,
        expected_version: int,
    ) -> Mapping[str, Any]:
        ...

    def next_fencing_token(
        self,
        key: str,
        *,
        ttl_seconds: int | None,
    ) -> Mapping[str, Any]:
        ...


def _now(value: datetime | None = None) -> datetime:
    return utc(value or datetime.now(timezone.utc))


def _scope_payload(context) -> list[str]:
    return json.loads(context.key)


def _bundle_digest(raw: Mapping[str, Any]) -> str:
    payload = dict(raw or {})
    payload.pop("digest", None)
    return digest(payload)


def _parse_iso(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return utc(parsed)
    except Exception:
        return None


def _exact_int(value: Any, *, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + name)
    return value


def _optional_text(value: Any, limit: int) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return safe_text(raw, limit)


def _descriptor(adapter: SharedCoordinationAdapter | None) -> dict[str, Any]:
    if adapter is None:
        return {
            "configured": False,
            "identity": "NONE",
            "backend_kind": "NONE",
            "shared_across_instances": False,
            "external_paid_service": False,
            "capabilities": {name: False for name in REQUIRED_CAPABILITIES},
            "reason": "NO_SHARED_ATOMIC_STORE_CONFIGURED",
        }
    if not isinstance(adapter, SharedCoordinationAdapter):
        return {
            "configured": False,
            "identity": "INVALID",
            "backend_kind": "UNKNOWN",
            "shared_across_instances": False,
            "external_paid_service": False,
            "capabilities": {name: False for name in REQUIRED_CAPABILITIES},
            "reason": "ADAPTER_CONTRACT_INCOMPLETE",
        }
    try:
        raw = dict(adapter.describe() or {})
    except Exception as exc:
        return {
            "configured": False,
            "identity": "UNKNOWN",
            "backend_kind": "UNKNOWN",
            "shared_across_instances": False,
            "external_paid_service": False,
            "capabilities": {name: False for name in REQUIRED_CAPABILITIES},
            "reason": "DESCRIPTOR_ERROR:" + type(exc).__name__,
        }
    caps_raw = raw.get("capabilities") if isinstance(raw.get("capabilities"), Mapping) else {}
    caps = {name: bool(caps_raw.get(name, False)) for name in REQUIRED_CAPABILITIES}
    identity = _optional_text(raw.get("identity"), 200)
    backend_kind = safe_text(str(raw.get("backend_kind") or "UNKNOWN"), 80)
    configured = bool(raw.get("configured")) and bool(identity)
    return {
        "configured": configured,
        "identity": identity or "UNKNOWN",
        "backend_kind": backend_kind or "UNKNOWN",
        "shared_across_instances": bool(caps["shared_across_instances"]),
        "external_paid_service": bool(raw.get("external_paid_service", False)),
        "capabilities": caps,
        "reason": _optional_text(raw.get("reason"), 300),
    }


def _read_record(adapter: SharedCoordinationAdapter, key: str) -> dict[str, Any]:
    raw = dict(adapter.read(key) or {})
    exists = bool(raw.get("exists"))
    version = raw.get("version")
    if exists:
        if type(version) is not int or version < 1:
            raise ValueError("invalid shared coordination version")
        value = raw.get("value")
        if not isinstance(value, Mapping):
            raise ValueError("invalid shared coordination value")
        return {
            "exists": True,
            "version": version,
            "value": deepcopy(dict(value)),
        }
    if version not in (None, 0):
        raise ValueError("invalid absent shared coordination version")
    return {"exists": False, "version": None, "value": {}}


def _cas(
    adapter: SharedCoordinationAdapter,
    key: str,
    *,
    expected_version: int | None,
    value: Mapping[str, Any],
    ttl_seconds: int,
) -> dict[str, Any]:
    ttl = _exact_int(
        ttl_seconds,
        minimum=1,
        maximum=MAX_LEASE_SECONDS,
        name="coordination ttl",
    )
    raw = dict(adapter.compare_and_swap(
        key,
        expected_version=expected_version,
        value=deepcopy(dict(value)),
        ttl_seconds=ttl,
    ) or {})
    swapped = bool(raw.get("swapped"))
    version = raw.get("version")
    if swapped and (type(version) is not int or version < 1):
        raise ValueError("invalid CAS version")
    if not swapped and version is not None and (
        type(version) is not int or version < 1
    ):
        raise ValueError("invalid CAS conflict version")
    return {
        "swapped": swapped,
        "version": version,
        "reason": _optional_text(raw.get("reason"), 200),
    }


def _delete(
    adapter: SharedCoordinationAdapter,
    key: str,
    *,
    expected_version: int,
) -> dict[str, Any]:
    version = _exact_int(
        expected_version,
        minimum=1,
        maximum=2_147_483_647,
        name="delete version",
    )
    raw = dict(adapter.delete(key, expected_version=version) or {})
    return {
        "deleted": bool(raw.get("deleted")),
        "reason": _optional_text(raw.get("reason"), 200),
    }


def _next_fencing_token(
    adapter: SharedCoordinationAdapter,
    key: str,
    *,
    ttl_seconds: int | None,
) -> int:
    if ttl_seconds is not None:
        _exact_int(
            ttl_seconds,
            minimum=1,
            maximum=MAX_LEASE_SECONDS,
            name="fencing ttl",
        )
    raw = dict(adapter.next_fencing_token(
        key,
        ttl_seconds=ttl_seconds,
    ) or {})
    token = raw.get("token")
    if type(token) is not int or token < 1:
        raise ValueError("invalid fencing token")
    return token


def probe_integrity(receipt: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(receipt, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if receipt.get("schema") != PROBE_SCHEMA:
        return {"state": "MISMATCH", "stored": "", "expected": PROBE_SCHEMA}
    supplied = str(receipt.get("digest") or "").strip()
    expected = _bundle_digest(receipt)
    return {
        "state": "MATCH" if supplied and supplied == expected else "MISMATCH",
        "stored": supplied,
        "expected": expected,
    }


def validate_probe(
    receipt: Mapping[str, Any] | None,
    *,
    adapter_identity: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _now(now)
    integrity = probe_integrity(receipt)
    if integrity["state"] != "MATCH":
        return {
            "state": "UNVERIFIED",
            "reason": "PROBE_RECEIPT_" + integrity["state"],
            "fresh": False,
        }
    raw = dict(receipt or {})
    if str(raw.get("adapter_identity") or "") != str(adapter_identity or ""):
        return {
            "state": "UNVERIFIED",
            "reason": "PROBE_ADAPTER_IDENTITY_MISMATCH",
            "fresh": False,
        }
    checked_at = _parse_iso(raw.get("checked_at"))
    expires_at = _parse_iso(raw.get("expires_at"))
    if checked_at is None or expires_at is None:
        return {
            "state": "UNVERIFIED",
            "reason": "PROBE_TIME_INVALID",
            "fresh": False,
        }
    if checked_at > current or expires_at <= current:
        return {
            "state": "STALE",
            "reason": "PROBE_EXPIRED_OR_FUTURE",
            "fresh": False,
        }
    tests = raw.get("tests") if isinstance(raw.get("tests"), Mapping) else {}
    required_tests = (
        "create_cas",
        "stale_cas_rejected",
        "live_cas",
        "read_after_cas",
        "version_monotonic",
        "fencing_token_monotonic",
        "cleanup",
    )
    if str(raw.get("status") or "") != "PASS" or not all(
        bool(tests.get(name)) for name in required_tests
    ):
        return {
            "state": "FAILED",
            "reason": "PROBE_SEMANTICS_NOT_CONFIRMED",
            "fresh": True,
        }
    return {
        "state": "CONFIRMED",
        "reason": "",
        "fresh": True,
        "checked_at": checked_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def run_coordination_probe(
    access: Mapping[str, Any] | None,
    adapter: SharedCoordinationAdapter | None,
    *,
    confirmation: bool,
    paid_service_approved: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run a bounded real CAS probe. This mutates only a temporary probe key."""
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_ADMIN_PROBE_CONFIRMATION_REQUIRED",
            "provider_called": False,
            "external_write_executed": False,
        }
    context = authenticated_context(access, Domain.ADMIN)
    descriptor = _descriptor(adapter)
    if not descriptor["configured"]:
        return {
            "schema": SCHEMA,
            "status": "UNAVAILABLE",
            "reason": descriptor["reason"] or "ADAPTER_NOT_CONFIGURED",
            "descriptor": descriptor,
            "provider_called": False,
            "external_write_executed": False,
        }
    missing = [
        name for name, enabled in descriptor["capabilities"].items()
        if not enabled
    ]
    if missing:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "MISSING_REQUIRED_CAPABILITIES:" + ",".join(missing),
            "descriptor": descriptor,
            "provider_called": False,
            "external_write_executed": False,
        }
    if descriptor["external_paid_service"] and paid_service_approved is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "PAID_SERVICE_REQUIRES_EXPLICIT_APPROVAL",
            "descriptor": descriptor,
            "provider_called": False,
            "external_write_executed": False,
        }

    current = _now(now)
    probe_suffix = digest({
        "scope": context.key,
        "adapter": descriptor["identity"],
        "nonce": secrets.token_urlsafe(18),
    })[:32]
    key = "atlasquant/aion/probe/" + probe_suffix
    fence_key = "atlasquant/aion/probe-fence/" + probe_suffix
    external_write = False
    mutation_count = 0
    first_version = None
    second_version = None
    tests = {
        "initial_absent": False,
        "create_cas": False,
        "stale_cas_rejected": False,
        "live_cas": False,
        "read_after_cas": False,
        "version_monotonic": False,
        "fencing_token_monotonic": False,
        "cleanup": False,
    }
    failure = ""
    try:
        initial = _read_record(adapter, key)
        tests["initial_absent"] = not initial["exists"]

        first_value = {
            "schema": "AION_COORDINATION_PROBE_VALUE_V1",
            "phase": 1,
            "owner": context.actor_id,
            "checked_at": current.isoformat(),
        }
        created = _cas(
            adapter,
            key,
            expected_version=None,
            value=first_value,
            ttl_seconds=PROBE_TTL_SECONDS,
        )
        external_write = external_write or created["swapped"]
        if created["swapped"]:
            mutation_count += 1
        tests["create_cas"] = created["swapped"]
        first_version = created["version"]
        if not created["swapped"] or first_version is None:
            raise RuntimeError("CREATE_CAS_FAILED")

        stale = _cas(
            adapter,
            key,
            expected_version=None,
            value={"phase": "stale"},
            ttl_seconds=PROBE_TTL_SECONDS,
        )
        external_write = external_write or stale["swapped"]
        if stale["swapped"]:
            mutation_count += 1
        tests["stale_cas_rejected"] = not stale["swapped"]
        if stale["swapped"]:
            raise RuntimeError("STALE_CAS_ACCEPTED")

        second_value = {
            "schema": "AION_COORDINATION_PROBE_VALUE_V1",
            "phase": 2,
            "owner": context.actor_id,
            "checked_at": current.isoformat(),
        }
        updated = _cas(
            adapter,
            key,
            expected_version=first_version,
            value=second_value,
            ttl_seconds=PROBE_TTL_SECONDS,
        )
        external_write = external_write or updated["swapped"]
        if updated["swapped"]:
            mutation_count += 1
        tests["live_cas"] = updated["swapped"]
        second_version = updated["version"]
        if not updated["swapped"] or second_version is None:
            raise RuntimeError("LIVE_CAS_FAILED")

        reread = _read_record(adapter, key)
        tests["read_after_cas"] = bool(
            reread["exists"]
            and reread["version"] == second_version
            and int(reread["value"].get("phase") or 0) == 2
        )
        tests["version_monotonic"] = bool(second_version > first_version)
        first_fence = _next_fencing_token(
            adapter,
            fence_key,
            ttl_seconds=PROBE_TTL_SECONDS,
        )
        mutation_count += 1
        external_write = True
        second_fence = _next_fencing_token(
            adapter,
            fence_key,
            ttl_seconds=PROBE_TTL_SECONDS,
        )
        mutation_count += 1
        external_write = True
        tests["fencing_token_monotonic"] = bool(second_fence > first_fence)
        deleted = _delete(
            adapter,
            key,
            expected_version=second_version,
        )
        tests["cleanup"] = deleted["deleted"]
        if deleted["deleted"]:
            mutation_count += 1
            external_write = True
        if not all((
            tests["read_after_cas"],
            tests["version_monotonic"],
            tests["fencing_token_monotonic"],
            tests["cleanup"],
        )):
            raise RuntimeError("PROBE_SEMANTICS_FAILED")
    except Exception as exc:
        failure = type(exc).__name__
        if second_version is not None:
            try:
                cleanup = _delete(
                    adapter,
                    key,
                    expected_version=second_version,
                )
                tests["cleanup"] = bool(cleanup["deleted"])
                if cleanup["deleted"]:
                    mutation_count += 1
                    external_write = True
            except Exception:
                pass
        elif first_version is not None:
            try:
                cleanup = _delete(
                    adapter,
                    key,
                    expected_version=first_version,
                )
                tests["cleanup"] = bool(cleanup["deleted"])
                if cleanup["deleted"]:
                    mutation_count += 1
                    external_write = True
            except Exception:
                pass

    passed = all((
        tests["create_cas"],
        tests["stale_cas_rejected"],
        tests["live_cas"],
        tests["read_after_cas"],
        tests["version_monotonic"],
        tests["fencing_token_monotonic"],
        tests["cleanup"],
    ))
    receipt = {
        "schema": PROBE_SCHEMA,
        "status": "PASS" if passed else "FAIL",
        "adapter_identity": descriptor["identity"],
        "backend_kind": descriptor["backend_kind"],
        "scope_digest": digest({"scope": context.key}),
        "checked_at": current.isoformat(),
        "expires_at": (
            current + timedelta(seconds=MAX_PROBE_AGE_SECONDS)
        ).isoformat(),
        "tests": tests,
        "first_version": first_version,
        "second_version": second_version,
        "failure_type": failure,
        "probe_writes": mutation_count,
        "cleanup_attempted": bool(first_version is not None),
        "paid_service_approved": bool(paid_service_approved),
        "external_write_executed": external_write,
        "real_trading_enabled": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
    }
    receipt["digest"] = _bundle_digest(receipt)
    return {
        "schema": SCHEMA,
        "status": "CONFIRMED" if passed else "FAILED",
        "reason": "" if passed else "PROBE_FAILED:" + (failure or "SEMANTICS"),
        "descriptor": descriptor,
        "probe_receipt": receipt,
        "provider_called": False,
        "external_write_executed": external_write,
        "real_trading_enabled": False,
    }


def checkpoint_bundle_integrity(
    raw: Mapping[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if raw.get("schema") != CHECKPOINT_SCHEMA:
        return {
            "state": "MISMATCH",
            "stored": "",
            "expected": CHECKPOINT_SCHEMA,
        }
    supplied = str(raw.get("digest") or "").strip()
    expected = _bundle_digest(raw)
    return {
        "state": "MATCH" if supplied and supplied == expected else "MISMATCH",
        "stored": supplied,
        "expected": expected,
    }


def stage_probe_receipt(
    checkpoint: Mapping[str, Any],
    context,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if probe_integrity(receipt)["state"] != "MATCH":
        raise ValueError("COORDINATION_PROBE_INTEGRITY_MISMATCH")
    out = deepcopy(dict(checkpoint or {}))
    previous = out.get(CHECKPOINT_NAMESPACE)
    if isinstance(previous, Mapping):
        previous_scope = previous.get("scope")
        if previous_scope != _scope_payload(context):
            raise ValueError("COORDINATION_CONTEXT_MISMATCH")
    bundle = {
        "schema": CHECKPOINT_SCHEMA,
        "scope": _scope_payload(context),
        "probe_receipt": deepcopy(dict(receipt)),
        "global_activation": "NOT_ACTIVATED",
        "shared_backend_connected": False,
        "updated_at": str(receipt.get("checked_at") or ""),
        "global_worker_started": False,
        "global_24x7_confirmed": False,
    }
    bundle["digest"] = _bundle_digest(bundle)
    out[CHECKPOINT_NAMESPACE] = bundle
    return out


def load_probe_receipt(
    context,
    checkpoint: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    raw = (
        checkpoint.get(CHECKPOINT_NAMESPACE)
        if isinstance(checkpoint, Mapping)
        else None
    )
    if raw is None:
        return None, {
            "state": "EMPTY",
            "reason": "COORDINATION_CHECKPOINT_ABSENT",
        }
    if not isinstance(raw, Mapping):
        raise ValueError("COORDINATION_CHECKPOINT_MISMATCH")
    integrity = checkpoint_bundle_integrity(raw)
    if integrity["state"] != "MATCH":
        raise ValueError("COORDINATION_CHECKPOINT_MISMATCH")
    if raw.get("scope") != _scope_payload(context):
        return None, {
            "state": "CONTEXT_ISOLATED",
            "reason": "COORDINATION_CONTEXT_MISMATCH",
        }
    receipt = raw.get("probe_receipt")
    if not isinstance(receipt, Mapping):
        return None, {
            "state": "EMPTY",
            "reason": "COORDINATION_PROBE_ABSENT",
        }
    return deepcopy(dict(receipt)), {"state": "CONNECTED", "reason": ""}


def validate_resource_budget(
    raw: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {"state": "INVALID", "reason": "RESOURCE_BUDGET_REQUIRED"}
    limits = {
        "max_workers": (1, 64),
        "max_claims_per_minute": (1, 600),
        "max_lease_seconds": (MIN_LEASE_SECONDS, MAX_LEASE_SECONDS),
        "max_probe_writes": (1, 10),
    }
    out = {}
    for name in BUDGET_FIELDS:
        value = raw.get(name)
        low, high = limits[name]
        if type(value) is not int or not low <= value <= high:
            return {
                "state": "INVALID",
                "reason": "INVALID_RESOURCE_BUDGET:" + name,
            }
        out[name] = value
    return {"state": "CONFIRMED", "reason": "", "budget": out}


def activation_gate(
    access: Mapping[str, Any] | None,
    adapter: SharedCoordinationAdapter | None,
    *,
    probe_receipt: Mapping[str, Any] | None,
    resource_budget: Mapping[str, Any] | None,
    confirmation: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Determine readiness. This never starts a global worker."""
    context = authenticated_context(access, Domain.ADMIN)
    descriptor = _descriptor(adapter)
    base = {
        "schema": SCHEMA,
        "adapter_identity": descriptor["identity"],
        "backend_kind": descriptor["backend_kind"],
        "global_worker_started": False,
        "execution_authorized": False,
        "external_action_executed": False,
        "real_trading_enabled": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
        "scope_digest": digest({"scope": context.key}),
    }
    if not descriptor["configured"]:
        return {
            **base,
            "status": "UNAVAILABLE",
            "reason": descriptor["reason"] or "SHARED_BACKEND_NOT_CONFIGURED",
        }
    missing = [
        name for name, enabled in descriptor["capabilities"].items()
        if not enabled
    ]
    if missing:
        return {
            **base,
            "status": "BLOCKED",
            "reason": "MISSING_REQUIRED_CAPABILITIES:" + ",".join(missing),
        }
    probe = validate_probe(
        probe_receipt,
        adapter_identity=descriptor["identity"],
        now=now,
    )
    if probe["state"] != "CONFIRMED":
        return {
            **base,
            "status": "BLOCKED",
            "reason": "COORDINATION_PROBE_" + probe["state"],
            "probe": probe,
        }
    budget = validate_resource_budget(resource_budget)
    if budget["state"] != "CONFIRMED":
        return {
            **base,
            "status": "BLOCKED",
            "reason": budget["reason"],
            "probe": probe,
        }
    probe_writes = int((probe_receipt or {}).get("probe_writes") or 0)
    if probe_writes > int(budget["budget"]["max_probe_writes"]):
        return {
            **base,
            "status": "BLOCKED",
            "reason": "PROBE_WRITE_BUDGET_EXCEEDED",
            "probe": probe,
            "budget": budget["budget"],
        }
    if confirmation is not True:
        return {
            **base,
            "status": "BLOCKED",
            "reason": "EXPLICIT_GLOBAL_ACTIVATION_CONFIRMATION_REQUIRED",
            "probe": probe,
            "budget": budget["budget"],
        }
    return {
        **base,
        "status": "READY",
        "reason": "COORDINATION_CONTRACT_READY_NOT_STARTED",
        "probe": probe,
        "budget": budget["budget"],
        "coordination_ready": True,
        "global_worker_started": False,
    }


class SharedLeaseManager:
    """Atomic lease/fencing contract over an injected shared CAS adapter."""

    def __init__(
        self,
        adapter: SharedCoordinationAdapter,
        *,
        namespace: str,
    ):
        self.adapter = adapter
        self.namespace = safe_text(namespace, 160)
        if not self.namespace:
            raise ValueError("shared coordination namespace required")

    def _key(self, kind: str) -> str:
        return self.namespace + "/" + safe_text(kind, 100)

    def _kill_state(self) -> dict[str, Any]:
        row = _read_record(self.adapter, self._key("kill-switch"))
        if not row["exists"]:
            return {
                "active": False,
                "version": None,
                "epoch": 0,
                "reason": "",
            }
        value = row["value"]
        return {
            "active": bool(value.get("active")),
            "version": row["version"],
            "epoch": int(value.get("epoch") or 0),
            "reason": _optional_text(value.get("reason"), 300),
        }

    def claim(
        self,
        *,
        owner: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = _now(now)
        ttl = _exact_int(
            ttl_seconds,
            minimum=MIN_LEASE_SECONDS,
            maximum=MAX_LEASE_SECONDS,
            name="shared lease",
        )
        owner_clean = safe_text(owner, 160)
        if not owner_clean:
            raise ValueError("lease owner required")
        kill = self._kill_state()
        if kill["active"]:
            return {
                "status": "KILLED",
                "reason": "GLOBAL_KILL_SWITCH_ACTIVE",
                "fencing_token": None,
            }
        key = self._key("lease")
        row = _read_record(self.adapter, key)
        expected_version = row["version"] if row["exists"] else None
        prior = row["value"] if row["exists"] else {}
        expires = _parse_iso(prior.get("expires_at"))
        if (
            row["exists"]
            and expires is not None
            and expires > current
            and str(prior.get("owner") or "") != owner_clean
        ):
            return {
                "status": "LEASE_HELD",
                "reason": "ACTIVE_SHARED_LEASE",
                "owner": str(prior.get("owner") or ""),
                "expires_at": expires.isoformat(),
                "fencing_token": int(prior.get("fencing_token") or 0),
            }
        same_live_owner = bool(
            row["exists"]
            and expires is not None
            and expires > current
            and str(prior.get("owner") or "") == owner_clean
        )
        next_fence = (
            int(prior.get("fencing_token") or 0)
            if same_live_owner
            else _next_fencing_token(
                self.adapter,
                self._key("fencing-counter"),
                ttl_seconds=None,
            )
        )
        lease_token = (
            str(prior.get("lease_token") or "")
            if same_live_owner and str(prior.get("lease_token") or "")
            else secrets.token_urlsafe(24)
        )
        value = {
            "schema": LEASE_SCHEMA,
            "owner": owner_clean,
            "lease_token": lease_token,
            "fencing_token": next_fence,
            "kill_epoch": kill["epoch"],
            "heartbeat_at": current.isoformat(),
            "expires_at": (current + timedelta(seconds=ttl)).isoformat(),
        }
        swapped = _cas(
            self.adapter,
            key,
            expected_version=expected_version,
            value=value,
            ttl_seconds=ttl,
        )
        if not swapped["swapped"]:
            return {
                "status": "CAS_CONFLICT",
                "reason": "SHARED_LEASE_RACE_LOST",
                "fencing_token": None,
            }
        return {
            "status": "CLAIMED",
            "reason": "",
            "owner": owner_clean,
            "lease_token": lease_token,
            "fencing_token": next_fence,
            "store_version": swapped["version"],
            "expires_at": value["expires_at"],
            "kill_epoch": kill["epoch"],
        }

    def heartbeat(
        self,
        *,
        owner: str,
        lease_token: str,
        fencing_token: int,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = _now(now)
        ttl = _exact_int(
            ttl_seconds,
            minimum=MIN_LEASE_SECONDS,
            maximum=MAX_LEASE_SECONDS,
            name="shared lease",
        )
        fence = _exact_int(
            fencing_token,
            minimum=1,
            maximum=2_147_483_647,
            name="fencing token",
        )
        kill = self._kill_state()
        if kill["active"]:
            return {"status": "KILLED", "reason": "GLOBAL_KILL_SWITCH_ACTIVE"}
        key = self._key("lease")
        row = _read_record(self.adapter, key)
        if not row["exists"]:
            return {"status": "LOST", "reason": "LEASE_ABSENT"}
        prior = row["value"]
        if (
            str(prior.get("owner") or "") != safe_text(owner, 160)
            or str(prior.get("lease_token") or "") != str(lease_token or "")
            or int(prior.get("fencing_token") or 0) != fence
            or int(prior.get("kill_epoch") or 0) != kill["epoch"]
        ):
            return {"status": "LOST", "reason": "FENCING_OR_OWNER_MISMATCH"}
        expires = _parse_iso(prior.get("expires_at"))
        if expires is None or expires <= current:
            return {"status": "LOST", "reason": "LEASE_EXPIRED"}
        value = {
            **deepcopy(prior),
            "heartbeat_at": current.isoformat(),
            "expires_at": (current + timedelta(seconds=ttl)).isoformat(),
        }
        swapped = _cas(
            self.adapter,
            key,
            expected_version=row["version"],
            value=value,
            ttl_seconds=ttl,
        )
        return {
            "status": "HEARTBEAT" if swapped["swapped"] else "CAS_CONFLICT",
            "reason": "" if swapped["swapped"] else "SHARED_HEARTBEAT_RACE_LOST",
            "fencing_token": fence,
            "store_version": swapped["version"],
            "expires_at": value["expires_at"] if swapped["swapped"] else "",
        }

    def release(
        self,
        *,
        owner: str,
        lease_token: str,
        fencing_token: int,
    ) -> dict[str, Any]:
        fence = _exact_int(
            fencing_token,
            minimum=1,
            maximum=2_147_483_647,
            name="fencing token",
        )
        key = self._key("lease")
        row = _read_record(self.adapter, key)
        if not row["exists"]:
            return {"status": "RELEASED", "reason": "ALREADY_ABSENT"}
        prior = row["value"]
        if (
            str(prior.get("owner") or "") != safe_text(owner, 160)
            or str(prior.get("lease_token") or "") != str(lease_token or "")
            or int(prior.get("fencing_token") or 0) != fence
        ):
            return {"status": "BLOCKED", "reason": "FENCING_OR_OWNER_MISMATCH"}
        deleted = _delete(
            self.adapter,
            key,
            expected_version=row["version"],
        )
        return {
            "status": "RELEASED" if deleted["deleted"] else "CAS_CONFLICT",
            "reason": "" if deleted["deleted"] else "SHARED_RELEASE_RACE_LOST",
        }

    def set_kill_switch(
        self,
        *,
        active: bool,
        reason: str,
    ) -> dict[str, Any]:
        key = self._key("kill-switch")
        row = _read_record(self.adapter, key)
        prior = row["value"] if row["exists"] else {}
        epoch = int(prior.get("epoch") or 0)
        if bool(prior.get("active")) != bool(active):
            epoch += 1
        value = {
            "active": bool(active),
            "epoch": epoch,
            "reason": _optional_text(reason, 300),
        }
        swapped = _cas(
            self.adapter,
            key,
            expected_version=row["version"] if row["exists"] else None,
            value=value,
            ttl_seconds=MAX_LEASE_SECONDS,
        )
        return {
            "status": "UPDATED" if swapped["swapped"] else "CAS_CONFLICT",
            "active": bool(active) if swapped["swapped"] else bool(prior.get("active")),
            "epoch": epoch if swapped["swapped"] else int(prior.get("epoch") or 0),
            "reason": "" if swapped["swapped"] else "GLOBAL_KILL_SWITCH_RACE_LOST",
        }


def shared_coordination_snapshot(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any] | None,
    *,
    adapter: SharedCoordinationAdapter | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    context = authenticated_context(access, Domain.ADMIN)
    descriptor = _descriptor(adapter)
    receipt, state = load_probe_receipt(context, checkpoint)
    probe = validate_probe(
        receipt,
        adapter_identity=descriptor["identity"],
        now=now,
    ) if receipt is not None and descriptor["configured"] else {
        "state": "UNVERIFIED",
        "reason": (
            "SHARED_BACKEND_NOT_CONFIGURED"
            if not descriptor["configured"]
            else "COORDINATION_PROBE_ABSENT"
        ),
        "fresh": False,
    }
    missing = [
        name for name, enabled in descriptor["capabilities"].items()
        if not enabled
    ]
    ready = bool(
        descriptor["configured"]
        and not missing
        and probe["state"] == "CONFIRMED"
    )
    return {
        "schema": SCHEMA,
        "status": "READY" if ready else (
            "UNAVAILABLE" if not descriptor["configured"] else "BLOCKED"
        ),
        "reason": (
            ""
            if ready
            else descriptor["reason"]
            or probe.get("reason")
            or "SHARED_COORDINATION_NOT_READY"
        ),
        "backend_kind": descriptor["backend_kind"],
        "adapter_identity": descriptor["identity"],
        "configured": descriptor["configured"],
        "required_capabilities": list(REQUIRED_CAPABILITIES),
        "missing_capabilities": missing,
        "probe_state": probe["state"],
        "probe_fresh": bool(probe.get("fresh")),
        "checkpoint_probe_state": state["state"],
        "coordination_ready": ready,
        "global_worker_started": False,
        "global_24x7_confirmed": False,
        "multi_instance_safe_confirmed": False,
        "external_paid_service_activated": False,
        "real_trading_enabled": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
    }


__all__ = [
    "SCHEMA",
    "CHECKPOINT_NAMESPACE",
    "CHECKPOINT_SCHEMA",
    "PROBE_SCHEMA",
    "LEASE_SCHEMA",
    "REQUIRED_CAPABILITIES",
    "BUDGET_FIELDS",
    "SharedCoordinationAdapter",
    "probe_integrity",
    "validate_probe",
    "run_coordination_probe",
    "checkpoint_bundle_integrity",
    "stage_probe_receipt",
    "load_probe_receipt",
    "validate_resource_budget",
    "activation_gate",
    "SharedLeaseManager",
    "shared_coordination_snapshot",
]
