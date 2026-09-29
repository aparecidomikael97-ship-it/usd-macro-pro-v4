"""Explicit network I/O boundary for AION GitHub runtime adapters.

Core-facing modules call these tiny wrappers instead of importing the HTTP
client directly. The dependency stays lazy so imports remain operational when
the optional runtime transport is unavailable; actual network use still fails
closed in the caller.
"""
from __future__ import annotations

from typing import Any, Mapping


def github_get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    timeout: float = 12.0,
):
    import requests

    return requests.get(
        url,
        headers=dict(headers or {}),
        params=dict(params or {}),
        timeout=timeout,
    )


def github_put(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    json: Mapping[str, Any] | None = None,
    timeout: float = 12.0,
):
    import requests

    return requests.put(
        url,
        headers=dict(headers or {}),
        json=dict(json or {}),
        timeout=timeout,
    )


__all__ = ["github_get", "github_put"]
