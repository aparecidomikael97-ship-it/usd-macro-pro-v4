"""A323 LAB: read-only recovery reconciliation with two claimed custodians.

The caller supplies ALL alleged external references and signer pins. Even
a coherent A322 genesis, A321 signed history and local SQLite state CANNOT
prove independent custody, authorize recovery or resend provider effects.

No DDL/DML, Worker, provider, network, trusted bootstrap, deployment or retry.
"""
from contextlib import closing
from pathlib import Path
import sqlite3

from labs.a320_offline_custody_ceremony_lab import _hex64, _nonneg_int
from labs.a321_signed_high_water_fork_detection_lab import (
    verify_signed_high_water_history,
)
from labs.a322_genesis_out_of_band_handoff_lab import (
    verify_declared_genesis_handoff,
)
from labs.a317_detached_signed_intent_anchor_lab import encode, sha

SCHEMA = "ATLASQUANT_AION_A323_READ_ONLY_RECOVERY_RECONCILIATION_LAB_V1"
FIXTURE_MARKER = ".a323-synthetic-only"
FIXTURE_TEXT = "A323 DISPOSABLE SYNTHETIC RECOVERY LAB ONLY\n"
DB_NAME = "a323-synthetic.sqlite"
GENESIS_FIELDS = frozenset((
    "public_manifest", "genesis_card", "custody_copies",
))
HISTORY_FIELDS = frozenset((
    "ceremony_request", "starting_reference", "checkpoints",
    "expected_challenges", "observed_clock_epoch", "competing_reports",
    "revoked_custodian_ids",
))
LOCAL_FIELDS = frozenset((
    "root_generation", "incident_epoch", "sequence", "head_sha256",
    "intent_digest",
))


def result(status, issues, *, local_match=False, signed_match=False):
    return {
        "schema": SCHEMA, "status": status, "issues": sorted(set(issues)),
        "local_snapshot_matches_latest_claimed_head": bool(local_match),
        "claimed_signature_chain_checked": bool(signed_match),
        "research_only": True,
        "synthetic_only": True,
        "evidence_sources_independently_authenticated": False,
        "actual_custodians_independently_identified": False,
        "first_genesis_pin_authenticated_out_of_band": False,
        "high_water_off_host_authenticated": False,
        "immutable_off_host_custody_proven": False,
        "provider_effect_ack_attested": False,
        "trusted_time_proven": False,
        "semantic_exactly_once_proven": False,
        "recovery_authorized": False,
        "can_recover_or_restore": False,
        "can_authorize_real_effect": False,
        "can_resume": False, "can_resend": False,
        "can_auto_retry": False, "automatic_retries": 0,
        "zero_auto_resend": True, "hard_no_go": True,
        "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def read_disposable_local_state(db_path):
    """Only a marked, disposable SQLite DB can be read, never written."""
    if type(db_path) not in (str, Path):
        # Concrete pathlib.Path objects can be platform subclasses.
        if not isinstance(db_path, Path):
            return None, "LOCAL_FIXTURE_PATH_INVALID"
    path = Path(db_path)
    marker = path.parent / FIXTURE_MARKER
    try:
        if (not path.is_absolute()
                or path.name != DB_NAME
                or not path.parent.name.startswith("a323-lab-")
                or path.is_symlink() or path.parent.is_symlink()
                or not path.is_file() or marker.is_symlink()
                or not marker.is_file()
                or marker.read_text(encoding="utf-8") != FIXTURE_TEXT):
            return None, "LOCAL_FIXTURE_REFUSED"
        with closing(sqlite3.connect(
            path.as_uri() + "?mode=ro", uri=True, timeout=3,
        )) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute(
                "SELECT root_generation, incident_epoch, sequence, "
                "head_sha256, intent_digest FROM a323_recovery_state LIMIT 2"
            ).fetchall()
        if len(rows) != 1:
            return None, "LOCAL_SNAPSHOT_MISSING_OR_AMBIGUOUS"
        state = dict(rows[0])
        if (
            set(state) != LOCAL_FIELDS
            or not all(_nonneg_int(state[field]) for field in (
                "root_generation", "incident_epoch", "sequence"
            ))
            or not _hex64(state["head_sha256"])
            or not _hex64(state["intent_digest"])
        ):
            return None, "LOCAL_SNAPSHOT_MALFORMED"
        return state, None
    except (OSError, UnicodeError, sqlite3.Error, ValueError, TypeError):
        return None, "LOCAL_SNAPSHOT_UNREADABLE"


def verify_recovery_hold(
    *, genesis_package, history_package, local_db_path,
    incident_reopened=False, operation="OBSERVE_ONLY",
):
    """Demand A322 and A321 verification then compare actual SQLite bytes.

    This operation is intentionally a mathematical HOLD, even when all
    snapshots agree. Never infer external authority from caller-owned data.
    """
    if type(incident_reopened) is not bool or type(operation) is not str:
        return result("LAB_RECOVERY_DENIED", ["CONTROL_INPUT_INVALID"])
    if incident_reopened:
        return result("LAB_RECOVERY_DENIED", ["INCIDENT_REOPENED_FREEZE"])
    if operation != "OBSERVE_ONLY":
        return result("LAB_RECOVERY_DENIED", ["RECOVERY_OPERATION_NOT_ALLOWED"])
    if type(genesis_package) is not dict or set(genesis_package) != GENESIS_FIELDS:
        return result("LAB_RECOVERY_MISSING_EVIDENCE", ["A322_GENESIS_PACKAGE_MISSING"])
    if type(history_package) is not dict or set(history_package) != HISTORY_FIELDS:
        return result("LAB_RECOVERY_MISSING_EVIDENCE", ["A321_HISTORY_PACKAGE_MISSING"])
    try:
        genesis = verify_declared_genesis_handoff(**genesis_package)
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
        return result("LAB_RECOVERY_MISSING_EVIDENCE", ["A322_GENESIS_UNVERIFIABLE"])
    if genesis["status"] != "LAB_HANDOFF_COPIES_MATCH_UNATTESTED":
        return result("LAB_RECOVERY_MISSING_EVIDENCE", ["A322_GENESIS_VETO"])
    try:
        source_manifest = history_package["ceremony_request"][
            "transition_request"
        ]["previous_manifest"]
        if sha(encode(genesis_package["public_manifest"])) != sha(encode(source_manifest)):
            return result("LAB_RECOVERY_CONFLICT_VETO",
                          ["GENESIS_NOT_BOUND_TO_RECOVERY_HISTORY"])
        chain = verify_signed_high_water_history(**history_package)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        return result("LAB_RECOVERY_MISSING_EVIDENCE", ["A321_HISTORY_UNVERIFIABLE"])
    if chain["status"] != "LAB_CONSISTENT_SIGNED_HISTORY_NO_EXTERNAL_CUSTODY":
        return result("LAB_RECOVERY_CONFLICT_VETO", ["A321_SIGNED_HISTORY_VETO"])
    try:
        last = history_package["checkpoints"][-1][0]
        expected = {
            "root_generation": last["root_generation"],
            "incident_epoch": last["incident_epoch"],
            "sequence": last["sequence"],
            "head_sha256": last["head_sha256"],
            "intent_digest": last["intent_digest"],
        }
    except (IndexError, TypeError, KeyError):
        return result("LAB_RECOVERY_MISSING_EVIDENCE",
                      ["LATEST_SIGNED_HEAD_MISSING"])
    local, local_problem = read_disposable_local_state(local_db_path)
    if local_problem is not None:
        return result("LAB_RECOVERY_MISSING_EVIDENCE",
                      [local_problem], signed_match=True)
    issues = []
    if local["sequence"] < expected["sequence"]:
        issues.append("LOCAL_ROLLBACK_SEQUENCE")
    if local["sequence"] > expected["sequence"]:
        issues.append("LOCAL_AHEAD_OF_CLAIMED_WITNESSES")
    for field in (
        "root_generation", "incident_epoch", "head_sha256", "intent_digest",
    ):
        if local[field] != expected[field]:
            issues.append("LOCAL_" + field.upper() + "_CONFLICT")
    if issues:
        return result("LAB_RECOVERY_CONFLICT_VETO",
                      issues, signed_match=True)
    return result("LAB_RECOVERY_CONSISTENT_HOLD_NO_EXTERNAL_AUTHORITY",
                  [], signed_match=True, local_match=True)


__all__ = [
    "SCHEMA", "FIXTURE_MARKER", "FIXTURE_TEXT", "DB_NAME", "GENESIS_FIELDS",
    "HISTORY_FIELDS", "LOCAL_FIELDS", "read_disposable_local_state",
    "verify_recovery_hold",
]
