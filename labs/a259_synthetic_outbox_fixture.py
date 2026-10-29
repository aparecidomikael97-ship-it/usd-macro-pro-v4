"""A259 *LAB-ONLY* synthetic first-attempt callback Outbox fixture.

NEVER import this class from production, deployed code, or a live adapter.
The test-only override preserves A241/A242/A243 synthetic SEND scenarios.
An arbitrary True callback is NOT authentic independent witness evidence.
This file remains in labs/, not in atlasquant_aion_execution_outbox.py.
"""
from collections.abc import Mapping

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


__all__ = ["SyntheticFirstAttemptOutboxLab"]
