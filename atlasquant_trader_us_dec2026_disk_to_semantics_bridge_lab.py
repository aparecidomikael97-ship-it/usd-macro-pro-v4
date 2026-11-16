"""Read-only December-2026 original-file custody -> PROVISIONAL semantics.

This is the missing physical bridge between:
  (a) one-GET capture's original.html + receipt.json + replay verifier, and
  (b) the still-unapproved TD/TE CPI/PPI November consensus column interpreter.

Require a real archive directory and exact event+provider+filename identity;
verify the raw-file SHA, HTTP/UTC receipt, issuer URL and pre-release freeze
again with the existing capture replay, then pass ORIGINAL bytes (not caller
numbers) to the semantic interpreter. Future files are not opened or parsed
at an earlier research cutoff. A bad past archive fails the WHOLE cohort,
rather than cherry-picking another provider's nicer result.

No network, writes, command execution, broker, scheduler, trader or deploy.
The locally supplied receipts are NOT independent publisher-first-seen proof.
The future December provider HTML layouts are still HYPOTHESES. A successful
synthetic replay is only a software test, not economic evidence or an FX hit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
from typing import Any

from atlasquant_trader_us_dec2026_consensus_original_one_get_lab import (
    _ROOT as _ARCHIVE_FILENAME,
    _source_claim,
    _unique_json_pairs,
    _reconcile,
    replay_dec2026_one_get_original_lab,
)
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import (
    EVENTS, SOURCE_NAMES,
)
from atlasquant_trader_us_dec2026_consensus_semantic_candidate_lab import (
    inspect_dec2026_consensus_semantic_candidate_lab,
)

SCHEMA = "ATLASQUANT_US_DEC2026_DISK_SOURCE_TO_PROVISIONAL_SEMANTICS_LAB_V1"
_ROOTS = tuple(root for root, _, _, _ in EVENTS)


@dataclass(frozen=True)
class ArchivedOriginalSelector:
    event_root: str
    provider: str
    archive_basename: str


def _utc(t: Any) -> datetime | None:
    if type(t) is not datetime or t.tzinfo is None:
        return None
    try:
        return t.astimezone(timezone.utc) if t.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_DEC2026_DISK_TO_PROVISIONAL_SEMANTICS_BLOCKED_HARD_NO_GO",
        "reason": reason,
        "economic_events_frozen_denominator": 2,
        "events": [
            {"event_root": root, "visible_replayed_originals": 0,
             "provisional_semantic_candidate": False,
             "consensus_eligible_for_fx": False}
            for root in _ROOTS
        ],
        "original_archives_replayed_visible": 0,
        "original_archives_future_hidden": 0,
        "semantic_candidate_event_count": 0,
        "synthetic_fixture_is_real_consensus_evidence": False,
        "source_originals_independently_first_seen_attested": False,
        "source_layout_semantics_validated_against_real_december_html": False,
        "independent_directional_predictions": 0,
        "scoreable_out_of_sample_fx_trials": 0,
        "win_rate": None,
        "usd_direction": None,
        "probability": None,
        "semantic_details_local_only": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "original_fx28_672_slots_modified": False,
        "http_requests": 0, "file_writes": 0, "mt5_calls": 0,
        "new_cost_brl": 0,
    }


def replay_dec2026_archives_to_semantic_candidates_lab(
    *, archive_root: Any, archives: Any, research_cutoff_utc: Any,
) -> dict[str, Any]:
    """Accept only physical replayed files and preserve PIT/missingness."""
    out=_blocked("INVALID_ARCHIVE_ROSTER_ROOT_OR_CUTOFF")
    now=_utc(research_cutoff_utc)
    if (now is None or type(archives) not in (tuple, list)
            or len(archives) > 4):
        return out
    try:
        root=Path(archive_root)
        if root.is_symlink() or not root.is_dir():
            return out
    except (OSError, ValueError, TypeError):
        return out

    original_claims=[]
    future_count=0
    seen=set()
    for s in archives:
        if (type(s) is not ArchivedOriginalSelector
                or type(s.event_root) is not str
                or s.event_root not in _ROOTS
                or type(s.provider) is not str
                or s.provider not in SOURCE_NAMES
                or type(s.archive_basename) is not str):
            return _blocked("UNKNOWN_EVENT_PROVIDER_OR_SELECTOR_TYPE")
        key=(s.event_root,s.provider)
        if key in seen:
            return _blocked("DUPLICATED_EVENT_PROVIDER_ARCHIVE")
        seen.add(key)
        m=_ARCHIVE_FILENAME.fullmatch(s.archive_basename)
        if (m is None or m.group(1)!=s.event_root
                or m.group(2)!=s.provider):
            return _blocked("ARCHIVE_DIRECTORY_NOT_MATCHING_FIXED_EVENT_PROVIDER")
        # Filename timestamp is only a *claim*. It prevents opening files
        # which weren't even supposedly captured by this decision cutoff.
        try:
            nominal_end=datetime.strptime(m.group(3),"%Y%m%dT%H%M%S%fZ")
            nominal_end=nominal_end.replace(tzinfo=timezone.utc)
        except ValueError:
            return _blocked("ARCHIVE_DIRECTORY_CAPTURE_CLOCK_UNPARSEABLE")
        if nominal_end>now:
            future_count+=1
            continue
        try:
            directory=root/s.archive_basename
            receipt_path=directory/"receipt.json"
            html_path=directory/"original.html"
            if (directory.is_symlink() or not directory.is_dir()
                    or receipt_path.is_symlink() or html_path.is_symlink()
                    or not receipt_path.is_file() or not html_path.is_file()
                    or receipt_path.stat().st_size > 8192):
                return _blocked("MISSING_SYMLINK_OR_OVERSIZED_ARCHIVE_FILES")
            proof=replay_dec2026_one_get_original_lab(
                output_root=root,archive_basename=s.archive_basename,
                research_cutoff_utc=now)
            if (proof["state"] !=
                "LAB_DEC2026_ONE_GET_ORIGINAL_LOCALLY_REPLAYED_NO_GO"
                    or proof["original_replayed_from_disk"] is not True
                    or proof["event_root"]!=s.event_root
                    or proof["provider"]!=s.provider
                    or proof["trade_authorized"] is not False):
                return _blocked("PHYSICAL_ORIGINAL_SHA_RECEIPT_REPLAY_REJECTED")
            # The physical replay validated ONE pair of raw HTML/receipt
            # snapshots. Bind the second read to BOTH exact hashes, not
            # merely the HTML hash and two identity keys. Otherwise a receipt
            # can be replaced between disk reads to launder changed HTTP or
            # BLS-review metadata into provisional economic semantics.
            receipt_bytes=receipt_path.read_bytes()
            body=html_path.read_bytes()
            if (sha256(body).hexdigest()!=proof["source_original_sha256"]
                    or len(body)!=proof["source_original_bytes"]
                    or sha256(receipt_bytes).hexdigest()!=proof["source_receipt_sha256"]):
                return _blocked("REOPENED_ORIGINAL_OR_RECEIPT_CHANGED_AFTER_REPLAY")
            receipt=json.loads(receipt_bytes.decode("utf-8","strict"),
                               object_pairs_hook=_unique_json_pairs)
            if (receipt["event_root"]!=s.event_root
                    or receipt["provider"]!=s.provider
                    or receipt["finished_at_utc"]!=proof["local_receipt_finished_utc_claim"]
                    or not _reconcile(body,receipt,cutoff=now)):
                return _blocked("REOPENED_RECEIPT_CUSTODY_OR_EVENT_BINDING_REJECTED")
            original_claims.append(_source_claim(body,receipt))
        except (OSError, UnicodeError, ValueError, TypeError, KeyError,
                OverflowError, RuntimeError):
            return _blocked("RECEIPT_OR_ARCHIVED_ORIGINAL_READ_FAILED")

    semantic=inspect_dec2026_consensus_semantic_candidate_lab(
        source_snapshots=tuple(original_claims),inspected_at_utc=now)
    if (semantic.get("state")!=
            "LAB_DEC2026_TWO_SOURCE_PROVISIONAL_SEMANTICS_ONLY_HARD_NO_GO"
            or semantic.get("economic_consensus_pre_event_independently_authenticated")!=0
            or semantic.get("registered_directional_fx_predictions")!=0
            or semantic.get("trade_authorized") is not False
            or semantic.get("publishable") is not False):
        return _blocked("ORIGINAL_BYTES_SEMANTICS_FAILED_NO_PARTIAL_CANDIDATE")
    result=[]
    for row in semantic["events"]:
        root=row["event_root"]
        count=sum(s.event_root==root for s in original_claims)
        if bool(row["locally_reconciled_two_source_bytes"]) != (count==2):
            return _blocked("SOURCE_PAIR_OR_PROVISIONAL_CANDIDATE_COUNT_MISMATCH")
        result.append({
            "event_root":root,"visible_replayed_originals":count,
            "provisional_semantic_candidate":count==2,
            "consensus_eligible_for_fx":False,
        })
    out.update({
        "state":"LAB_DEC2026_PHYSICAL_ORIGINALS_TO_PROVISIONAL_COLUMNS_NO_GO",
        "reason":"ORIGINAL_FILE_REPLAYED_BUT_DECEMBER_LAYOUT_AND_FIRST_SEEN_NOT_ATTESTED",
        "events":result,
        "original_archives_replayed_visible":len(original_claims),
        "original_archives_future_hidden":future_count,
        "semantic_candidate_event_count":semantic["local_two_source_candidate_event_count"],
        # Explicitly LOCAL; never forward this to public PRs or a client UI.
        "semantic_details_local_only":semantic,
    })
    return out


__all__=(
    "SCHEMA","ArchivedOriginalSelector",
    "replay_dec2026_archives_to_semantic_candidates_lab",
)
