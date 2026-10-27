"""Sanitized Twelve Data budget preflight telemetry. No authority, no retry.

A diagnostic string must never contain provider keys, GitHub tokens, exception
messages, URLs, budget counts or PII. This module makes zero I/O calls.
"""
from __future__ import annotations

STAGES = frozenset({
    "NOT_RUN", "READ_PREVIOUS_STATUS", "READ_SCANNER", "READ_CACHE",
    "BOOTSTRAP", "SUMMARY", "COMPLETE", "UNKNOWN",
})
EXCEPTION_TYPES = frozenset({
    "BudgetUnavailable", "ValueError", "TypeError", "KeyError",
    "Timeout", "ConnectionError", "HTTPError",
})


def preflight_diagnostic(stage: object, *, failed: bool, error: BaseException | None = None) -> dict[str, object]:
    """Return a strictly non-authorizing allowlist-coded observation."""
    safe_stage = stage if type(stage) is str and stage in STAGES else "UNKNOWN"
    category = (
        type(error).__name__
        if failed and error is not None and type(error).__name__ in EXCEPTION_TYPES
        else "UNCLASSIFIED" if failed else "NONE"
    )
    return {
        "state": "BLOCKED" if failed else "COMPLETED_NON_AUTHORIZING",
        "stage": safe_stage,
        "error_category": category,
        "authorizes_provider_call": False,
        "automatic_retry_allowed": False,
        "spend_authorized": False,
    }
