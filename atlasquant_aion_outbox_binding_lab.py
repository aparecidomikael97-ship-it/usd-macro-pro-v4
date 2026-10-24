"""A190 G44: PURE local Outbox/Decision/Effect binding inspection (LAB).

No table creation, no DML, no provider, no host root of trust. Column/JSON
consistency is not provenance of a business event or an authenticated receipt.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
from typing import Any

STATES = {"PENDING", "RETRY", "CLAIMED", "UNCERTAIN", "SENT",
          "CONFIRMED", "FAILED", "REVOKED", "BLOCKED_REAPPROVAL"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _object(value: Any) -> dict[str, Any] | None:
    # Default json.loads silently keeps the LAST of duplicate object keys.
    # A safety-critical decision must not carry ambiguous JSON identities.
    def unique_keys(pairs):
        obj = {}
        for name, item in pairs:
            if name in obj:
                raise ValueError("G44_DUPLICATE_JSON_KEY")
            obj[name] = item
        return obj

    try:
        parsed = json.loads(value, object_pairs_hook=unique_keys)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def binding_issue_lab(
    db: sqlite3.Connection, key: str, scope: tuple[str, str, str],
) -> str:
    """Return one generic scoped issue; never return private payload."""
    if (not isinstance(key, str) or not key or
            len(scope) != 3 or any(not isinstance(x, str) or not x for x in scope)):
        return "INVALID_BINDING_REQUEST"
    o = db.execute(
        """SELECT * FROM action_outbox
           WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
        (key, *scope),
    ).fetchone()
    if o is None:
        return "OUTBOX_UNAVAILABLE"
    if (o["state"] not in STATES or type(o["attempts"]) is not int or
            o["attempts"] < 0):
        return "OUTBOX_STATE_OR_EPOCH_INVALID"
    outbox_json = _object(o["data"])
    if outbox_json is None:
        return "OUTBOX_JSON_INVALID"
    if (outbox_json.get("idempotency_key") != key or
            outbox_json.get("decision_id") != o["decision_id"]):
        return "OUTBOX_JSON_IDENTITY_MISMATCH"

    references = db.execute(
        "SELECT COUNT(*) FROM action_outbox WHERE decision_id=?",
        (o["decision_id"],),
    ).fetchone()[0]
    if references != 1:
        return "DECISION_SHARED_BY_MULTIPLE_OUTBOXES"

    d = db.execute(
        "SELECT * FROM action_decisions WHERE decision_id=?",
        (o["decision_id"],),
    ).fetchone()
    if d is None:
        return "DECISION_UNAVAILABLE"
    if (d["owner"], d["tenant"], d["workspace"]) != scope:
        return "DECISION_SCOPE_MISMATCH"
    decision = _object(d["data"])
    if decision is None:
        return "DECISION_JSON_INVALID"
    checks = {
        "decision_id": d["decision_id"], "owner_id": d["owner"],
        "tenant_id": d["tenant"], "workspace_id": d["workspace"],
        "idempotency_key": key,
        "intent_ref": d["intent_ref"], "action": d["action"],
        "aggregate_key": d["aggregate_key"],
        "aggregate_seq": d["aggregate_seq"],
        "payload_digest": d["payload_digest"],
        "policy_version": d["policy_version"],
        "authorization_ref": d["authorization_ref"],
        "valid_until": d["valid_until"], "created_at": d["created_at"],
    }
    if any(decision.get(name) != wanted for name, wanted in checks.items()):
        return "DECISION_COLUMN_JSON_MISMATCH"
    if type(d["aggregate_seq"]) is not int or d["aggregate_seq"] < 1:
        return "DECISION_AGGREGATE_INVALID"
    if not isinstance(decision.get("payload"), dict):
        return "DECISION_PAYLOAD_INVALID"
    if _digest(decision["payload"]) != d["payload_digest"]:
        return "DECISION_PAYLOAD_DIGEST_MISMATCH"
    key_material = {
        "scope": list(scope),
        "intent_ref": d["intent_ref"],
        "action": d["action"],
        "aggregate_key": d["aggregate_key"],
        "payload_digest": d["payload_digest"],
        "transaction_id": decision.get("transaction_id", ""),
        "authority_budget_ref": decision.get("authority_budget_ref", ""),
        "risk_points": decision.get("risk_points", 0),
        "capability_class": decision.get("capability_class", ""),
    }
    semantic = decision.get("semantic_event_id_lab") or ""
    if semantic:
        key_material["semantic_event_id_lab"] = semantic
    if key != _digest(key_material):
        return "DECISION_IDEMPOTENCY_MATERIAL_MISMATCH"
    if d["decision_id"] != "DEC-" + key[:24].upper():
        return "DECISION_ID_DERIVATION_MISMATCH"
    if semantic:
        reservation = db.execute(
            """SELECT * FROM semantic_reservations_lab
               WHERE tenant=? AND business_event_id=?""",
            (d["tenant"], semantic),
        ).fetchone()
        if (reservation is None or reservation["idempotency_key"] != key or
                reservation["owner"] != d["owner"] or
                reservation["workspace"] != d["workspace"] or
                reservation["intent_ref"] != d["intent_ref"] or
                reservation["payload_digest"] != d["payload_digest"]):
            return "SEMANTIC_RESERVATION_MISMATCH"
    e = db.execute(
        "SELECT * FROM action_effects WHERE idempotency_key=?", (key,),
    ).fetchone()
    if e is not None:
        if (e["owner"], e["tenant"], e["workspace"]) != scope:
            return "EFFECT_SCOPE_MISMATCH"
        if o["state"] != "CONFIRMED":
            return "NONCONFIRMED_EFFECT_PRESENT"
        if (e["effect_ref"] != o["effect_ref"] or
                e["confirmed_at"] != o["confirmed_at"]):
            return "EFFECT_COLUMN_MISMATCH"
    elif o["state"] == "CONFIRMED":
        return "CONFIRMED_EFFECT_ABSENT"
    return "OK"


def audit_binding_readonly_lab(
    sqlite_file: Path, *, owner: str, tenant: str, workspace: str,
) -> dict[str, Any]:
    """Mode=ro snapshot, no constructors, no schema DDL or payload output."""
    path = Path(sqlite_file).resolve()
    if not path.is_file():
        raise RuntimeError("G44_AUDIT_FILE_ABSENT")
    scope = (owner, tenant, workspace)
    if any(not isinstance(s, str) or not s for s in scope):
        raise RuntimeError("G44_AUDIT_SCOPE_REQUIRED")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                         isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        schema = db.execute(
            "SELECT type,name FROM sqlite_schema WHERE type IN ('table','view','trigger')"
        ).fetchall()
        if any(item["type"] in {"view","trigger"} for item in schema):
            raise RuntimeError("G44_UNSUPPORTED_EXECUTABLE_SCHEMA")
        tables = {item["name"] for item in schema if item["type"]=="table"}
        if not {"action_outbox","action_decisions","action_effects",
                "semantic_reservations_lab"}.issubset(tables):
            raise RuntimeError("G44_SCHEMA_ADMISSION_DENIED")
        keys = db.execute(
            """SELECT idempotency_key FROM action_outbox
               WHERE owner=? AND tenant=? AND workspace=? ORDER BY idempotency_key""",
            scope,
        ).fetchall()
        findings = []
        counts = {}
        for row in keys:
            issue = binding_issue_lab(db, row["idempotency_key"], scope)
            counts[issue] = counts.get(issue,0)+1
            findings.append({"idempotency_key":row["idempotency_key"],
                             "issue":issue})
        # No secret-bearing decision data or receipt content returned.
        orphans = db.execute(
            """SELECT COUNT(*) FROM action_effects e
               LEFT JOIN action_outbox o ON o.idempotency_key=e.idempotency_key
               WHERE e.owner=? AND e.tenant=? AND e.workspace=?
                 AND o.idempotency_key IS NULL""",scope,
        ).fetchone()[0]
        if orphans:
            counts["ORPHAN_EFFECT"] = int(orphans)
        abandoned_decisions = db.execute(
            """SELECT COUNT(*) FROM action_decisions d
               LEFT JOIN action_outbox o ON o.decision_id=d.decision_id
               WHERE d.owner=? AND d.tenant=? AND d.workspace=?
                 AND o.idempotency_key IS NULL""",scope,
        ).fetchone()[0]
        if abandoned_decisions:
            counts["ORPHAN_DECISION"] = int(abandoned_decisions)
        db.execute("ROLLBACK")
        return {"schema":"AION-A190-G44-BINDING-AUDIT-V1",
                "scope":{"owner":owner,"tenant":tenant,"workspace":workspace},
                "rows":len(keys),"counts":counts,"findings":findings}
    finally:
        db.close()
