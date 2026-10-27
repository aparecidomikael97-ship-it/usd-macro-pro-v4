"""G137: real SQLite decision-INSERT staging tripwire (LAB ONLY, NO P0).

Unlike the voluntary G136 Python facade, an explicitly installed SQLite
BEFORE INSERT trigger checks *every new action_decisions row*, including
direct ExecutionOutbox.enqueue calls that omit semantic_event_id_lab.

A matching permission is purely LOCAL and attacker-writable: self-minting a
row, DROP TRIGGER, joint rollback, same-inode edits, another DB, or skipping
LAB install defeats this layer. No trust root, provider or SEND here.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3
import subprocess
import sys

from atlasquant_aion_execution_outbox import ExecutionOutbox, _digest
from labs.a190.g134_process_custody_lab import ADMITTED
from labs.a190.g135_pinned_original_claim_lab import PinnedOriginalClaimLab


DENIED = "G137_DENIED_UNKNOWN_OR_UNCERTAIN_NO_RETRY"
STAGED = "G137_LOCAL_SQLITE_STAGE_ONLY_NOT_AUTHORITY_NO_SEND"

# Note: triggers are a lab-local *policy* over an untrusted database, not a
# true native OS/SQLite write authority boundary.
CREATE_PERMIT_TABLE = """
CREATE TABLE IF NOT EXISTS g137_local_stage_permits_lab (
 owner TEXT NOT NULL, tenant TEXT NOT NULL, workspace TEXT NOT NULL,
 intent_ref TEXT NOT NULL, action TEXT NOT NULL,
 original_event_id TEXT NOT NULL, payload_digest TEXT NOT NULL,
 consumed INTEGER NOT NULL DEFAULT 0 CHECK(consumed IN(0,1)),
 PRIMARY KEY (owner, tenant, workspace, intent_ref)
)
"""
CREATE_BEFORE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS g137_require_stage_permit_lab
BEFORE INSERT ON action_decisions
BEGIN
 SELECT RAISE(ABORT, 'G137_MISSING_LOCAL_STAGE_PERMIT')
 WHERE NOT EXISTS(
  SELECT 1 FROM g137_local_stage_permits_lab p
  WHERE p.owner=NEW.owner AND p.tenant=NEW.tenant
    AND p.workspace=NEW.workspace
    AND p.intent_ref=NEW.intent_ref AND p.action=NEW.action
    AND p.payload_digest=NEW.payload_digest AND p.consumed=0
 );
END
"""
CREATE_AFTER_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS g137_consume_stage_permit_lab
AFTER INSERT ON action_decisions
BEGIN
 UPDATE g137_local_stage_permits_lab SET consumed=1
 WHERE owner=NEW.owner AND tenant=NEW.tenant
   AND workspace=NEW.workspace AND intent_ref=NEW.intent_ref
   AND action=NEW.action AND payload_digest=NEW.payload_digest
   AND consumed=0;
END
"""


def install_local_tripwire_lab(outbox: ExecutionOutbox) -> None:
    """Explicit LAB provisioning; never a trusted mandatory global install."""
    if type(outbox) is not ExecutionOutbox:
        raise TypeError("G137_ACTUAL_OUTBOX_REQUIRED")
    outbox.store.require_healthy()
    db = outbox.db
    # The real Outbox schema already exists from its constructor.
    with db:
        db.execute(CREATE_PERMIT_TABLE)
        db.execute(CREATE_BEFORE_TRIGGER)
        db.execute(CREATE_AFTER_TRIGGER)


def _record_local_permit(db: sqlite3.Connection, scope, reference, action,
                         original_event, payload):
    """Adversarial fixture: anybody with db access can forge this row!"""
    with db:
        db.execute(
            """INSERT INTO g137_local_stage_permits_lab
               (owner,tenant,workspace,intent_ref,action,original_event_id,payload_digest)
               VALUES(?,?,?,?,?,?,?)""",
            (scope.owner_id, scope.tenant_id, scope.workspace_id,
             reference, action, original_event, _digest(payload)),
        )


def reserve_and_stage_lab(*, outbox: ExecutionOutbox, claim: PinnedOriginalClaimLab,
                          custody_path: Path, original, economic_effect,
                          evidence_query, technical_ref: str):
    """Voluntary safe-order orchestrator for synthetic test fixtures only.

    Strict read/write paths require the trigger installed beforehand.
    No automatic retry under lost subprocess ACK or Outbox exceptions.
    """
    if type(outbox) is not ExecutionOutbox or type(claim) is not PinnedOriginalClaimLab:
        return DENIED, None
    if not isinstance(custody_path, Path):
        return DENIED, None
    approved = claim.inspect(
        claimed_event=deepcopy(original),
        proposed_economic_effect=deepcopy(economic_effect),
        evidence_query=evidence_query,
    )
    if approved is None:
        return DENIED, None
    scope = outbox.scope
    if (approved["owner_id"], approved["tenant_id"], approved["workspace_id"]) != (
        scope.owner_id, scope.tenant_id, scope.workspace_id
    ):
        return DENIED, None
    try:
        process = subprocess.run([
            sys.executable, "-B", "-m", "labs.a190.g134_process_custody_lab",
            "reserve", str(custody_path), scope.tenant_id,
            approved["event_id"], approved["original_sha256"], technical_ref,
        ], capture_output=True, text=True, check=True, timeout=12)
        if process.stdout.strip() != ADMITTED or process.stderr:
            return DENIED, None
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return DENIED, None
    try:
        payload = {"business_event_id": approved["event_id"], **deepcopy(economic_effect)}
        _record_local_permit(outbox.db, scope, technical_ref,
                             economic_effect["action"], approved["event_id"], payload)
        item = outbox.enqueue(
            intent_ref=technical_ref,
            action=economic_effect["action"],
            payload=payload,
            semantic_event_id_lab=approved["event_id"],
            aggregate_key="g137-native-trigger-lab",
            policy_version="G137-LAB-NOT-AUTHORITY",
            authorization_ref="G137-SYNTHETIC-OWNER-NO-SEND",
            created_at="2026-10-27T12:00:00+00:00",
            valid_until="2026-10-27T12:05:00+00:00",
        )
        if item["enqueue_state"] != "ENQUEUED":
            return DENIED, None
        return STAGED, item
    except (sqlite3.Error, OSError, RuntimeError, TypeError, ValueError):
        return DENIED, None


__all__ = [
    "DENIED", "STAGED", "CREATE_PERMIT_TABLE", "CREATE_BEFORE_TRIGGER",
    "CREATE_AFTER_TRIGGER", "install_local_tripwire_lab",
    "reserve_and_stage_lab",
]
