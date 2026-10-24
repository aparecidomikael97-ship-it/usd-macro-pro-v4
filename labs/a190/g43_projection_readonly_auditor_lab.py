"""A190 G43 standalone SQLite read-only projection auditor — synthetic LAB.

Unlike instantiating SQLiteChatStore/ExecutionOutbox, opens mode=ro and does
not run _ensure_schema. Outputs anomaly classifications, NOT secret payloads.
This is local diagnosis, not database attestation or independent custodian.
"""
from __future__ import annotations
from pathlib import Path
import json
import sqlite3
from typing import Any

REQUIRED = {"action_outbox", "action_decisions", "action_effects"}
FIELDS = ("state", "attempts", "lease_owner", "lease_until",
          "dispatch_started_at", "sent_at", "confirmed_at",
          "last_error", "effect_ref")


def audit_projection_snapshot_readonly_lab(
    sqlite_file: Path, *, owner: str, tenant: str, workspace: str,
) -> dict[str, Any]:
    """Read a consistent, explicitly read-only snapshot, without Outbox init."""
    path = Path(sqlite_file).resolve()
    if not path.is_file():
        raise RuntimeError("G43_AUDIT_FILE_ABSENT")
    if not all(isinstance(v, str) and v for v in (owner, tenant, workspace)):
        raise RuntimeError("G43_AUDIT_SCOPE_REQUIRED")
    # File URI avoids immutable=1: concurrent WAL snapshots must not be
    # silently ignored. Query-only plus mode=ro blocks accidental DML.
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                         isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        objects = db.execute(
            "SELECT type,name FROM sqlite_schema "
            "WHERE type IN ('table','trigger','view')"
        ).fetchall()
        if any(row["type"] in ("trigger", "view") for row in objects):
            raise RuntimeError("G43_AUDIT_UNSUPPORTED_EXECUTABLE_SCHEMA")
        tables = {row["name"] for row in objects if row["type"] == "table"}
        if not REQUIRED.issubset(tables):
            raise RuntimeError("G43_AUDIT_SCHEMA_MISSING")
        rows = db.execute(
            """SELECT o.idempotency_key, o.decision_id, o.state,
                      o.attempts, o.lease_owner,o.lease_until,
                      o.dispatch_started_at, o.sent_at, o.confirmed_at,
                      o.last_error,o.effect_ref,o.data,
                      d.decision_id AS matched_decision,
                      d.owner AS decision_owner,d.tenant AS decision_tenant,
                      d.workspace AS decision_workspace,
                      e.effect_ref AS ledger_effect,e.confirmed_at AS ledger_at,
                      e.owner AS effect_owner,e.tenant AS effect_tenant,
                      e.workspace AS effect_workspace,
                      e.idempotency_key AS matched_effect
               FROM action_outbox o
               LEFT JOIN action_decisions d ON d.decision_id=o.decision_id
               LEFT JOIN action_effects e ON e.idempotency_key=o.idempotency_key
               WHERE o.owner=? AND o.tenant=? AND o.workspace=?
               ORDER BY o.idempotency_key""",
            (owner, tenant, workspace),
        ).fetchall()
        findings = []
        counts = {}
        for row in rows:
            code = "OK"
            if (row["matched_decision"] is None or
                    (row["decision_owner"],row["decision_tenant"],
                     row["decision_workspace"]) != (owner,tenant,workspace)):
                code = "DECISION_MISSING_OR_FOREIGN_SCOPE"
            elif (row["matched_effect"] is not None and
                  (row["effect_owner"],row["effect_tenant"],
                   row["effect_workspace"]) != (owner,tenant,workspace)):
                code = "EFFECT_SCOPE_MISMATCH"
            elif row["state"] == "CONFIRMED":
                if (row["matched_effect"] is None or
                        row["effect_ref"] != row["ledger_effect"] or
                        row["confirmed_at"] != row["ledger_at"]):
                    code = "CONFIRMED_LEDGER_INCONSISTENT"
            elif row["matched_effect"] is not None:
                code = "NONCONFIRMED_HAS_EFFECT"
            if code == "OK":
                try:
                    document = json.loads(row["data"])
                except (ValueError, TypeError):
                    code = "INVALID_JSON"
                else:
                    if not isinstance(document, dict):
                        code = "JSON_NOT_OBJECT"
                    elif (document.get("idempotency_key") != row["idempotency_key"] or
                          document.get("decision_id") != row["decision_id"]):
                        code = "JSON_IDENTITY_MISMATCH"
                    elif document.get("state") not in {
                        "PENDING", "RETRY", "CLAIMED", "UNCERTAIN",
                        "SENT", "CONFIRMED", "FAILED", "REVOKED",
                        "BLOCKED_REAPPROVAL",
                    }:
                        code = "JSON_STATE_INVALID"
                    elif any(
                        field in document and (
                            document[field] != (int(row[field]) if field == "attempts"
                                               else row[field])
                        )
                        for field in FIELDS
                    ) or document.get("state") != row["state"]:
                        code = "PROJECTION_DRIFT"
            counts[code] = counts.get(code, 0) + 1
            findings.append({"idempotency_key":row["idempotency_key"],
                             "issue":code})
        # Detect scoped effect-ledger orphans hidden by an Outbox left join.
        orphan_count = db.execute(
            """SELECT count(*) FROM action_effects e
               LEFT JOIN action_outbox o ON o.idempotency_key=e.idempotency_key
               WHERE e.owner=? AND e.tenant=? AND e.workspace=?
                 AND o.idempotency_key IS NULL""",
            (owner,tenant,workspace),
        ).fetchone()[0]
        if orphan_count:
            counts["ORPHAN_EFFECT_ROWS"] = int(orphan_count)
        db.execute("ROLLBACK")
        return {"schema":"AION-A190-G43-READONLY-AUDIT-V1",
                "scope":{"owner":owner,"tenant":tenant,"workspace":workspace},
                "row_count":len(rows),"counts":counts,
                "findings":findings}
    finally:
        db.close()
