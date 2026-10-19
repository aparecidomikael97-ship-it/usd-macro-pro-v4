"""AION P0 H0: ACTUAL SQLite boot observation, with a permanent no-witness deny.

READ-ONLY LAB DIAGNOSTIC ONLY. This does not run at productive startup,
claim, dispatch or Worker entrypoints. It cannot authenticate an external
custodian, discover a manual rollback or approve a first effect. Its only
authority answer is BLOCKED. A caller-provided witness-shaped object is
deliberately ignored, not inspected or authenticated.

Use for honest boot/rollback forensics, not as a "green" P0 certificate.
The underlying A118 dispatch remains hard-denied by producer enrollment.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

SCHEMA = "AION_P0_H0_SQLITE_STARTUP_OBSERVATION_LAB_V1"
_EXEC_TABLES = frozenset({
    "action_decisions", "action_outbox", "action_effects",
    "aion_execution_sagas", "aion_execution_saga_steps",
    "aion_execution_saga_events", "aion_authority_spend",
})
_OUTBOX_KNOWN_STATES = (
    "PENDING", "RETRY", "CLAIMED", "UNCERTAIN", "SENT", "CONFIRMED",
    "BLOCKED_PRODUCER", "BLOCKED_REAPPROVAL", "BLOCKED_AUTHORIZATION",
    "FAILED",
)


def observe_h0_sqlite_first_effect_lab(
    database_path: str | Path,
    _caller_witness_claim: Any = None,
) -> dict[str, Any]:
    """Read local SQLite, fail closed on ANY local state and ANY witness claim.

    No source-controlled signature, local sequence, file hash or even a SQLite
    quick_check can substitute for independently entrusted monotonic custody.
    Side-effect authority remains FALSE for every reachable return value.
    """
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "blocker": "INDEPENDENT_H0_WITNESS_NOT_ENROLLED",
        "local_observation": "UNAVAILABLE",
        "sqlite_quick_check_observed": False,
        "execution_schema_present": False,
        "outbox_rows_observed": 0,
        "outbox_states_observed": {k: 0 for k in _OUTBOX_KNOWN_STATES},
        "unrecognized_outbox_states": 0,
        "local_rollback_detected": False,
        "local_rollback_ruled_out": False,
        "independent_witness_source_enrolled": False,
        "independent_witness_authenticated": False,
        "external_highwater_compared": False,
        "monotonic_epoch_verified": False,
        "producer_receipt_authenticated": False,
        "first_attempt_cleared": False,
        "unknown_outcome_cleared": False,
        "automatic_retry_allowed": False,
        "claim_release_authorized": False,
        "worker_arming_allowed": False,
        "external_action_executed": False,
        "database_written_by_this_check": False,
    }
    # _caller_witness_claim is intentionally not read, not even checked for
    # truthiness: Python properties and __bool__ can be hostile.
    try:
        path = Path(database_path)
        if path.is_symlink():
            report["local_observation"] = "SYMLINK_PATH_UNTRUSTED"
            return report
        if not path.is_file():
            report["local_observation"] = "DATABASE_MISSING_OR_NOT_REGULAR"
            return report
        if not path.exists():
            report["local_observation"] = "DATABASE_MISSING_OR_NOT_REGULAR"
            return report
        # Read-only connection: no CREATE/UPDATE/INSERT/DELETE/DDL/backup.
        # WAL mode can still require SQLite-managed sidecar files; this is
        # not evidence of external immutability or physical read-only media.
        uri = path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db:
            db.execute("PRAGMA query_only=ON")
            quick = db.execute("PRAGMA quick_check(1)").fetchone()
            if quick is None or str(quick[0]).lower() != "ok":
                report["local_observation"] = "INTEGRITY_NOT_OBSERVED"
                return report
            report["sqlite_quick_check_observed"] = True
            names = {str(r[0]) for r in db.execute(
                "SELECT name FROM sqlite_schema WHERE type='table'"
            )}
            report["execution_schema_present"] = bool(names & _EXEC_TABLES)
            if "action_outbox" not in names:
                report["local_observation"] = (
                    "EXECUTION_SCHEMA_WITHOUT_OUTBOX" if report["execution_schema_present"]
                    else "NO_EXECUTION_SCHEMA_LOCALLY"
                )
                return report
            cols = {str(r[1]) for r in db.execute("PRAGMA table_info('action_outbox')")}
            if "state" not in cols:
                report["local_observation"] = "OUTBOX_SCHEMA_INCOMPLETE"
                return report
            statuses = db.execute(
                "SELECT state, COUNT(*) FROM action_outbox GROUP BY state"
            ).fetchall()
            observed = report["outbox_states_observed"]
            for state, count in statuses:
                if type(state) is str and state in observed:
                    observed[state] = int(count)
                else:
                    report["unrecognized_outbox_states"] += int(count)
                report["outbox_rows_observed"] += int(count)
            report["local_observation"] = (
                "OUTBOX_UNCERTAIN_LOCALLY" if observed["UNCERTAIN"]
                else "OUTBOX_UNKNOWN_STATE_LOCALLY" if report["unrecognized_outbox_states"]
                else "OUTBOX_PRESENT_LOCAL_ONLY"
            )
            return report
    except (sqlite3.Error, OSError, ValueError, TypeError, RuntimeError):
        report["local_observation"] = "DATABASE_READ_UNVERIFIABLE"
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="AION P0 H0 LAB: read-only SQLite first-effect posture; always BLOCKED")
    parser.add_argument("database", help="Path to a local SQLite database (NO credentials/PII)")
    args = parser.parse_args()
    result = observe_h0_sqlite_first_effect_lab(args.database)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 2  # STOP/NO-GO for any orchestration shell; never return 0/READY.


if __name__ == "__main__":
    raise SystemExit(main())
