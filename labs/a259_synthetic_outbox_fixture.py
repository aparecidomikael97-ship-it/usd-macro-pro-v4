"""A259 *LAB-ONLY* synthetic first-attempt callback Outbox fixture.

NEVER import this class from production, deployed code, or a live adapter.
The test-only override preserves A241/A242/A243 synthetic SEND scenarios.
An arbitrary True callback is NOT authentic independent witness evidence.
This file remains in labs/, not in atlasquant_aion_execution_outbox.py.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from atlasquant_aion_execution_outbox import _token, _iso


from atlasquant_aion_execution_outbox import _clean, _utc, _mapping

from atlasquant_aion_execution_outbox import ExecutionOutbox


class SyntheticFirstAttemptOutboxLab(ExecutionOutbox):
    """Unsafe by design: strictly offline test fixture, not an authority."""

    LAB_ONLY_UNTRUSTED_CALLBACK = True

    def __init__(self, store, scope, *, first_attempt_guard=None):
        if first_attempt_guard is not None and not callable(first_attempt_guard):
            raise TypeError("callable synthetic first_attempt_guard required")
        self._lab_first_attempt_guard = first_attempt_guard
        super().__init__(store, scope)

    def _reserved_first_attempt(self, intent: Mapping) -> bool:
        if self._lab_first_attempt_guard is None:
            return False
        try:
            # Preserves the A242/A243 synthetic test fixture, not real proof.
            return self._lab_first_attempt_guard(dict(intent)) is True
        except Exception:
            return False


    def dispatch_claimed(
        self,
        idempotency_key: Any,
        *,
        worker_id: Any,
        authorize: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        adapter: Any,
        cumulative_authority_guard: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
        now: Any | None = None,
    ) -> dict[str, Any]:
        """Dispatch one claimed intent; uncertain outcomes require reconciliation."""
        key = _clean(idempotency_key, 64)
        worker = _token(worker_id, "worker_id")
        now_dt = _utc(now)
        intent = self.get(key)
        if intent["state"] != "CLAIMED":
            raise ValueError("intent must be CLAIMED before dispatch")
        if intent["lease_owner"] != worker:
            raise PermissionError("worker does not own claim")
        if not intent["lease_until"] or now_dt >= _utc(intent["lease_until"]):
            raise TimeoutError("claim lease expired before dispatch")

        allowed, blocked_state, auth = self._authorization_gate(intent, authorize, now_dt)
        if not allowed:
            return self._set_blocked(
                key, blocked_state, auth.get("reason", blocked_state),
                observed=intent,
            )

        decision = _mapping(intent.get("decision"))
        budget_ref = _clean(decision.get("authority_budget_ref"), 128)
        if budget_ref:
            if not callable(cumulative_authority_guard):
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_GUARD_REQUIRED",
                    observed=intent,
                )
            try:
                budget = _mapping(cumulative_authority_guard(dict(decision)))
            except Exception:
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_GUARD_FAILED",
                    observed=intent,
                )
            if budget.get("allowed") is not True:
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    _clean(budget.get("reason") or "CUMULATIVE_AUTHORITY_BUDGET_EXCEEDED", 240),
                    observed=intent,
                )
            if _clean(budget.get("authority_budget_ref"), 128) != budget_ref:
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_BUDGET_REF_MISMATCH",
                    observed=intent,
                )
            if _clean(budget.get("transaction_id"), 128) != _clean(decision.get("transaction_id"), 128):
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_TRANSACTION_MISMATCH",
                    observed=intent,
                )

        # A266: DO NOT inspect adapter.send here. A hostile Python object
        # may perform effects merely from a property getter or __getattribute__.
        # The ordinary Outbox never obtains an independently reserved first
        # attempt, so adapter attributes must remain untouched on that path.
        # Persist ambiguity BEFORE crossing the external boundary. If the process
        # dies after this commit, restart must reconcile and must not blind-retry.
        #
        # A202: this UPDATE is the atomic dispatch admission CAS, not just a
        # state annotation. Two calls can read the same CLAIMED row with the
        # same lease owner on separate SQLite connections. Only the call
        # that transitions exactly ONE row may enter adapter.send. A failed
        # transition MUST be fail-closed: never send, retry, reauthorize, or
        # reset UNCERTAIN. Also bind the lease snapshot from the initial read.
        with self.db:
            cursor = self.db.execute(
                """UPDATE action_outbox
                   SET state='UNCERTAIN',dispatch_started_at=?,last_error='FIRST_ATTEMPT_WITNESS_PENDING'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='CLAIMED' AND lease_owner=? AND lease_until=?""",
                (
                    _iso(now_dt), key, *self._scope_args(),
                    worker, intent["lease_until"],
                ),
            )
            dispatch_admitted = cursor.rowcount == 1
        if not dispatch_admitted:
            # The other contender may now be UNCERTAIN, SENT or CONFIRMED.
            # This local result is NOT proof of an external effect or absence.
            return {
                **self.get(key),
                "dispatch_state": "NOT_DISPATCHED_STATE_CHANGED",
            }

        # A242: the write-ahead UNKNOWN is durable BEFORE any possible
        # reservation request. Lost witness ACK means NO SEND and NO RETRY.
        self._require_bound_store()
        reservation_ok = self._reserved_first_attempt(intent)
        if not reservation_ok:
            with self.db:
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',
                           last_error='FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN' AND lease_owner=? AND lease_until=?
                         AND dispatch_started_at=?""",
                    (
                        key, *self._scope_args(), worker,
                        intent["lease_until"], _iso(now_dt),
                    ),
                )
                denied = cursor.rowcount == 1
            return {
                **self.get(key),
                "dispatch_state": (
                    "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED" if denied
                    else "NOT_DISPATCHED_STATE_CHANGED"
                ),
            }

        # A positive response is STILL untrusted without external root
        # provenance. CAS prevents a delayed guard from authorizing SEND
        # against a newer lease/state/reconciliation.
        with self.db:
            cursor = self.db.execute(
                """UPDATE action_outbox
                   SET last_error='FIRST_ATTEMPT_RESERVATION_LAB_UNVERIFIED'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='UNCERTAIN' AND lease_owner=? AND lease_until=?
                     AND dispatch_started_at=?""",
                (
                    key, *self._scope_args(), worker,
                    intent["lease_until"], _iso(now_dt),
                ),
            )
            reservation_admitted = cursor.rowcount == 1
        if not reservation_admitted:
            return {
                **self.get(key),
                "dispatch_state": "NOT_DISPATCHED_STATE_CHANGED",
            }

        # Recheck just before the potentially irreversible adapter boundary.
        # Pathname comparison is local and does not attest the SQLite FD.
        self._require_bound_store()
        try:
            # A266: resolve the potentially effectful adapter attribute ONLY
            # AFTER the durable attempt marker, independent reservation gate,
            # and exact lease CAS have all succeeded. Currently that positive
            # path is available ONLY in deliberately synthetic LAB subclasses.
            send = getattr(adapter, "send", None)
            if not callable(send):
                raise TypeError("adapter.send required")
            result = _mapping(send(dict(intent["decision"]), key))
        except Exception as exc:
            # A206: a slow SEND callback must not undo a newer reconciliation
            # which already stored a matching confirmed effect. This is
            # a CAS over the exact write-ahead UNCERTAIN dispatch attempt.
            with self.db:
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN' AND lease_owner=?
                         AND lease_until=? AND dispatch_started_at=?""",
                    (
                        "SEND_RESULT_UNKNOWN:" + type(exc).__name__,
                        key, *self._scope_args(), worker,
                        intent["lease_until"], _iso(now_dt),
                    ),
                )
                updated = cursor.rowcount == 1
            out = self.get(key)
            return {
                **out,
                "dispatch_state": (
                    "UNCERTAIN_RECONCILE_REQUIRED" if updated
                    else "NOT_DISPATCHED_STATE_CHANGED"
                ),
            }

        if result.get("accepted") is not True:
            # A205 H0: a caller-controlled adapter's rejection, including
            # retryable=True, is NOT external proof of NO_EFFECT_FENCED.
            # send() has already crossed the potential effect boundary.
            # Never mark this attempt RETRY or conclusively FAILED merely
            # because its caller claims rejection. Preserve UNCERTAIN.
            with self.db:
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',
                           last_error='ADAPTER_REJECTION_UNVERIFIED'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN' AND lease_owner=? AND lease_until=?
                         AND dispatch_started_at=?""",
                    (
                        key, *self._scope_args(), worker,
                        intent["lease_until"], _iso(now_dt),
                    ),
                )
                updated = cursor.rowcount == 1
            out = self.get(key)
            return {
                **out,
                "dispatch_state": (
                    "UNCERTAIN_RECONCILE_REQUIRED" if updated
                    else "NOT_DISPATCHED_STATE_CHANGED"
                ),
            }

        effect_ref = _clean(result.get("effect_ref"), 128)
        if result.get("confirmed") is True:
            # A213: this callback can lie. Preserve the write-ahead
            # UNCERTAIN state, do not record its fake effect_ref and never
            # call _confirm. Row-level CAS protects a newer reconciliation
            # from a delayed self-asserted SEND outcome.
            with self.db:
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',
                           last_error='UNTRUSTED_SEND_POSITIVE_NO_EXTERNAL_RECEIPT'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN' AND lease_owner=? AND lease_until=?
                         AND dispatch_started_at=?""",
                    (
                        key, *self._scope_args(), worker,
                        intent["lease_until"], _iso(now_dt),
                    ),
                )
                updated = cursor.rowcount == 1
            out = self.get(key)
            return {
                **out,
                "dispatch_state": (
                    "UNTRUSTED_POSITIVE_RECONCILE_REQUIRED" if updated
                    else "NOT_DISPATCHED_STATE_CHANGED"
                ),
            }

        # A206: do not regress from a newer CONFIRMED to an old
        # "accepted, not yet confirmed" reply. No re-send and no reset.
        with self.db:
            cursor = self.db.execute(
                """UPDATE action_outbox
                   SET state='SENT',sent_at=?,effect_ref=?,lease_owner='',lease_until='',last_error=''
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='UNCERTAIN' AND lease_owner=?
                     AND lease_until=? AND dispatch_started_at=?""",
                (
                    _iso(now_dt), effect_ref, key, *self._scope_args(),
                    worker, intent["lease_until"], _iso(now_dt),
                ),
            )
            updated = cursor.rowcount == 1
        out = self.get(key)
        return {
            **out,
            "dispatch_state": (
                "SENT_RECONCILE_REQUIRED" if updated
                else "NOT_DISPATCHED_STATE_CHANGED"
            ),
        }

    def reconcile(
        self,
        idempotency_key: Any,
        *,
        adapter: Any,
        authorize: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        now: Any | None = None,
    ) -> dict[str, Any]:
        """Resolve SENT/UNCERTAIN without ever blind-resending an ambiguous effect."""
        key = _clean(idempotency_key, 64)
        now_dt = _utc(now)
        intent = self.get(key)
        if intent["state"] not in {"UNCERTAIN", "SENT"}:
            raise ValueError("only SENT or UNCERTAIN intents require reconciliation")
        reconcile = getattr(adapter, "reconcile", None)
        if not callable(reconcile):
            raise TypeError("adapter.reconcile required")

        result = _mapping(reconcile(key, dict(intent["decision"])))
        if result.get("found") is True and result.get("confirmed") is True:
            # A213: even a "found" callback can forge effect_ref. Never
            # publish CONFIRMED or action_effects on adapter testimony.
            # Bind this audit marker to the exact observed snapshot, so a
            # stale callback cannot overwrite newer state/error evidence.
            with self.db:
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET lease_owner='',lease_until='',
                           last_error='UNTRUSTED_RECONCILE_POSITIVE_NO_EXTERNAL_RECEIPT'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state=? AND attempts=? AND lease_owner=? AND lease_until=?
                         AND dispatch_started_at=? AND sent_at=?
                         AND confirmed_at=? AND effect_ref=? AND last_error=?""",
                    (
                        key, *self._scope_args(),
                        intent["state"], intent["attempts"],
                        intent["lease_owner"], intent["lease_until"],
                        intent["dispatch_started_at"], intent["sent_at"],
                        intent["confirmed_at"], intent["effect_ref"], intent["last_error"],
                    ),
                )
                updated = cursor.rowcount == 1
            out = self.get(key)
            return {
                **out,
                "reconcile_state": (
                    "UNTRUSTED_POSITIVE_HARD_NO_GO" if updated
                    else "NOT_RECONCILED_STATE_CHANGED"
                ),
            }

        if result.get("found") is False and result.get("authoritative_absence") is True:
            # A205 H0: this boolean is supplied by an injected callback. It
            # is NOT a cryptographically and causally independently fenced
            # NO_EFFECT receipt. Even a fresh absence claim cannot justify
            # RETRY after a potentially irreversible SEND. No host-local
            # token/flag/caller assertion may turn this into a SEND license.
            latest = self.get(key)
            return {
                **latest,
                "reconcile_state": (
                    "ABSENCE_UNVERIFIED_HARD_NO_GO"
                    if latest["state"] in {"UNCERTAIN", "SENT"}
                    else "NOT_RECONCILED_STATE_CHANGED"
                ),
            }

            # Previous local-only simulated approval/retry flow retained
            # below for historical audit, deliberately unreachable until
            # externally independent NO_EFFECT_FENCED custody is proven.
            allowed, blocked_state, auth = self._authorization_gate(intent, authorize, now_dt)
            if not allowed:
                out = self._set_blocked(
                    key,
                    blocked_state,
                    auth.get("reason", blocked_state),
                    observed=intent,
                )
                return {
                    **out,
                    "reconcile_state": (
                        blocked_state if out["state"] == blocked_state
                        else "NOT_RECONCILED_STATE_CHANGED"
                    ),
                }
            # A204: provider reconciliation is a potentially delayed reply.
            # Do not let a stale "absence" replace a newer CONFIRMED, SENT,
            # UNCERTAIN or re-claimed snapshot. Only a CAS winner may make
            # the particular originally observed attempt locally retryable.
            # This local CAS does NOT authenticate NO_EFFECT_FENCED evidence.
            with self.db:
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state='RETRY',lease_owner='',lease_until='',
                           last_error='AUTHORITATIVE_ABSENCE_CONFIRMED'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state=? AND attempts=? AND lease_owner=?
                         AND lease_until=? AND dispatch_started_at=?
                         AND sent_at=? AND confirmed_at=? AND effect_ref=?""",
                    (
                        key, *self._scope_args(),
                        intent["state"], intent["attempts"],
                        intent["lease_owner"], intent["lease_until"],
                        intent["dispatch_started_at"], intent["sent_at"],
                        intent["confirmed_at"], intent["effect_ref"],
                    ),
                )
                transitioned = cursor.rowcount == 1
            out = self.get(key)
            return {
                **out,
                "reconcile_state": (
                    "RETRY" if transitioned
                    else "NOT_RECONCILED_STATE_CHANGED"
                ),
            }

        return {**intent, "reconcile_state": "STILL_UNCERTAIN"}


__all__ = ["SyntheticFirstAttemptOutboxLab"]
