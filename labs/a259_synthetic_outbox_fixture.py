"""A259 *LAB-ONLY* synthetic first-attempt callback Outbox fixture.

NEVER import this class from production, deployed code, or a live adapter.
The test-only override preserves A241/A242/A243 synthetic SEND scenarios.
An arbitrary True callback is NOT authentic independent witness evidence.
This file remains in labs/, not in atlasquant_aion_execution_outbox.py.
"""
from __future__ import annotations

from collections.abc import Mapping

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
