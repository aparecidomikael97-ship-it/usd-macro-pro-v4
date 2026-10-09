"""Fail-closed HTTP status contract for legacy authenticated GitHub writes.

A 3xx after allow_redirects=False is NOT confirmation of a successful write.
The helper is pure local response validation, not an authorization, retry,
idempotency guarantee, remote receipt or proof that a call did not execute.
"""
from __future__ import annotations

MODE_SUCCESS={
    "contents_put":frozenset((200,201)),
    "variable_post":frozenset((201,)),
    "variable_patch":frozenset((204,)),
}
# Preserve legacy compare-and-swap conflict handling on existing callers:
# HTTP 409/422 are not success; their caller must decide fail/retry behavior.
MODE_CONFLICT={
    "contents_put":frozenset((409,422)),
    "variable_post":frozenset(),
    # The existing safety rollback path conditionally creates a missing
    # disabled flag when PATCH /actions/variables/NAME returns 404.
    "variable_patch":frozenset((404,)),
}
def reject_github_write_unexpected_status(response:object,mode:str)->object:
    """Only pass documented success or caller-handled conflict/not-found.

    Disallowed 3xx, unexpected 2xx, 4xx/5xx and malformed status are
    ambiguous/FAILED, never proof of no side effect or safe-to-retry.
    """
    if type(mode) is not str or mode not in MODE_SUCCESS:
        raise ValueError("BLOCKED_GITHUB_WRITE_UNKNOWN_OPERATION")
    status=getattr(response,"status_code",None)
    if type(status) is not int or status not in (
        MODE_SUCCESS[mode] | MODE_CONFLICT[mode]
    ):
        raise ValueError("GITHUB_WRITE_OUTCOME_NOT_CONFIRMED_NO_RETRY_AUTHORITY")
    return response

__all__=["reject_github_write_unexpected_status"]
