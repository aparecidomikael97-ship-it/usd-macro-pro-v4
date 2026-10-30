"""A317 LAB: detached Ed25519 intent snapshot cross-check against SQLite.

The key, prior head, clock and challenge here are CALLER-SUPPLIED, not
independently obtained or attested. Real cryptographic math, synthetic
signer/fixture. A pass NEVER proves off-host authority, P0-3, or GO.
No outbound I/O, Worker, deploy, operation, provider, paid service or retry.
"""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from contextlib import closing

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aion_chat.models import Scope

SCHEMA = "ATLASQUANT_AION_A317_DETACHED_INTENT_SNAPSHOT_LAB_V1"
DOMAIN = b"ATLASQUANT_AION_A317_DETACHED_INTENT_SNAPSHOT_LAB_V1\x00"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX128 = re.compile(r"[0-9a-f]{128}\Z")
ID = re.compile(r"[A-Za-z0-9._-]{1,80}\Z")
SIGNED_FIELDS = frozenset((
    "schema", "witness_id", "owner", "tenant", "workspace", "intent_id",
    "payload_digest", "conversation_id", "message_id", "sequence",
    "message_data_sha256", "receipt_row_sha256", "incident_epoch",
    "chain_sequence", "previous_anchor_sha256", "challenge_nonce",
    "issued_at", "expires_at",
))
ALL_FIELDS = SIGNED_FIELDS | {"signature_hex"}
SNAPSHOT_FIELDS = frozenset((
    "owner", "tenant", "workspace", "intent_id", "payload_digest",
    "conversation_id", "message_id", "sequence",
    "message_data_sha256", "receipt_row_sha256",
))
MAX_CLOCK_WINDOW = 900
FIXTURE_MARKER = ".a315-synthetic-only"
FIXTURE_CONTENT = "A315 DISPOSABLE SYNTHETIC LAB ONLY\n"


def encode(data):
    """Strict deterministic bytes, no float/NaN ambiguity."""
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def signing_bytes(receipt):
    return DOMAIN + encode({field: receipt[field] for field in sorted(SIGNED_FIELDS)})


def snapshot_from_rows(receipt, message):
    """Project one A315 local receipt and its canonical A316 message JSON."""
    row = {
        "owner": receipt["owner"], "tenant": receipt["tenant"],
        "workspace": receipt["workspace"], "intent_id": receipt["intent_id"],
        "payload_digest": receipt["payload_digest"],
        "conversation_id": receipt["cid"],
        "message_id": receipt["message_id"],
        "sequence": receipt["seq"],
    }
    row["receipt_row_sha256"] = sha(encode(row))
    row["message_data_sha256"] = sha(message["data"].encode("utf-8"))
    return row


def read_fixture_snapshot(db_path, scope, intent_id):
    """Read ONLY a marked synthetic SQLite fixture; never open operational DB."""
    if (not isinstance(db_path, (str, Path)) or not isinstance(scope, Scope)
            or type(intent_id) is not str or not ID.fullmatch(intent_id)):
        return None, "LAB_FIXTURE_OR_INTENT_INVALID"
    path = Path(db_path)
    folder = path.parent
    marker = folder / FIXTURE_MARKER
    try:
        if (not path.is_absolute() or not folder.name.startswith("a315-lab-")
                or folder.is_symlink() or path.is_symlink()
                or not path.is_file() or not marker.is_file()
                or marker.is_symlink()
                or marker.read_text(encoding="utf-8") != FIXTURE_CONTENT):
            return None, "LAB_FIXTURE_REFUSED"
        # mode=ro doesn't authorize any restore, DDL or write transaction.
        uri = path.as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=3)) as conn:
            conn.row_factory = sqlite3.Row
            receipt = conn.execute(
                "SELECT owner,tenant,workspace,intent_id,payload_digest,"
                "cid,message_id,seq FROM a315_local_intent_receipts "
                "WHERE owner=? AND tenant=? AND workspace=? AND intent_id=?",
                (scope.owner_id, scope.tenant_id, scope.workspace_id,
                 intent_id),
            ).fetchone()
            if receipt is None:
                return None, "LOCAL_RECEIPT_MISSING"
            message = conn.execute(
                "SELECT cid,seq,content,data FROM messages WHERE id=?",
                (receipt["message_id"],),
            ).fetchone()
            if message is None:
                return None, "LOCAL_MESSAGE_MISSING"
            data = json.loads(message["data"])
            trace = data.get("metadata")
            if (type(trace) is not dict
                    or trace.get("a316_semantic_intent_id") != intent_id
                    or trace.get("a316_payload_digest") != receipt["payload_digest"]
                    or data.get("conversation_id") != message["cid"]
                    or data.get("content") != message["content"]
                    or data.get("sequence") != message["seq"]
                    or message["cid"] != receipt["cid"]
                    or message["seq"] != receipt["seq"]):
                return None, "LOCAL_RECEIPT_MESSAGE_DIVERGED"
            return snapshot_from_rows(receipt, message), None
    except (OSError, sqlite3.DatabaseError, ValueError, TypeError, KeyError,
            UnicodeError):
        return None, "LOCAL_READ_UNCERTAIN"


def outcome(status, issues, **data):
    return {
        "schema": SCHEMA, "status": status, "issues": sorted(set(issues)),
        "research_only": True, "synthetic_only": True,
        "cryptographic_signature_valid": bool(data.get("signature", False)),
        "signed_snapshot_mathematically_coherent": bool(data.get("structural", False)),
        "local_snapshot_matches_signed_witness": bool(data.get("local_match", False)),
        "local_rollback_or_tamper_observed": bool(data.get("local_tamper", False)),
        "independently_pinned_witness_identity": False,
        "off_host_head_authenticated": False,
        "external_custody_proven": False,
        "trusted_clock_proven": False,
        "provider_effect_verified": False,
        "semantic_exactly_once_proven": False,
        "can_authorize_real_effect": False, "can_resume": False,
        "can_resend": False, "can_auto_retry": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def assess_detached_intent_anchor(
    *, db_path, scope, intent_id, signed_anchor, pinned_witness_key,
    previous_head, challenge_nonce, now_epoch, expected_incident_epoch,
):
    """Require cryptographic witness binding *and* compare current local bytes.

    Mathematical validation does not mean the witness originates off host.
    Caller can forge the pin, previous head, nonce, time and synthetic key.
    This function can ONLY veto; it never authorizes a real effect.
    """
    issues = set()
    if type(signed_anchor) is not dict or set(signed_anchor) != ALL_FIELDS:
        return outcome("LAB_WITNESS_INVALID_VETO", ["ANCHOR_FIELDS_INVALID"])
    if (type(pinned_witness_key) is not bytes
            or len(pinned_witness_key) != 32):
        issues.add("WITNESS_PIN_INVALID")
    if (type(scope) is not Scope or type(intent_id) is not str
            or ID.fullmatch(intent_id) is None):
        issues.add("INTENT_SCOPE_INVALID")
    if (type(previous_head) is not dict
            or set(previous_head) != {"sequence", "sha256"}
            or type(previous_head["sequence"]) is not int
            or previous_head["sequence"] < 0
            or type(previous_head["sha256"]) is not str
            or not HEX64.fullmatch(previous_head["sha256"])):
        issues.add("ANCHOR_HEAD_UNVERIFIED_OR_INVALID")
    if (type(challenge_nonce) is not str
            or not HEX64.fullmatch(challenge_nonce)):
        issues.add("CHALLENGE_NONCE_INVALID")
    if (type(now_epoch) is not int or now_epoch < 0
            or type(expected_incident_epoch) is not int
            or expected_incident_epoch < 0):
        issues.add("EPOCH_OR_TIME_INVALID")
    a = signed_anchor
    for field in ("witness_id", "owner", "tenant", "workspace",
                  "intent_id", "conversation_id", "message_id"):
        if type(a[field]) is not str or not ID.fullmatch(a[field]):
            issues.add("ANCHOR_IDENTIFIER_INVALID")
    for field in ("payload_digest", "message_data_sha256",
                  "receipt_row_sha256", "previous_anchor_sha256",
                  "challenge_nonce"):
        if type(a[field]) is not str or not HEX64.fullmatch(a[field]):
            issues.add("ANCHOR_HASH_INVALID")
    for field in ("sequence", "incident_epoch", "chain_sequence",
                  "issued_at", "expires_at"):
        if type(a[field]) is not int or a[field] < 0:
            issues.add("ANCHOR_NUMBER_INVALID")
    if type(a["signature_hex"]) is not str or not HEX128.fullmatch(a["signature_hex"]):
        issues.add("SIGNATURE_FORMAT_INVALID")
    if a["schema"] != SCHEMA:
        issues.add("ANCHOR_SCHEMA_INVALID")
    if type(scope) is Scope and (
        a["owner"], a["tenant"], a["workspace"], a["intent_id"]
    ) != (
        scope.owner_id, scope.tenant_id, scope.workspace_id, intent_id
    ):
        issues.add("SCOPE_INTENT_BINDING_MISMATCH")
    if (type(previous_head) is dict
            and set(previous_head) == {"sequence", "sha256"}
            and type(previous_head["sequence"]) is int
            and type(a["chain_sequence"]) is int):
        if (a["chain_sequence"] != previous_head["sequence"] + 1
                or a["previous_anchor_sha256"] != previous_head["sha256"]):
            issues.add("CHAIN_ROLLBACK_OR_REPLAY")
    if a["challenge_nonce"] != challenge_nonce:
        issues.add("CHALLENGE_REUSED_OR_MISMATCH")
    if a["incident_epoch"] != expected_incident_epoch:
        issues.add("INCIDENT_EPOCH_MISMATCH")
    if (type(a["issued_at"]) is int and type(a["expires_at"]) is int
            and type(now_epoch) is int):
        if (a["expires_at"] <= a["issued_at"]
                or a["expires_at"] - a["issued_at"] > MAX_CLOCK_WINDOW
                or now_epoch < a["issued_at"]
                or now_epoch >= a["expires_at"]):
            issues.add("ANCHOR_STALE_OR_FUTURE")
    valid_sig = False
    if ("SIGNATURE_FORMAT_INVALID" not in issues
            and "WITNESS_PIN_INVALID" not in issues):
        try:
            Ed25519PublicKey.from_public_bytes(pinned_witness_key).verify(
                bytes.fromhex(a["signature_hex"]), signing_bytes(a)
            )
            valid_sig = True
        except (InvalidSignature, ValueError, TypeError, KeyError, OverflowError):
            issues.add("SIGNATURE_NOT_VALID")
    if issues:
        return outcome("LAB_WITNESS_INVALID_VETO", issues,
                       signature=valid_sig)
    local, reason = read_fixture_snapshot(db_path, scope, intent_id)
    if reason is not None:
        return outcome("LAB_LOCAL_DIVERGENCE_VETO", [reason],
                       signature=True, structural=True, local_tamper=True)
    mismatch = sorted(field for field in SNAPSHOT_FIELDS
                      if local[field] != a[field])
    if mismatch:
        return outcome("LAB_LOCAL_DIVERGENCE_VETO",
                       ["SNAPSHOT_FIELD_MISMATCH:" + field for field in mismatch],
                       signature=True, structural=True, local_tamper=True)
    return outcome("LAB_SNAPSHOT_MATCH_NO_EXTERNAL_AUTHORITY", [],
                   signature=True, structural=True, local_match=True)
