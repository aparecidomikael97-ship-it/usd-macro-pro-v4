"""AION V2.11 — Provenance Trust Lifecycle READINESS (replay / rotation / revocation).

This module is a *readiness* contract, not an implementation. It evaluates a
provenance evidence envelope and reports which trust-lifecycle dimensions are
still absent. Every dimension that is not explicitly configured by a trusted
authority remains fail-closed. The global state is BLOCKED until every
dimension is configured AND verified; nothing here ever auto-promotes to READY.

Guarantees (enforced by the red-team suite):
- pure functions; no I/O, no network, no persistent storage;
- no secret/key material created or read;
- no execution of external actions;
- deterministic: same input -> same output (byte-for-byte JSON);
- no implicit relationship between readiness and approval.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping
from atlasquant_aion_trusted_readiness_authority import trusted_readiness_authority_view

SCHEMA = "ATLASQUANT_AION_PROVENANCE_TRUST_LIFECYCLE_V1"

# Canonical dimension flags. All default to False (fail-closed).
DIMENSIONS = (
    "replay_policy_configured",
    "nonce_registry_available",
    "replay_window_configured",
    "signed_timestamp_policy_configured",
    "key_rotation_policy_configured",
    "revocation_registry_available",
    "compromise_recovery_policy_configured",
    "key_version_policy_configured",
    "old_key_acceptance_policy_configured",
    "execution_allowed",
)

MAX_EVIDENCE_BYTES = 65_536          # bound on serialized envelope
MAX_NONCE_BYTES = 128
MAX_KEY_ID_BYTES = 128
MAX_CLAIMS = 32
_MAX_INT = 2 ** 63 - 1

_TS_RE = None  # compiled lazily to avoid import-time cost


def _strict_pairs(pairs):
    """Reject duplicate keys in a JSON object (ambiguity is a bug)."""
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _is_str(v):
    return isinstance(v, str)


def _is_int(v):
    # bool is a subclass of int; reject it explicitly for canonical types.
    return isinstance(v, int) and not isinstance(v, bool)


def _b64url_ok(v):
    if not _is_str(v) or not v:
        return False
    if len(v) > MAX_NONCE_BYTES:
        return False
    import base64
    try:
        pad = v + "=" * (-len(v) % 4)
        base64.urlsafe_b64decode(pad.encode("ascii"))
        return True
    except Exception:
        return False


def _ts_canonical(v):
    """Return normalized RFC3339 UTC string or '' if malformed."""
    if not _is_str(v):
        return ""
    s = v.strip()
    if len(s) < 20:
        return ""
    # Accept only a strict shape: YYYY-MM-DDTHH:MM:SS(.fff)?Z
    global _TS_RE
    if _TS_RE is None:
        import re as _re
        _TS_RE = _re.compile(
            r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d{1,6})?Z$"
        )
    m = _TS_RE.match(s)
    if not m:
        return ""
    y, mo, d, hh, mm, ss = (int(m.group(i)) for i in range(1, 7))
    if not (1 <= mo <= 12 and 1 <= d <= 31 and hh < 24 and mm < 60 and ss < 60):
        return ""
    frac = m.group(7) or ""
    return f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:{ss:02d}{frac}Z"


def _canonical_digest(envelope: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(envelope), ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _check_bounds(envelope: Mapping[str, Any]) -> list[str]:
    problems = []
    try:
        size = len(json.dumps(dict(envelope), ensure_ascii=False, sort_keys=True,
                              allow_nan=False, default=str).encode("utf-8"))
    except Exception:
        size = MAX_EVIDENCE_BYTES + 1
    if size > MAX_EVIDENCE_BYTES:
        problems.append("EVIDENCE_OVERSIZED")
    nonce = envelope.get("nonce")
    if nonce is not None and not _b64url_ok(nonce):
        problems.append("NONCE_MALFORMED")
    kid = envelope.get("key_id")
    if kid is not None and (not _is_str(kid) or not kid or len(kid) > MAX_KEY_ID_BYTES):
        problems.append("KEY_ID_MALFORMED")
    claims = envelope.get("claims")
    if claims is not None:
        if not isinstance(claims, list):
            problems.append("CLAIMS_NOT_LIST")
        elif len(claims) > MAX_CLAIMS:
            problems.append("CLAIMS_OVERSIZED")
    kv = envelope.get("key_version")
    if kv is not None and not (_is_int(kv) and 0 <= kv <= _MAX_INT):
        problems.append("KEY_VERSION_NOT_CANONICAL")
    return problems


def evaluate_provenance_envelope(
    envelope: Any,
    *,
    now_ts: str,
    known_key_versions: Any = (),
    revoked_key_ids: Any = (),
) -> dict[str, Any]:
    """Evaluate one provenance evidence envelope against the readiness contract.

    `now_ts` is the authoritative evaluation time (RFC3339 UTC). It must be
    supplied by the caller; this module never reads a clock itself.
    Returns a machine-readable, deterministic report. Global state is BLOCKED
    unless every dimension is configured and every check passes.
    """
    blockers: list[str] = []

    # 0. Hostile object: must be a plain mapping with str keys.
    if not isinstance(envelope, Mapping):
        blockers.append("ENVELOPE_NOT_MAPPING")
        return _report({}, blockers, now_ts, {})
    if not all(_is_str(k) for k in envelope.keys()):
        blockers.append("ENVELOPE_KEYS_NOT_STR")
        return _report(dict(envelope), blockers, now_ts, {})

    env = {str(k): v for k, v in envelope.items()}

    # 1. Bounds / canonical types.
    blockers.extend(_check_bounds(env))

    # 2. Nonce presence + format.
    nonce = env.get("nonce")
    if nonce is None:
        blockers.append("NONCE_ABSENT")
    elif not _b64url_ok(nonce):
        blockers.append("NONCE_MALFORMED")

    # 3. Timestamp presence / canonical / future / stale.
    ts_raw = env.get("timestamp")
    ts = _ts_canonical(ts_raw)
    if ts_raw is None:
        blockers.append("TIMESTAMP_ABSENT")
    elif ts == "":
        blockers.append("TIMESTAMP_MALFORMED")
    else:
        if ts > _ts_canonical(now_ts):
            blockers.append("TIMESTAMP_FUTURE")
        # staleness requires replay_window_configured; without it we cannot
        # bound it, so we flag the missing policy rather than guess.
        if not env.get("replay_window_configured"):
            blockers.append("REPLAY_WINDOW_NOT_CONFIGURED")

    # 4. Key version presence + known.
    kv = env.get("key_version")
    if kv is None:
        blockers.append("KEY_VERSION_ABSENT")
    elif not (_is_int(kv) and 0 <= kv <= _MAX_INT):
        blockers.append("KEY_VERSION_NOT_CANONICAL")
    else:
        known = set()
        for k in (known_key_versions or ()):
            if _is_int(k) and 0 <= k <= _MAX_INT:
                known.add(k)
        if kv not in known:
            blockers.append("KEY_VERSION_UNKNOWN")

    # 5. Key id revocation: only a real registry (revoked_key_ids) counts.
    kid = env.get("key_id")
    if _is_str(kid) and kid:
        revoked = set()
        for r in (revoked_key_ids or ()):
            if _is_str(r) and r:
                revoked.add(r)
        if kid in revoked:
            blockers.append("KEY_REVOKED_BY_REGISTRY")

    # 6. Claims: rotation / revocation / compromise require authority.
    claims = env.get("claims")
    if claims is not None:
        if not isinstance(claims, list):
            blockers.append("CLAIMS_NOT_LIST")
        else:
            for i, c in enumerate(claims):
                if not isinstance(c, Mapping) or not all(_is_str(k) for k in c.keys()):
                    blockers.append(f"CLAIM_{i}_NOT_MAPPING")
                    continue
                ctype = c.get("type")
                authority = c.get("authority")
                has_authority = _is_str(authority) and bool(authority.strip())
                if ctype == "rotation" and not has_authority:
                    blockers.append("ROTATION_CLAIM_WITHOUT_AUTHORITY")
                if ctype == "revocation":
                    # A revocation claim is only meaningful with a real registry.
                    if not env.get("revocation_registry_available"):
                        blockers.append("REVOCATION_CLAIM_WITHOUT_REGISTRY")
                if ctype == "compromise_recovery":
                    if not env.get("compromise_recovery_policy_configured"):
                        blockers.append("COMPROMISE_RECOVERY_WITHOUT_POLICY")
                if ctype == "key_revoked" and not has_authority:
                    blockers.append("KEY_REVOCATION_CLAIM_UNTRUSTED")

    # 7. Dimension flags: any that are not True are blockers.
    dims = {}
    for d in DIMENSIONS:
        val = env.get(d)
        ok = val is True
        dims[d] = ok
        if not ok:
            blockers.append(f"DIMENSION_NOT_CONFIGURED:{d}")

    # 8. Replay / ordering / duplication are cross-envelope concerns handled by
    #    the evaluator state machine below; single-envelope report marks them
    #    as requiring the registry (fail-closed while absent).
    if not env.get("nonce_registry_available"):
        blockers.append("NONCE_REGISTRY_UNAVAILABLE")

    digest = _canonical_digest(env)
    report = _report(env, blockers, now_ts, dims)
    report["evidence_digest"] = digest
    return report


def _report(env, blockers, now_ts, dims) -> dict[str, Any]:
    # V2.12 separates caller-controlled lifecycle claims from canonical
    # readiness authority. The authority view ignores env and remains blocked
    # until a real authenticated trust root/binding design exists.
    authority = trusted_readiness_authority_view(env)
    unique = sorted(set(blockers) | set(authority["blockers"]))
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "blockers": unique,
        "dimensions": dims,
        "dimensions_verified": authority["authority_verified"],
        "trusted_readiness_authority": authority,
        "now_ts": _ts_canonical(now_ts) or now_ts,
        "execution_allowed": False,
        "executes_action": False,
        "creates_secret_or_key_material": False,
        "reads_persistent_storage": False,
        "network_called": False,
        "approval_implied": False,
    }


class ReplayEvaluator:
    """Deterministic, in-memory, per-evaluation replay/ordering/duplication gate.

    It holds NO persistent store: state lives only for the duration of one
    `evaluate_batch` call. Feeding the same batch twice yields the same result.
    """

    def evaluate_batch(self, envelopes: Any, *, now_ts: str,
                       known_key_versions=(), revoked_key_ids=()) -> dict[str, Any]:
        if not isinstance(envelopes, list):
            return {"schema": SCHEMA, "state": "BLOCKED",
                    "blockers": ["BATCH_NOT_LIST"], "results": [],
                    "executes_action": False}
        seen_nonce: dict[str, int] = {}
        seen_digest: dict[str, int] = {}
        last_seq: int | None = None
        results = []
        batch_blockers: set[str] = set()
        for idx, env in enumerate(envelopes):
            rep = evaluate_provenance_envelope(
                env, now_ts=now_ts,
                known_key_versions=known_key_versions,
                revoked_key_ids=revoked_key_ids,
            )
            entry = {"index": idx, "report": rep}
            # nonce duplication within the batch
            nonce = env.get("nonce") if isinstance(env, Mapping) else None
            if _is_str(nonce) and nonce:
                if nonce in seen_nonce:
                    entry["report"]["blockers"] = sorted(
                        set(entry["report"]["blockers"]) | {"NONCE_DUPLICATED"})
                    entry["report"]["state"] = "BLOCKED"
                    batch_blockers.add("NONCE_DUPLICATED")
                else:
                    seen_nonce[nonce] = idx
            # event duplication by digest
            dig = rep.get("evidence_digest")
            if dig:
                if dig in seen_digest:
                    entry["report"]["blockers"] = sorted(
                        set(entry["report"]["blockers"]) | {"EVENT_DUPLICATED"})
                    entry["report"]["state"] = "BLOCKED"
                    batch_blockers.add("EVENT_DUPLICATED")
                else:
                    seen_digest[dig] = idx
            # ordering by sequence
            seq = env.get("sequence") if isinstance(env, Mapping) else None
            if _is_int(seq):
                if last_seq is not None and seq <= last_seq:
                    entry["report"]["blockers"] = sorted(
                        set(entry["report"]["blockers"]) | {"SEQUENCE_OUT_OF_ORDER"})
                    entry["report"]["state"] = "BLOCKED"
                    batch_blockers.add("SEQUENCE_OUT_OF_ORDER")
                last_seq = seq
            results.append(entry)
        state = "READY" if not batch_blockers and all(
            r["report"]["state"] == "READY" for r in results) else "BLOCKED"
        return {
            "schema": SCHEMA,
            "state": state,
            "blockers": sorted(batch_blockers),
            "results": results,
            "executes_action": False,
            "persistent_store_used": False,
        }
