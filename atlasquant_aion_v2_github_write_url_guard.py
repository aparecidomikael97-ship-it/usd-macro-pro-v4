"""Fail-closed local GitHub REST WRITE URL syntax guard (no network).

This is NOT authorization to write, not a credential/owner check, and not
proof of DNS, TLS, proxy safety or remote repo permission. Current callers
must additionally set requests allow_redirects=False.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

SAFE_SEGMENT=re.compile(r"[A-Za-z0-9_.-]{1,255}\Z",re.ASCII)
GITHUB_ORIGIN="https://api.github.com"
MAX_URL_CHARS=2048


def guard_github_write_destination(url:object)->str:
    """Return the original exact canonical URL or fail before HTTP creation.

    Only GitHub contents write /repos/OWNER/REPO/contents/PATH and
    Actions variables /repos/OWNER/REPO/actions/variables[/NAME] exist.
    Reject URL encodings, fragments, userinfo, traversal, unusual segments,
    non-ASCII controls, off-origin hosts, implicit URL rewriting and ports.
    """
    if type(url) is not str or not url or len(url)>MAX_URL_CHARS:
        raise ValueError("GitHub write URL is not a bounded literal string")
    if any(ord(c)<33 or ord(c)>126 for c in url):
        raise ValueError("GitHub write URL has control/non-ASCII character")
    if any(c in url for c in ("\\","%","?","#","@")):
        raise ValueError("GitHub write URL contains forbidden URL syntax")
    try:
        parts=urlsplit(url)
        if (parts.scheme!="https" or parts.netloc!="api.github.com"
            or parts.hostname!="api.github.com" or parts.port is not None
            or parts.username is not None or parts.password is not None
            or parts.query or parts.fragment):
            raise ValueError("GitHub write URL not pinned to HTTPS origin")
    except ValueError as exc:
        raise ValueError("GitHub write URL invalid origin") from exc
    if (not url.startswith(GITHUB_ORIGIN+"/repos/")
        or url!=parts.geturl()):
        raise ValueError("GitHub write URL has unexpected canonical encoding")
    path=parts.path.split("/")
    # Leading slash + repos/owner/repo/(contents/file | actions/variables)
    if (len(path)<6 or path[0]!="" or path[1]!="repos"
        or not all(SAFE_SEGMENT.fullmatch(s) and s not in (".","..")
                    for s in path[2:])):
        raise ValueError("GitHub write URL invalid path")
    if (path[4]=="contents" and len(path)>=6
        or path[4]=="actions" and len(path) in (6,7)
        and path[5]=="variables"):
        return url
    raise ValueError("GitHub write URL route not allowlisted")


__all__=["guard_github_write_destination","GITHUB_ORIGIN"]
