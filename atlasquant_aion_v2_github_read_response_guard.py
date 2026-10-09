"""Fail closed on non-content status from authenticated GitHub REST GET.

No HTTP/credentials used here. Requests' raise_for_status() does not reject
3xx; a synthetic redirect response with JSON is never GitHub file content.
"""
from __future__ import annotations

ALLOWED_CONTENT_GET_STATUSES=frozenset((200,404))

def reject_github_read_unexpected_status(response:object)->object:
    """Pass only 200 (content) and 404 (missing/create preflight) unchanged."""
    code=getattr(response,"status_code",None)
    if type(code) is not int or code not in ALLOWED_CONTENT_GET_STATUSES:
        raise ValueError("BLOCKED_GITHUB_GET_UNEXPECTED_STATUS")
    return response

__all__=["reject_github_read_unexpected_status"]
