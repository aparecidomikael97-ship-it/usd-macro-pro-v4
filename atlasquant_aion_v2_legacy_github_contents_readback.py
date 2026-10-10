"""Verify a legacy JSONL GitHub Contents PUT by a fresh same-endpoint GET.

Source-only hardening: existing readers supply the GET (already pinned URL,
auth header, no redirect, explicit status). This does NOT establish independent
network origin, trusted custody, monotonic witness or remote durability.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

class GitHubReadAfterWriteUnconfirmedError(RuntimeError):
    """A reported successful PUT is not verified by a matching fresh read."""

def _git_blob_sha(raw:bytes)->str:
    # GitHub Contents 'content.sha' identifies the resulting Git blob.
    # Supports the current SHA-1 repository format only, fail closed otherwise.
    return hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()

def decode_verified_github_contents(payload:object)->tuple[str,str]:
    """Bind the GET's raw bytes to its blob SHA before JSON parsing loses data.

    A missing/unsupported content body is not an empty file. This proves only
    consistency of the response, never independent provenance or durability.
    """
    if type(payload) is not dict or payload.get("encoding") != "base64":
        raise ValueError("GITHUB_BASE64_CONTENT_REQUIRED")
    content=payload.get("content")
    sha=payload.get("sha")
    if type(content) is not str or type(sha) is not str or re.fullmatch(r"[0-9a-f]{40}",sha) is None:
        raise ValueError("GITHUB_CONTENT_OR_BLOB_SHA_INVALID")
    try:
        # Contents API wraps base64 with line breaks; other garbage is invalid.
        encoded=content.replace("\r","").replace("\n","")
        raw=base64.b64decode(encoded,validate=True)
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise ValueError("NONCANONICAL_BASE64")
        if _git_blob_sha(raw) != sha:
            raise ValueError("GITHUB_RAW_BLOB_SHA_MISMATCH")
        return raw.decode("utf-8"),sha
    except (ValueError,UnicodeError,binascii.Error):
        raise ValueError("GITHUB_CONTENT_BYTES_UNVERIFIED") from None

def verify_legacy_jsonl_readback(
    *,
    response:object,
    expected_text:str,
    readback:Callable[[],tuple[list[dict[str,Any]],str]],
    serialize:Callable[[Iterable[Mapping[str,Any]]],str],
)->dict[str,Any]:
    """After a PUT returns 200/201, compare response SHA, fresh GET SHA and content.

    The caller must treat *any* raised error as UNKNOWN_OUTCOME, not safe retry.
    Neither success nor exception is a remotely attested terminal certificate.
    """
    if type(expected_text) is not str:
        raise GitHubReadAfterWriteUnconfirmedError("EXPECTED_JSONL_TEXT_REQUIRED")
    raw=expected_text.encode("utf-8")
    if not raw:
        raise GitHubReadAfterWriteUnconfirmedError("EMPTY_EXPECTED_JSONL_BLOCKED")
    if getattr(response,"status_code",None) not in (200,201) or type(getattr(response,"status_code",None)) is not int:
        raise GitHubReadAfterWriteUnconfirmedError("UNEXPECTED_PUT_ACCEPTANCE_STATUS")
    try:
        obj=response.json()
        if type(obj) is not dict or type(obj.get("content")) is not dict:
            raise GitHubReadAfterWriteUnconfirmedError("PUT_CONTENT_SHA_MISSING")
        sha=obj["content"].get("sha")
        if type(sha) is not str or re.fullmatch(r"[0-9a-f]{40}",sha) is None:
            raise GitHubReadAfterWriteUnconfirmedError("PUT_BLOB_SHA_MALFORMED")
        if sha!=_git_blob_sha(raw):
            raise GitHubReadAfterWriteUnconfirmedError("PUT_BLOB_SHA_NOT_EXPECTED_CONTENT")
        records,read_sha=readback()
        if type(read_sha) is not str or read_sha!=sha:
            raise GitHubReadAfterWriteUnconfirmedError("READBACK_BLOB_SHA_DIFFERENT")
        if type(records) is not list or not all(type(item) is dict for item in records):
            raise GitHubReadAfterWriteUnconfirmedError("READBACK_RECORDS_NOT_VALID_JSONL")
        read_text=serialize(records)
        if type(read_text) is not str or read_text.encode("utf-8")!=raw:
            raise GitHubReadAfterWriteUnconfirmedError("READBACK_CONTENT_DIFFERENT")
    except GitHubReadAfterWriteUnconfirmedError:
        raise
    except Exception as exc:
        # Exception detail can contain token/url/content. Report class only.
        raise GitHubReadAfterWriteUnconfirmedError(
            "READBACK_FAILED_"+type(exc).__name__
        ) from None
    return {
        "verified":True,
        "verification":"SAME_GITHUB_CONTENTS_ENDPOINT_READ_AFTER_WRITE",
        "blob_sha":sha,
        "content_sha256":hashlib.sha256(raw).hexdigest(),
        "readback_matching_content":True,
        "independent_response_origin_verified":False,
        "remote_durability_certified":False,
        "reconciliation_required":False,
        "safe_to_retry":False,
    }

__all__=["GitHubReadAfterWriteUnconfirmedError","verify_legacy_jsonl_readback",
         "decode_verified_github_contents"]
