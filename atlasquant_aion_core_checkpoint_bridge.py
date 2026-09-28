"""Checkpoint-backed persistence adapter for AION Core Intelligence.

The adapter stages Core memory inside the existing AtlasQuant Checkpoint Mestre.
It performs no network I/O. External durability still requires the existing
explicit Checkpoint save flow and Guardian approval.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import secrets
from typing import Any, Mapping
from uuid import uuid4

from atlasquant_aion_core_intelligence.adapters import (
    CHECKPOINT_NAMESPACE,
    attach_checkpoint,
)
from atlasquant_aion_core_intelligence.approval import Action
from atlasquant_aion_core_intelligence.context import Context, Domain
from atlasquant_aion_core_intelligence.evidence import Origin, digest, safe_text, timestamp, utc
from atlasquant_aion_core_intelligence.service import AionCore
from atlasquant_aion_core_intelligence.store import (
    ConflictError,
    EVENTS,
    KINDS,
    memory_subject,
)
from atlasquant_aion_observability import new_event
from atlasquant_aion_core_runtime_bridge import authenticated_context


SCHEMA = "ATLASQUANT_AION_CORE_CHECKPOINT_BRIDGE_V1"
MAX_RECORDS = 1000
MAX_APPROVALS = 500
MAX_EVENTS = 1000
MAX_BUNDLE_BYTES = 2_000_000


def _scope_payload(context: Context) -> list[str]:
    return json.loads(context.key)


def _bundle_digest(bundle: Mapping[str, Any]) -> str:
    raw = dict(bundle)
    raw.pop("digest", None)
    return digest(raw)


def _bounded_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    raw = json.dumps(bundle, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError("core checkpoint bundle too large")
    return dict(bundle)


class CheckpointCoreStore:
    """CoreStore-compatible staged store backed by one scoped checkpoint bundle."""

    storage_kind = "CHECKPOINT_MASTER_STAGED"
    remote_persistence = "REQUIRES_EXPLICIT_CHECKPOINT_SAVE"

    def __init__(self, context: Context, bundle: Mapping[str, Any] | None = None):
        if not isinstance(context, Context):
            raise ValueError("typed context required")
        self.context = context
        self.closed = False
        self.persistent = False
        self._revision = 0
        self._records: list[dict[str, Any]] = []
        self._approvals: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        if bundle:
            self._load(bundle)

    def _load(self, bundle: Mapping[str, Any]) -> None:
        data = _bounded_bundle(bundle)
        if data.get("schema") != "AION_CORE_CHECKPOINT_V1":
            raise ValueError("invalid core checkpoint schema")
        if data.get("scope") != _scope_payload(self.context):
            raise ValueError("CORE_CHECKPOINT_CONTEXT_MISMATCH")
        supplied = str(data.get("digest") or "")
        if not supplied or supplied != _bundle_digest(data):
            raise ValueError("CORE_CHECKPOINT_DIGEST_MISMATCH")
        revision = data.get("version", 0)
        if type(revision) is not int or revision < 0:
            raise ValueError("invalid core checkpoint revision")

        records = data.get("records", [])
        approvals = data.get("approvals", [])
        events = data.get("events", [])
        if not isinstance(records, list) or len(records) > MAX_RECORDS:
            raise ValueError("invalid core checkpoint records")
        if not isinstance(approvals, list) or len(approvals) > MAX_APPROVALS:
            raise ValueError("invalid core checkpoint approvals")
        if not isinstance(events, list) or len(events) > MAX_EVENTS:
            raise ValueError("invalid core checkpoint events")
        if any(not isinstance(x, Mapping) for x in records + approvals + events):
            raise ValueError("invalid core checkpoint rows")

        self._revision = revision
        self._records = [deepcopy(dict(x)) for x in records]
        self._approvals = {
            str(x.get("approval_id")): deepcopy(dict(x))
            for x in approvals
            if str(x.get("approval_id") or "").strip()
        }
        self._events = [deepcopy(dict(x)) for x in events]

    def close(self) -> None:
        self.closed = True

    def revision(self, context: Context) -> int:
        self._require_context(context)
        return self._revision

    def _require_context(self, context: Context) -> None:
        if self.closed:
            raise ValueError("core checkpoint store closed")
        if not isinstance(context, Context) or context.key != self.context.key:
            raise ValueError("CORE_CHECKPOINT_CONTEXT_MISMATCH")

    def history(self, context: Context) -> list[dict[str, Any]]:
        self._require_context(context)
        return deepcopy(self._records)

    def read(self, context: Context, now: datetime, *, kind: str | None = None) -> list[dict[str, Any]]:
        self._require_context(context)
        if kind is not None and kind not in KINDS:
            raise ValueError("invalid memory kind")
        latest: dict[str, dict[str, Any]] = {}
        for row in self._records:
            latest[str(row.get("record_id") or "")] = row
        self._event(context, "memory_read", now, "OK")
        return [
            deepcopy(row)
            for row in latest.values()
            if kind is None or row.get("kind") == kind
        ]

    def append(
        self,
        context: Context,
        *,
        kind: str,
        text: str,
        origin: Origin,
        source: str,
        now: datetime,
        expected_revision: int,
        evidence_refs: tuple[str, ...] = (),
        record_id: str | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_context(context)
        subject = memory_subject(kind, text, evidence_refs)
        if not isinstance(origin, Origin) or type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("explicit origin and checkpoint revision required")
        source = safe_text(source, 500)
        if origin != Origin.UNKNOWN and (
            source.upper() in {"UNKNOWN", "UNAVAILABLE"} or not evidence_refs
        ):
            raise ValueError("classified memory requires source and evidence references")
        if self._revision != expected_revision:
            raise ConflictError("checkpoint revision changed")

        snapshot = (
            self._revision,
            deepcopy(self._records),
            deepcopy(self._approvals),
            deepcopy(self._events),
        )
        try:
            if origin == Origin.USER_APPROVED:
                approval = self.approval(context, approval_id or "")
                if (
                    not approval
                    or approval.get("state") != "APPROVED"
                    or approval.get("action") != Action.MEMORY_DECISION.value
                    or approval.get("subject_digest") != digest(subject)
                    or timestamp(str(approval.get("expires_at") or "")) <= utc(now)
                    or approval.get("consumed") is not False
                ):
                    raise ValueError("matching unexpired human approval required")
                approval["consumed"] = True
                self._approvals[str(approval_id)] = approval
            elif approval_id is not None:
                raise ValueError("approval cannot relabel an observation or inference")

            prior = [
                x for x in self._records
                if str(x.get("record_id") or "") == str(record_id or "")
            ] if record_id else []
            if record_id is not None and not prior:
                raise ValueError("record is absent from this context")
            version = int(prior[-1].get("version") or 0) + 1 if prior else 1
            row = {
                "schema_version": 1,
                "record_id": record_id or uuid4().hex,
                "version": version,
                "checkpoint_revision": expected_revision + 1,
                **subject,
                "origin": origin.value,
                "source": source,
                "created_at": utc(now).isoformat(),
                "approval_id": approval_id,
                "is_approved_decision": origin == Origin.USER_APPROVED,
                "supersedes_version": version - 1 if prior else None,
            }
            self._records.append(row)
            if len(self._records) > MAX_RECORDS:
                raise ValueError("core checkpoint record limit reached")
            self._revision = expected_revision + 1
            self._event(context, "memory_write", now, "OK")
            return deepcopy(row)
        except Exception:
            self._revision, self._records, self._approvals, self._events = snapshot
            raise

    def approval(self, context: Context, approval_id: str) -> dict[str, Any] | None:
        self._require_context(context)
        row = self._approvals.get(str(approval_id or ""))
        return deepcopy(row) if row else None

    def _save_approval(
        self,
        context: Context,
        row: dict[str, Any],
        *,
        previous_version: int | None,
        now: datetime,
    ) -> None:
        self._require_context(context)
        approval_id = str(row.get("approval_id") or "").strip()
        if not approval_id:
            raise ValueError("approval id required")
        snapshot = deepcopy(self._approvals)
        events_snapshot = deepcopy(self._events)
        try:
            current = self._approvals.get(approval_id)
            if previous_version is None:
                if current is not None:
                    raise ConflictError("approval already exists")
            else:
                if not current or current.get("version") != previous_version:
                    raise ConflictError("approval version changed")
            self._approvals[approval_id] = deepcopy(row)
            if len(self._approvals) > MAX_APPROVALS:
                raise ValueError("core checkpoint approval limit reached")
            self._event(
                context,
                "approval_required" if previous_version is None else "approval_recorded",
                now,
            )
        except Exception:
            self._approvals = snapshot
            self._events = events_snapshot
            raise

    def _event(self, context: Context, event_type: str, now: datetime, result: str = "") -> None:
        self._require_context(context)
        if event_type not in EVENTS:
            raise ValueError("unknown core event")
        if result not in {"", "OK", "BLOCKED", "UNKNOWN", "UNAVAILABLE", "ERROR"}:
            raise ValueError("invalid event result")
        event = new_event(
            event_type,
            event_type,
            source="AION_CORE_CHECKPOINT_BRIDGE",
            truth_state="CONFIRMED",
            created_at=utc(now).isoformat(),
            task_id=context.task_id,
            domain=context.domain.value,
            result=result,
            evidence={"scope_digest": digest(context.key)},
        )
        self._events.append(event)
        if len(self._events) > MAX_EVENTS:
            self._events = self._events[-MAX_EVENTS:]

    def event(self, context: Context, event_type: str, now: datetime, result: str = "") -> None:
        self._event(context, event_type, now, result)

    def events(self, context: Context, limit: int = 100) -> list[dict[str, Any]]:
        self._require_context(context)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("invalid event limit")
        return deepcopy(self._events[-limit:])

    def checkpoint(self, context: Context, now: datetime) -> dict[str, Any]:
        self._require_context(context)
        out = {
            "schema": "AION_CORE_CHECKPOINT_V1",
            "scope": _scope_payload(context),
            "version": self._revision,
            "exported_at": utc(now).isoformat(),
            "records": deepcopy(self._records),
            "approvals": list(deepcopy(self._approvals).values()),
            "events": deepcopy(self._events),
            "storage": self.storage_kind,
        }
        out["digest"] = _bundle_digest(out)
        return _bounded_bundle(out)


class AuthenticatedSessionApprovalAdapter:
    """One-shot receipt verifier bound to the already-authenticated admin session."""

    def __init__(self, access: Mapping[str, Any] | None):
        context = authenticated_context(access, Domain.ADMIN)
        session = access.get("session") if isinstance(access, Mapping) else None
        if not isinstance(session, Mapping):
            raise ValueError("authenticated admin session required")
        self.principal = context.actor_id
        self.session_binding = digest({
            "actor": context.actor_id,
            "role": context.role,
            "credential_fingerprint": str(session.get("credential_fingerprint") or ""),
        })
        self._receipts: dict[str, tuple[str, str, str, str, str, str]] = {}

    def issue(
        self,
        *,
        context: Context,
        approval_id: str,
        subject_digest: str,
        action: str,
        decision: str,
    ) -> str:
        if context.actor_id != self.principal:
            raise ValueError("approval principal mismatch")
        receipt = secrets.token_urlsafe(32)
        self._receipts[receipt] = (
            context.key,
            approval_id,
            subject_digest,
            action,
            decision,
            self.session_binding,
        )
        return receipt

    def verify(
        self,
        *,
        context: Context,
        approval_id: str,
        subject_digest: str,
        action: str,
        decision: str,
        receipt: str,
    ) -> str | None:
        expected = (
            context.key,
            approval_id,
            subject_digest,
            action,
            decision,
            self.session_binding,
        )
        stored = self._receipts.pop(str(receipt or ""), None)
        return self.principal if stored == expected else None


def load_checkpoint_store(
    context: Context,
    legacy_checkpoint: Mapping[str, Any] | None,
) -> tuple[CheckpointCoreStore, dict[str, Any]]:
    legacy = dict(legacy_checkpoint or {})
    raw = legacy.get(CHECKPOINT_NAMESPACE)
    if not isinstance(raw, Mapping):
        return CheckpointCoreStore(context), {
            "state": "EMPTY",
            "reason": "CORE_NAMESPACE_ABSENT",
            "records": 0,
            "version": 0,
        }
    try:
        store = CheckpointCoreStore(context, raw)
        return store, {
            "state": "CONNECTED",
            "reason": "",
            "records": len(store.history(context)),
            "version": store.revision(context),
        }
    except ValueError as exc:
        if str(exc) == "CORE_CHECKPOINT_CONTEXT_MISMATCH":
            return CheckpointCoreStore(context), {
                "state": "CONTEXT_ISOLATED",
                "reason": "CORE_CHECKPOINT_CONTEXT_MISMATCH",
                "records": 0,
                "version": 0,
            }
        raise


def attach_store_to_checkpoint(
    legacy_checkpoint: Mapping[str, Any],
    store: CheckpointCoreStore,
    context: Context,
    now: datetime,
) -> dict[str, Any]:
    export = store.checkpoint(context, now)
    return attach_checkpoint(dict(legacy_checkpoint), export, context)


def stage_user_approved_memory(
    access: Mapping[str, Any] | None,
    legacy_checkpoint: Mapping[str, Any],
    *,
    kind: str,
    text: str,
    confirmation: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_HUMAN_CONFIRMATION_REQUIRED",
            "checkpoint": dict(legacy_checkpoint or {}),
            "external_persisted": False,
            "execution_authorized": False,
        }
    current = utc(now or datetime.now(timezone.utc))
    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")
    if kind not in {"DECISION", "REQUIREMENT", "PRIORITY", "PENDING_TASK"}:
        raise ValueError("unsupported staged memory kind")
    clean_text = safe_text(text, 2400)

    store, state = load_checkpoint_store(context, legacy_checkpoint)
    if state["state"] == "CONTEXT_ISOLATED":
        raise ValueError("CORE_CHECKPOINT_CONTEXT_MISMATCH")

    adapter = AuthenticatedSessionApprovalAdapter(access)
    core = AionCore(store, human_adapter=adapter, clock=lambda: current)
    source = "AUTHENTICATED_ADMIN_SESSION"
    evidence_ref = "authenticated-session:" + adapter.session_binding[:24]
    subject = memory_subject(kind, clean_text, (evidence_ref,))
    request = core.approvals.request(
        context,
        Action.MEMORY_DECISION,
        subject,
        current,
        ttl_seconds=900,
    )
    receipt = adapter.issue(
        context=context,
        approval_id=request["approval_id"],
        subject_digest=request["subject_digest"],
        action=request["action"],
        decision="APPROVED",
    )
    approval = core.approvals.decide(
        context,
        request["approval_id"],
        "APPROVED",
        receipt,
        current,
    )
    row = core.remember(
        context,
        kind=kind,
        text=clean_text,
        origin=Origin.USER_APPROVED,
        source=source,
        expected_revision=store.revision(context),
        evidence_refs=(evidence_ref,),
        approval_id=approval["approval_id"],
    )
    staged = attach_store_to_checkpoint(legacy_checkpoint, store, context, current)
    return {
        "schema": SCHEMA,
        "status": "STAGED",
        "reason": "EXPLICIT_ADMIN_APPROVAL_BOUND_TO_RECORD",
        "checkpoint": staged,
        "record": row,
        "approval": {
            "approval_id": approval["approval_id"],
            "state": approval["state"],
            "human_principal": approval["human_principal"],
            "decision_at": approval["decision_at"],
            "execution_authorized": False,
        },
        "store_state": {
            "state": "CHECKPOINT_MASTER_STAGED",
            "version": store.revision(context),
            "records": len(store.history(context)),
        },
        "external_persisted": False,
        "requires_checkpoint_save": True,
        "execution_authorized": False,
        "external_action_executed": False,
    }


def checkpoint_memory_snapshot(
    access: Mapping[str, Any] | None,
    legacy_checkpoint: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = utc(now or datetime.now(timezone.utc))
    context = authenticated_context(access, Domain.ADMIN)
    store, state = load_checkpoint_store(context, legacy_checkpoint)
    if state["state"] == "CONTEXT_ISOLATED":
        return {
            "schema": SCHEMA,
            "state": "CONTEXT_ISOLATED",
            "records": [],
            "approved_decisions": [],
            "version": 0,
            "external_persisted": False,
        }
    rows = store.read(context, current)
    return {
        "schema": SCHEMA,
        "state": state["state"],
        "records": rows,
        "approved_decisions": [
            row for row in rows
            if row.get("kind") == "DECISION"
            and row.get("origin") == Origin.USER_APPROVED.value
        ],
        "version": store.revision(context),
        "storage": store.storage_kind,
        "external_persistence": store.remote_persistence,
        "external_persisted": False,
    }


__all__ = [
    "SCHEMA",
    "CheckpointCoreStore",
    "AuthenticatedSessionApprovalAdapter",
    "load_checkpoint_store",
    "attach_store_to_checkpoint",
    "stage_user_approved_memory",
    "checkpoint_memory_snapshot",
]
