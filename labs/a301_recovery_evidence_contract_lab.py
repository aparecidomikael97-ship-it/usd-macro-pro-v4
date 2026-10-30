"""A301 recovery evidence contract LAB: fail-closed, offline, NEVER GO.

Inspect real SQLite snapshots and synthetic intent manifests in disposable
paths. Structural consistency is not authentic custody. No recovery method,
provider send, worker, deploy, native C, network, paid API, or automatic retry.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory

from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore

SCHEMA = "ATLASQUANT_AION_RECOVERY_EVIDENCE_CONTRACT_LAB_V1"
SCOPE = Scope("owner-a301", "tenant-a301", "workspace-a301")
MAX_LAB_DB_BYTES = 16 * 1024 * 1024
REQUIRED_MANIFEST_FIELDS = frozenset({
    "schema", "source_id", "generation", "conversation_id",
    "db_sha256", "db_size", "history_sha256", "intent_sha256",
    "pending_marker_sha256",
})


def _sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            block = source.read(65536)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _snapshot(path, cid):
    """Read only a bounded disposable candidate and its committed messages."""
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise ValueError("SNAPSHOT_UNAVAILABLE_OR_LINK")
    size = path.stat().st_size
    if size <= 0 or size > MAX_LAB_DB_BYTES:
        raise ValueError("SNAPSHOT_SIZE_OUT_OF_LAB_BOUNDS")
    before = _file_sha256(path)
    with closing(sqlite3.connect(str(path))) as db:
        check = db.execute("PRAGMA quick_check").fetchone()
        foreign = db.execute("PRAGMA foreign_key_check").fetchall()
        if check is None or check[0] != "ok" or foreign:
            raise ValueError("SQLITE_INTEGRITY_REJECTED")
        conversation = db.execute(
            "SELECT COUNT(*) FROM conversations WHERE id=?", (cid,),
        ).fetchone()[0]
        if conversation != 1:
            raise ValueError("CONVERSATION_NOT_FOUND")
        rows = db.execute(
            "SELECT id, seq, data FROM messages WHERE cid=? ORDER BY seq, id",
            (cid,),
        ).fetchall()
    after = _file_sha256(path)
    if before != after:
        raise ValueError("SNAPSHOT_CHANGED_DURING_READ")
    history = [[str(i), int(seq), str(data)] for i, seq, data in rows]
    return {
        "db_sha256": after,
        "db_size": size,
        "history_sha256": _sha_bytes(_canonical(history)),
        "messages": [(item[0], item[1]) for item in history],
        "quick_check": "ok",
    }


def make_lab_manifest(path, cid, intents, *, source_id, generation):
    """Self-attested fixture only; NOT evidence or a signer/verifier."""
    snapshot = _snapshot(path, cid)
    marker = Path(str(path) + ".aion-message-commit-pending")
    return {
        "schema": SCHEMA,
        "source_id": source_id,
        "generation": generation,
        "conversation_id": cid,
        "db_sha256": snapshot["db_sha256"],
        "db_size": snapshot["db_size"],
        "history_sha256": snapshot["history_sha256"],
        "intent_sha256": _sha_bytes(_canonical(intents)),
        "pending_marker_sha256": (
            _file_sha256(marker) if marker.is_file() else None
        ),
    }


def assess_recovery_candidate(
    path, cid, intents, manifest, *, expected_source_id, min_generation,
    custody_claim=None,
):
    """Never authorizes restore. All coherent claims still lack trust anchor.

    Validates local format, SQLite integrity, snapshot digest, semantic
    intent coverage, ACK uncertainty marker and monotonic generation floor.
    A caller-supplied floor is NOT off-host evidence. No signature verifier
    is integrated; a forged custody_claim is deliberately ineffective.
    """
    issues = []
    out = {
        "schema": SCHEMA,
        "research_only": True,
        "can_resume": False,
        "can_authorize_real_effect": False,
        "zero_auto_resend": True,
        "automatic_retries": 0,
        "hard_no_go": True,
        "p0_homologated": 0,
        "authenticated_native_fd": False,
        "external_witness_verified": False,
        "no_provider_worker_deploy_orders": True,
        "no_new_paid_services": True,
    }
    if type(expected_source_id) is not str or not expected_source_id:
        issues.append("EXPECTED_SOURCE_INVALID")
    if type(min_generation) is not int or min_generation < 0:
        issues.append("GENERATION_FLOOR_INVALID")
    if type(cid) is not str or not cid:
        issues.append("CONVERSATION_ID_INVALID")
    if type(manifest) is not dict or (
        not REQUIRED_MANIFEST_FIELDS.issubset(manifest)
    ):
        issues.append("MANIFEST_MISSING_OR_MALFORMED")
        manifest = {}
    else:
        if manifest["schema"] != SCHEMA:
            issues.append("MANIFEST_SCHEMA_MISMATCH")
        if manifest["source_id"] != expected_source_id:
            issues.append("SOURCE_ID_MISMATCH")
        if manifest["conversation_id"] != cid:
            issues.append("CONVERSATION_SCOPE_MISMATCH")
        epoch = manifest["generation"]
        if type(epoch) is not int or epoch < 0 or (
            type(min_generation) is int and epoch < min_generation
        ):
            issues.append("GENERATION_STALE_OR_INVALID")
        for key in ("db_sha256", "history_sha256", "intent_sha256"):
            digest = manifest[key]
            if (
                type(digest) is not str or len(digest) != 64
                or any(ch not in "0123456789abcdef" for ch in digest)
            ):
                issues.append("DIGEST_INVALID_" + key.upper())
        marker_digest = manifest["pending_marker_sha256"]
        if marker_digest is not None and (
            type(marker_digest) is not str or len(marker_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in marker_digest)
        ):
            issues.append("PENDING_MARKER_DIGEST_INVALID")
        if type(manifest["db_size"]) is not int or manifest["db_size"] <= 0:
            issues.append("DB_SIZE_INVALID")

    if type(intents) is not list or len(intents) > 1000:
        issues.append("INTENT_LEDGER_INVALID")
        intents = []
    identity_set = set()
    message_set = set()
    ledger_rows = []
    uncertain = False
    for item in intents:
        if type(item) is not dict or set(item) != {
            "intent_id", "message_id", "sequence", "ack_state",
        }:
            issues.append("INTENT_RECORD_MALFORMED")
            continue
        intent_id, msg_id = item["intent_id"], item["message_id"]
        sequence, state = item["sequence"], item["ack_state"]
        if (
            type(intent_id) is not str or not intent_id
            or type(msg_id) is not str or not msg_id
            or type(sequence) is not int or sequence <= 0
            or type(state) is not str or state not in ("ACKED", "ACK_UNKNOWN")
        ):
            issues.append("INTENT_RECORD_INVALID")
            continue
        if intent_id in identity_set or msg_id in message_set:
            issues.append("INTENT_DUPLICATE_SEMANTIC_EFFECT")
        identity_set.add(intent_id)
        message_set.add(msg_id)
        ledger_rows.append((msg_id, sequence))
        uncertain = uncertain or state == "ACK_UNKNOWN"

    marker = Path(str(path) + ".aion-message-commit-pending") if (
        isinstance(path, Path)
    ) else None
    marker_hash = None
    if marker is not None and marker.is_file() and not marker.is_symlink():
        marker_hash = _file_sha256(marker)
    if uncertain and marker_hash is None:
        issues.append("UNCERTAIN_ACK_MARKER_MISSING")
    if marker_hash is not None and not uncertain:
        issues.append("ORPHAN_PENDING_MARKER_REQUIRES_REVIEW")
    if manifest and manifest.get("pending_marker_sha256") != marker_hash:
        issues.append("PENDING_MARKER_BINDING_MISMATCH")
    if manifest and manifest.get("intent_sha256") != _sha_bytes(
        _canonical(intents)
    ):
        issues.append("INTENT_LEDGER_DIGEST_MISMATCH")

    try:
        candidate = _snapshot(path, cid)
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        issues.append("SQLITE_CANDIDATE_REJECTED:" + str(exc))
    else:
        out["sqlite_quick_check"] = candidate["quick_check"]
        out["observed_messages"] = len(candidate["messages"])
        if set(ledger_rows) != set(candidate["messages"]) or (
            len(ledger_rows) != len(candidate["messages"])
        ):
            issues.append("INTENT_LEDGER_DOES_NOT_COVER_SQLITE_HISTORY")
        if manifest:
            for key in ("db_sha256", "db_size", "history_sha256"):
                if manifest.get(key) != candidate[key]:
                    issues.append("SNAPSHOT_MISMATCH_" + key.upper())

    # No hardware key, external signature chain or trusted custodian exists
    # in this LAB. Even internally coherent evidence CANNOT resume anything.
    issues.append("INDEPENDENT_CUSTODY_NOT_AUTHENTICATED")
    out["issues"] = sorted(set(issues))
    out["locally_consistent_only"] = out["issues"] == [
        "INDEPENDENT_CUSTODY_NOT_AUTHENTICATED"
    ]
    out["faked_custody_claim_ignored"] = custody_claim is not None
    return out


def probe_recovery_manifest_matrix():
    """Real SQLite snapshots, corrupted candidates, replay and fake witness."""
    with TemporaryDirectory(prefix="a301-recovery-contract-") as root:
        root = Path(root)
        source = root / "working.db"
        old_db = root / "old-history.db"
        current_db = root / "current.db"
        store = SQLiteChatStore(source, strict_local_data_version=True)
        try:
            cid = store.create_conversation(SCOPE, "A301").id
            with closing(sqlite3.connect(str(old_db))) as dest:
                store.db.backup(dest)
            store.append_message(
                SCOPE, Message(
                    cid, "user", "committed synthetic message",
                    id="a301-message-one",
                ),
            )
            with closing(sqlite3.connect(str(current_db))) as dest:
                store.db.backup(dest)
        finally:
            store.close()

        intents = [{
            "intent_id": "semantic-a301-one",
            "message_id": "a301-message-one",
            "sequence": 1,
            "ack_state": "ACKED",
        }]
        manifest = make_lab_manifest(
            current_db, cid, intents, source_id="synthetic-host-a",
            generation=7,
        )
        def assess(db, ledger, meta, **kwargs):
            return assess_recovery_candidate(
                db, cid, ledger, meta, expected_source_id="synthetic-host-a",
                min_generation=7, **kwargs,
            )

        coherent = assess(current_db, intents, manifest)
        fake_claim = assess(
            current_db, intents, manifest,
            custody_claim={"issuer": "same-host-forged", "verified": True},
        )
        missing_intent = assess(current_db, [], manifest)
        duplicated = assess(current_db, intents + intents, manifest)
        bad_digest = dict(manifest, db_sha256="0" * 64)
        wrong_hash = assess(current_db, intents, bad_digest)
        stale = assess(current_db, intents, dict(manifest, generation=6))
        swapped_scope = assess(
            current_db, intents, dict(manifest, source_id="wrong-host"),
        )
        malformed = assess(current_db, intents, {"schema": SCHEMA})
        mutated_db = root / "mutated.db"
        shutil.copy2(current_db, mutated_db)
        with closing(sqlite3.connect(str(mutated_db))) as db:
            db.execute(
                "UPDATE messages SET data='{}' WHERE id='a301-message-one'",
            )
            db.commit()
        tampered = assess(mutated_db, intents, manifest)

        unknown_db = root / "uncertain.db"
        shutil.copy2(current_db, unknown_db)
        pending = Path(str(unknown_db) + ".aion-message-commit-pending")
        pending.write_bytes(b"A301_SYNTHETIC_ACK_UNKNOWN_NO_AUTO_RETRY\n")
        unknown_intents = [dict(intents[0], ack_state="ACK_UNKNOWN")]
        unknown_manifest = make_lab_manifest(
            unknown_db, cid, unknown_intents,
            source_id="synthetic-host-a", generation=7,
        )
        known_marker = assess(unknown_db, unknown_intents, unknown_manifest)
        detached_db = root / "relocated-without-marker.db"
        shutil.copy2(unknown_db, detached_db)
        lost_marker = assess(detached_db, unknown_intents, unknown_manifest)

        older_manifest = make_lab_manifest(
            old_db, cid, [], source_id="synthetic-host-a", generation=7,
        )
        self_consistent_rollback = assess(old_db, [], older_manifest)
        return {
            "coherent": coherent,
            "fake_claim": fake_claim,
            "missing_intent": missing_intent,
            "duplicate_intent": duplicated,
            "wrong_hash": wrong_hash,
            "stale": stale,
            "wrong_source": swapped_scope,
            "malformed": malformed,
            "tampered_db": tampered,
            "uncertain_marker_present": known_marker,
            "uncertain_marker_lost": lost_marker,
            "old_self_attested_rollback": self_consistent_rollback,
            "real_sqlite_snapshots": True,
            "no_external_effects": True,
        }


__all__ = [
    "SCHEMA", "SCOPE", "REQUIRED_MANIFEST_FIELDS",
    "make_lab_manifest", "assess_recovery_candidate",
    "probe_recovery_manifest_matrix",
]
