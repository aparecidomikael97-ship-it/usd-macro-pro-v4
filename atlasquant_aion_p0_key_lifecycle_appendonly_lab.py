"""AION P0 LAB ONLY: synthetic key lifecycle chain & split-view screening.

This module is NOT an external log, key enrollment service, trusted ledger,
cryptographic signer, revocation authority, or a runtime authorization gate.
It receives caller-supplied data exclusively. Even a perfect sequence is BLOCKED.
No network, filesystem, clock, SDK, persistent write, or authorization.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS

SCHEMA = "AION_P0_KEY_LIFECYCLE_APPENDONLY_LAB_V1"
DOMAIN = b"ATLASQUANT:AION:P0:KEY_LOG:LAB:V1\x00"
GENESIS = "0" * 64
EVENT_FIELDS = frozenset((
    "sequence", "epoch", "event_type", "key_id", "previous_head",
    "record_head", "recorded_at_utc",
))
WITNESS_FIELDS = frozenset((
    "observer_id", "admin_root", "recovery_root", "sequence",
    "epoch", "head",
))
EVENT_TYPES = frozenset(("ENROLL", "ROTATE", "REVOKE", "RECOVER"))
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/@-]{2,127}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")


def _id(v: Any) -> bool:
    return type(v) is str and bool(IDENTIFIER.fullmatch(v))


def _digest(v: Any) -> bool:
    return type(v) is str and bool(DIGEST.fullmatch(v))


def _num(v: Any) -> bool:
    return type(v) is int and 0 <= v <= 2**63 - 1


def _time(v: Any) -> datetime | None:
    if type(v) is not str or not UTC.fullmatch(v):
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def calculate_record_head_lab(record_without_head: dict[str, Any]) -> str:
    """For inert, canonical built-in fixture fields only; not a trust hash."""
    payload = json.dumps(
        record_without_head, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")
    return sha256(DOMAIN + payload).hexdigest()


def audit_key_lifecycle_claims_lab(
    events: Any, witness_views: Any,
) -> dict[str, Any]:
    defects: list[str] = []
    if type(events) is not list:
        defects.append("EVENTS_NOT_PLAIN_LIST")
        events = []
    if not 1 <= len(events) <= 64:
        defects.append("EVENT_COUNT_OUT_OF_BOUNDS")
    if type(witness_views) is not list:
        defects.append("VIEWS_NOT_PLAIN_LIST")
        witness_views = []
    if not 2 <= len(witness_views) <= 5:
        defects.append("VIEW_COUNT_OUT_OF_BOUNDS")

    prior = GENESIS
    previous_time = None
    active_key = None
    state = "EMPTY"
    used_keys: set[str] = set()
    prior_epoch = 0
    records_valid = True

    for index, record in enumerate(events[:64]):
        if type(record) is not dict or frozenset(record) != EVENT_FIELDS:
            defects.append("EVENT_SHAPE_INVALID:" + str(index))
            records_valid = False
            continue
        valid = (
            _num(record["sequence"]) and _num(record["epoch"])
            and type(record["event_type"]) is str
            and record["event_type"] in EVENT_TYPES
            and _id(record["key_id"])
            and _digest(record["previous_head"])
            and _digest(record["record_head"])
            and _time(record["recorded_at_utc"]) is not None
        )
        if not valid:
            defects.append("EVENT_FIELD_INVALID:" + str(index))
            records_valid = False
            continue
        current_time = _time(record["recorded_at_utc"])
        if record["sequence"] != index + 1:
            defects.append("NONCONTIGUOUS_SEQUENCE:" + str(index))
        if record["epoch"] != prior_epoch + 1:
            defects.append("EPOCH_NOT_INCREMENTED:" + str(index))
        if record["previous_head"] != prior:
            defects.append("CHAIN_PARENT_MISMATCH:" + str(index))
        computed = calculate_record_head_lab({
            k: record[k] for k in EVENT_FIELDS if k != "record_head"
        })
        if computed != record["record_head"]:
            defects.append("EVENT_DIGEST_MISMATCH:" + str(index))
        if previous_time is not None and current_time <= previous_time:
            defects.append("CLOCK_NOT_INCREASING:" + str(index))
        action, key = record["event_type"], record["key_id"]
        if action == "ENROLL":
            if state != "EMPTY" or index != 0:
                defects.append("ENROLL_NOT_GENESIS:" + str(index))
            else:
                state, active_key = "ACTIVE", key
                used_keys.add(key)
        elif action == "ROTATE":
            if state != "ACTIVE":
                defects.append("ROTATE_WITHOUT_ACTIVE_KEY:" + str(index))
            if key in used_keys:
                defects.append("KEY_ID_REUSED:" + str(index))
            if state == "ACTIVE" and key not in used_keys:
                active_key = key
                used_keys.add(key)
        elif action == "REVOKE":
            if state != "ACTIVE" or key != active_key:
                defects.append("REVOKE_NON_ACTIVE_KEY:" + str(index))
            else:
                state, active_key = "REVOKED", None
        elif action == "RECOVER":
            if state != "REVOKED":
                defects.append("RECOVER_WITHOUT_REVOCATION:" + str(index))
            if key in used_keys:
                defects.append("KEY_ID_REUSED:" + str(index))
            if state == "REVOKED" and key not in used_keys:
                state, active_key = "ACTIVE", key
                used_keys.add(key)
        prior = record["record_head"]
        prior_epoch = record["epoch"]
        previous_time = current_time

    views: list[dict[str, Any]] = []
    for index, view in enumerate(witness_views[:5]):
        if type(view) is not dict or frozenset(view) != WITNESS_FIELDS:
            defects.append("VIEW_SHAPE_INVALID:" + str(index))
            continue
        if not (
            _id(view["observer_id"]) and _id(view["admin_root"])
            and _id(view["recovery_root"]) and _num(view["sequence"])
            and _num(view["epoch"]) and _digest(view["head"])
        ):
            defects.append("VIEW_FIELD_INVALID:" + str(index))
            continue
        views.append(view)
    if len(views) >= 2:
        for field in ("observer_id", "admin_root", "recovery_root"):
            values = [view[field] for view in views]
            if len(set(values)) != len(values):
                defects.append("CLAIMED_DOMAIN_COLLISION:" + field)
        # Cross-category overlap also matters: a recovery admin may control
        # a different observer's signing account despite unique labels.
        roots = [v[k] for v in views for k in ("admin_root", "recovery_root")]
        if len(set(roots)) != len(roots):
            defects.append("CROSS_ROLE_ADMIN_RECOVERY_COLLISION")
        if records_valid and events:
            final = events[-1]
            for index, view in enumerate(views):
                if any((
                    view["sequence"] != final["sequence"],
                    view["epoch"] != final["epoch"],
                    view["head"] != final["record_head"],
                )):
                    defects.append("WITNESS_VIEW_DIVERGES:" + str(index))
        per_height: dict[tuple[int, int], set[str]] = {}
        for view in views:
            per_height.setdefault(
                (view["epoch"], view["sequence"]), set()
            ).add(view["head"])
        if any(len(heads) > 1 for heads in per_height.values()):
            defects.append("SPLIT_VIEW_FORK_CLAIM")

    # A structural check NEVER authenticates the origin of events, witness
    # administration, signed tree head, inclusion/consistency proof or nonce.
    unsafe = tuple(sorted(set(defects)))
    blockers = tuple(sorted(set(defects + [
        "EXTERNAL_KEY_ISSUER_NOT_ENROLLED",
        "INDEPENDENT_APPEND_ONLY_CONSISTENCY_PROOF_MISSING",
        "OFF_HOST_LATEST_HEAD_NOT_AUTHENTICATED",
        "WITNESS_RECOVERY_INDEPENDENCE_NOT_AUDITED",
        "OUT_OF_BAND_NONCE_REVOCATION_NOT_VERIFIED",
    ])))
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "allowed": False,
        "reason": blockers[0],
        "blockers": blockers,
        "structural_defects": unsafe,
        "synthetic_sequence_structurally_consistent": (
            not unsafe and bool(events) and len(views) >= 2
        ),
        "external_issuer_verified": False,
        "external_latest_head_verified": False,
        "external_revocation_verified": False,
        "witnesses_independent_verified": False,
        "simulation_only": True,
        **{flag: False for flag in NO_GO_FLAGS},
    }


__all__ = ["SCHEMA", "DOMAIN", "GENESIS", "EVENT_FIELDS", "WITNESS_FIELDS",
           "calculate_record_head_lab", "audit_key_lifecycle_claims_lab"]
