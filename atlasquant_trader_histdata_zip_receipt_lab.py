"""Offline ZIP envelope inspection for an untrusted HistData M1 Bid CSV.

No download, extraction to disk, license inference, execution prices or signal.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from io import BytesIO
import re
from typing import Any
import zipfile
import zlib

from atlasquant_trader_histdata_m1_bid_window_lab import (
    MAX_BYTES as MAX_CSV_BYTES,
    _deny,
    inspect_histdata_m1_bid_window_lab,
)

SCHEMA = "ATLASQUANT_TRADER_HISTDATA_M1_ZIP_RECEIPT_LAB_V1"
MAX_ZIP_BYTES = 8 * 1024 * 1024
MAX_STATUS_BYTES = 64 * 1024
MAX_COMPRESSION_RATIO = 200
SAFE_TEXT_MEMBER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\.txt")
SAFE_ARCHIVE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.zip")


def _blocked(reason: str) -> dict[str, Any]:
    result = _deny(reason)
    result.update({
        "zip_receipt_schema": SCHEMA,
        "source_archive_name": None,
        "source_zip_sha256": None,
        "source_zip_bytes": None,
        "source_zip_member_count": None,
        "source_zip_crc_checked": False,
        "source_zip_archive_structure_checked": False,
        "status_member": None,
        "status_member_sha256": None,
        "status_report_independently_verified": False,
    })
    return result


def _regular_safe_member(member: zipfile.ZipInfo, *, max_size: int) -> bool:
    """Reject traversal, links, encrypted entries and decompression bombs."""
    name = member.filename
    if (not name or len(name) > 120 or not name.isascii()
            or "/" in name or "\\" in name or name in (".", "..")
            or member.is_dir() or member.flag_bits & 1
            or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
            or not 1 <= member.file_size <= max_size
            or member.compress_size <= 0
            or member.file_size > member.compress_size * MAX_COMPRESSION_RATIO):
        return False
    if member.create_system == 3:
        unix_kind = (member.external_attr >> 16) & 0o170000
        if unix_kind not in (0, 0o100000):
            return False
    return True


def inspect_histdata_m1_zip_receipt_lab(
    archive: Any, *, archive_name: str, expected_symbol: str,
    expected_year_month: str, captured_at_utc: datetime,
    as_of_utc: datetime, event_at_utc: datetime,
) -> dict[str, Any]:
    """Validate an in-memory ZIP then delegate CSV semantics to the M1 gate."""
    out = _blocked("INVALID_ZIP_OR_RECEIPT_INPUT")
    if (not isinstance(archive, bytes)
            or not 100 <= len(archive) <= MAX_ZIP_BYTES
            or not isinstance(archive_name, str)
            or SAFE_ARCHIVE_NAME.fullmatch(archive_name) is None
            or not isinstance(expected_year_month, str)
            or re.fullmatch(r"20\d{4}", expected_year_month) is None
            or not 1 <= int(expected_year_month[4:]) <= 12
            or not isinstance(expected_symbol, str)
            or re.fullmatch(r"[A-Z]{6}", expected_symbol) is None):
        return out

    csv_name = f"DAT_ASCII_{expected_symbol}_M1_{expected_year_month}.csv"
    try:
        with zipfile.ZipFile(BytesIO(archive), mode="r") as zf:
            members = zf.infolist()
            if not 1 <= len(members) <= 2:
                out["reason"] = "UNEXPECTED_ZIP_MEMBER_COUNT"
                return out
            if len(set(m.filename for m in members)) != len(members):
                out["reason"] = "DUPLICATE_ZIP_MEMBER"
                return out
            csv_members = [m for m in members if m.filename == csv_name]
            status_members = [m for m in members if m.filename != csv_name]
            if (len(csv_members) != 1 or len(status_members) > 1
                    or any(SAFE_TEXT_MEMBER.fullmatch(m.filename) is None
                           for m in status_members)):
                out["reason"] = "UNSUPPORTED_ZIP_MEMBERS_OR_WRONG_SYMBOL_MONTH"
                return out
            if not _regular_safe_member(csv_members[0], max_size=MAX_CSV_BYTES):
                out["reason"] = "UNSAFE_ZIP_CSV_MEMBER"
                return out
            if status_members and not _regular_safe_member(
                    status_members[0], max_size=MAX_STATUS_BYTES):
                out["reason"] = "UNSAFE_ZIP_STATUS_MEMBER"
                return out

            # ZipFile.read verifies stored CRC. Do not extract or execute files.
            csv = zf.read(csv_members[0])
            status = zf.read(status_members[0]) if status_members else None
            if (len(csv) != csv_members[0].file_size
                    or status is not None and len(status) != status_members[0].file_size):
                out["reason"] = "ZIP_DECOMPRESSED_SIZE_MISMATCH"
                return out

        out = inspect_histdata_m1_bid_window_lab(
            csv, filename=csv_name, expected_symbol=expected_symbol,
            captured_at_utc=captured_at_utc, as_of_utc=as_of_utc,
            event_at_utc=event_at_utc,
        )
        out["zip_receipt_schema"] = SCHEMA
        out["source_archive_name"] = archive_name
        out["source_zip_sha256"] = sha256(archive).hexdigest()
        out["source_zip_bytes"] = len(archive)
        out["source_zip_member_count"] = len(members)
        out["source_zip_crc_checked"] = True
        out["source_zip_archive_structure_checked"] = True
        out["status_member"] = status_members[0].filename if status_members else None
        out["status_member_sha256"] = sha256(status).hexdigest() if status is not None else None
        out["status_report_independently_verified"] = False
        # CRC and syntax are not authenticity, market-data rights or PIT proof.
        return out
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError,
            EOFError, OverflowError, TypeError, ValueError, zlib.error):
        out["reason"] = "ZIP_CORRUPT_OR_UNREADABLE"
        return out


__all__ = ["SCHEMA", "inspect_histdata_m1_zip_receipt_lab"]
