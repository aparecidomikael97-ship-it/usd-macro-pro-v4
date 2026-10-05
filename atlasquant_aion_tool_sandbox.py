"""Pure sandbox/egress policy for AION tools.

No socket is opened here. A future connector runtime must resolve destination
addresses outside the model and submit every resolved IP to this guard before
a credential may be resolved or an outbound connection may be attempted.
"""
from __future__ import annotations

import ipaddress
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

SCHEMA = "ATLASQUANT_AION_TOOL_SANDBOX_V1"
LOCAL_PROFILE = "LOCAL_NO_EGRESS"
PROXY_PROFILE = "THIRD_PARTY_EGRESS_PROXY"
_ALLOWED_PROFILES = frozenset({LOCAL_PROFILE, PROXY_PROFILE})
_HOST = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _hosts(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    out = []
    for raw in values[:100]:
        host = _clean(raw, 253).lower().rstrip(".")
        if host and host not in out:
            out.append(host)
    return out


def _public_ip(raw: Any) -> str:
    text = _clean(raw, 80)
    try:
        address = ipaddress.ip_address(text)
    except ValueError as exc:
        raise ValueError("resolved address must be a literal IP") from exc
    if not address.is_global:
        raise PermissionError("resolved address is not globally routable")
    return str(address)


def sandbox_contract_issues(tool: Mapping[str, Any]) -> list[str]:
    item = dict(tool or {})
    profile = _clean(item.get("sandbox_profile"), 60).upper()
    allowlist = _hosts(item.get("egress_allowlist"))
    connector_id = _clean(item.get("connector_id"), 96)
    credential_ref = _clean(item.get("credential_ref"), 96)
    third_party = item.get("third_party") is True
    issues = []

    if profile not in _ALLOWED_PROFILES:
        issues.append("SANDBOX_PROFILE_UNAPPROVED")
        return issues

    if profile == LOCAL_PROFILE:
        if connector_id:
            issues.append("LOCAL_SANDBOX_HAS_CONNECTOR")
        if allowlist:
            issues.append("LOCAL_SANDBOX_HAS_EGRESS")
        if credential_ref:
            issues.append("LOCAL_SANDBOX_HAS_CREDENTIAL")
        if third_party:
            issues.append("LOCAL_SANDBOX_MARKED_THIRD_PARTY")
    else:
        if not connector_id:
            issues.append("EGRESS_PROXY_CONNECTOR_REQUIRED")
        if not third_party:
            issues.append("THIRD_PARTY_FLAG_REQUIRED")
        if not allowlist:
            issues.append("EGRESS_ALLOWLIST_REQUIRED")
        for host in allowlist:
            if host == "*" or host.startswith("*."):
                issues.append("EGRESS_WILDCARD_FORBIDDEN")
            if not _HOST.fullmatch(host):
                issues.append("EGRESS_HOST_INVALID")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                issues.append("EGRESS_DIRECT_IP_FORBIDDEN")
    return list(dict.fromkeys(issues))


def sandbox_plan(tool: Mapping[str, Any]) -> dict[str, Any]:
    issues = sandbox_contract_issues(tool)
    profile = _clean(tool.get("sandbox_profile"), 60).upper()
    return {
        "schema": SCHEMA,
        "state": "READY" if not issues else "BLOCK",
        "profile": profile,
        "issues": issues,
        "filesystem_write": False,
        "subprocess": False,
        "raw_socket": False,
        "credential_visible_to_model": False,
        "direct_network": False,
        "egress_proxy_required": profile == PROXY_PROFILE,
        "egress_allowlist": _hosts(tool.get("egress_allowlist")),
        "executes_action": False,
    }


def validate_egress_request(
    tool: Mapping[str, Any],
    url: Any,
    resolved_ips: Sequence[Any] | None,
) -> dict[str, Any]:
    """Validate an HTTPS destination and every post-resolution address."""
    plan = sandbox_plan(tool)
    if plan["state"] != "READY":
        raise PermissionError("tool sandbox contract is not approved")
    if plan["profile"] != PROXY_PROFILE:
        raise PermissionError("tool has no egress capability")

    raw_url = _clean(url, 2048)
    parsed = urlsplit(raw_url)
    if parsed.scheme.lower() != "https":
        raise PermissionError("only HTTPS egress is allowed")
    if parsed.username is not None or parsed.password is not None:
        raise PermissionError("URL userinfo is forbidden")
    if parsed.fragment:
        raise PermissionError("URL fragments are forbidden at the egress proxy")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or not _HOST.fullmatch(host):
        raise PermissionError("invalid egress hostname")
    if host.replace(".", "").isdigit():
        raise PermissionError("numeric host aliases are forbidden")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise PermissionError("direct IP destinations are forbidden")
    try:
        port = parsed.port
    except ValueError as exc:
        raise PermissionError("invalid destination port") from exc
    if port not in (None, 443):
        raise PermissionError("only HTTPS port 443 is allowed")
    if host not in plan["egress_allowlist"]:
        raise PermissionError("destination is not in the tool allowlist")

    supplied = list(resolved_ips or [])
    if not supplied:
        raise PermissionError("post-resolution IP proof required")
    verified = []
    for raw in supplied[:16]:
        value = _public_ip(raw)
        if value not in verified:
            verified.append(value)
    if len(supplied) > 16:
        raise ValueError("too many resolved addresses")

    return {
        "schema": SCHEMA,
        "state": "ALLOW",
        "tool_id": _clean(tool.get("tool_id"), 96),
        "host": host,
        "port": 443,
        "resolved_ips": verified,
        "dns_rebinding_checked": True,
        "private_network_blocked": True,
        "metadata_service_blocked": True,
        "credential_visible_to_model": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "LOCAL_PROFILE",
    "PROXY_PROFILE",
    "sandbox_contract_issues",
    "sandbox_plan",
    "validate_egress_request",
]
