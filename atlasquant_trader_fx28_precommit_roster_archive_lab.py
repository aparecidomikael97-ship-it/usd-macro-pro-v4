"""Manual, fail-closed FX28 pre-window forecast roster ARCHIVE; LAB only.

This does NOT invent model forecasts, infer bias from price history, post to
GitHub or attest publisher/issuance. A real external issuer must supply all
28 original forecast records, cutoff times and source/model digests. We archive
the complete canonical bytes behind the prospective SHA (never hash alone).
Import is inert: no MT5, network, trades, scheduler, app writes or forecasts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    HEADER, PREWINDOW_LOOKBACK, PairForecastClaim,
    prepare_window_witness_body_lab,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import _nominal_windows

SCHEMA = "ATLASQUANT_FX28_PREWINDOW_ROSTER_WRITEONCE_LAB_V1"
INPUT_SCHEMA = "ATLASQUANT_FX28_EXPLICIT_28_FORECAST_ROSTER_INPUT_LAB_V1"
MAX_INPUT_BYTES = 100_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
INPUT_KEYS = frozenset((
    "schema", "horizon", "start_utc", "end_utc", "forecast_roster"))
RECORD_KEYS = frozenset((
    "pair", "direction", "abstain_reason", "feature_cutoff_utc",
    "forecast_issued_utc", "model_sha256_claim", "evidence_sha256_claim"))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PREWINDOW_ROSTER_ARCHIVE_BLOCKED_NO_GO",
        "reason": reason, "archive_dir": None, "roster_sha256": None,
        "manifest_sha256": None, "window": None,
        "pairs_supplied": 0, "input_file_overwritten": False,
        "external_prewindow_witness_posted": False,
        "forecast_original_issued_at_authenticated": False,
        "model_source_evidence_authenticated": False,
        "broker_prices_read": False, "macro_network_requests": 0,
        "calibrated_probability": None, "validated_accuracy": None,
        "publishable": False, "trade_authorized": False,
        "worker_enabled": False, "operational_bias": "AGUARDAR",
    }


def _stamp(x: Any) -> datetime | None:
    if type(x) is not str or STAMP.fullmatch(x) is None:
        return None
    try:
        dt = datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ")
        if dt.strftime("%Y-%m-%dT%H:%M:%SZ") != x:
            return None
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _utc(x: Any) -> datetime | None:
    if (type(x) is not datetime or x.tzinfo is None
            or x.utcoffset() is None or x.microsecond):
        return None
    return x.astimezone(timezone.utc)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("DUPLICATE_INPUT_JSON_KEY")
        data[key] = value
    return data


def _load_input(raw: Any, now: datetime) -> tuple[Any, list[Any]] | None:
    if type(raw) is not bytes or not 2 <= len(raw) <= MAX_INPUT_BYTES:
        return None
    try:
        data = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("NONFINITE_NUMBER")),
        )
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        return None
    if (type(data) is not dict or set(data) != INPUT_KEYS
            or data["schema"] != INPUT_SCHEMA
            or data["horizon"] not in ("D1", "W1")
            or type(data["forecast_roster"]) is not list
            or len(data["forecast_roster"]) != 28):
        return None
    horizon = data["horizon"]
    start, end = _stamp(data["start_utc"]), _stamp(data["end_utc"])
    if (start is None or end is None or
            (start, end) not in _nominal_windows(horizon)
            or not start - PREWINDOW_LOOKBACK <= now < start):
        return None
    records = []
    for row in data["forecast_roster"]:
        if type(row) is not dict or set(row) != RECORD_KEYS:
            return None
        issued = _stamp(row["forecast_issued_utc"])
        cutoff = _stamp(row["feature_cutoff_utc"])
        digest = (row["model_sha256_claim"], row["evidence_sha256_claim"])
        if (issued is None or cutoff is None
                or not start - PREWINDOW_LOOKBACK <= cutoff <= issued <= now
                or any(type(x) is not str or HEX64.fullmatch(x) is None
                       or x == "0" * 64 for x in digest)
                or type(row["pair"]) is not str
                or type(row["direction"]) is not str
                or row["abstain_reason"] is not None
                   and type(row["abstain_reason"]) is not str):
            return None
        records.append(PairForecastClaim(
            pair=row["pair"], direction=row["direction"],
            abstain_reason=row["abstain_reason"],
            feature_cutoff_at=cutoff, forecast_issued_at=issued,
            model_sha256_claim=digest[0],
            evidence_sha256_claim=digest[1],
        ))
    return (horizon, start, end), records


def archive_explicit_roster_lab(
    *, raw_input: Any, output_root: Path, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Only real explicit input; never synthesize any of the 28 directions."""
    out = _blocked("INVALID_INPUT_OR_OUTSIDE_FROZEN_12H_WINDOW")
    now = _utc(inspected_at_utc)
    if (now is None or not isinstance(output_root, Path)
            or not output_root.is_absolute()):
        return out
    validated = _load_input(raw_input, now)
    if validated is None:
        return out
    (horizon, start, end), records = validated
    prepared = prepare_window_witness_body_lab(
        horizon=horizon, start_at=start, end_at=end,
        forecast_roster=tuple(records), prepared_at=now)
    if (prepared["state"] != "LAB_WITNESS_BODY_PREPARED_NOT_POSTED"
            or type(prepared["canonical_forecast_json"]) is not str
            or type(prepared["body"]) is not str
            or not prepared["body"].startswith(HEADER)):
        out["reason"] = "WITNESS_BUILDER_REJECTED_UNVERIFIED_INPUT"
        return out
    digest = prepared["forecast_roster_sha256"]
    canonical = prepared["canonical_forecast_json"].encode("ascii")
    body = (prepared["body"] + "\n").encode("utf-8")
    directory = output_root / (
        "FX28_" + horizon + "_" + start.strftime("%Y%m%dT%H%M%SZ")
        + "_" + digest[:16])
    if directory.exists() or directory.is_symlink():
        out["reason"] = "CANONICAL_ROSTER_ALREADY_ARCHIVED_NO_OVERWRITE"
        return out
    manifest = {
        "schema": SCHEMA, "input_schema": INPUT_SCHEMA,
        "horizon": horizon, "start_utc": start.isoformat(),
        "end_utc": end.isoformat(), "archived_at_utc_local_clock_claim": now.isoformat(),
        "input_sha256": sha256(raw_input).hexdigest(),
        "canonical_roster_sha256": digest,
        "public_witness_body_sha256": sha256(body).hexdigest(),
        "forecast_records": 28, "research_only": True,
        "external_comment_posted": False,
        "issuance_and_sources_independently_attested": False,
        "model_prediction_accuracy": None, "trade_authorized": False,
    }
    manifest_bytes = (json.dumps(
        manifest, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    try:
        # Preserve source bytes, including each model-provided timestamp.
        output_root.mkdir(parents=True, exist_ok=True)
        directory.mkdir(exist_ok=False)
        for name, data in (
            ("original_input.json", raw_input),
            ("canonical_forecasts.json", canonical),
            ("witness_body_NOT_POSTED.txt", body),
            ("receipt.json", manifest_bytes),
        ):
            file = directory / name
            with file.open("xb") as handle:
                handle.write(data)
            if sha256(file.read_bytes()).digest() != sha256(data).digest():
                out["reason"] = "LOCAL_READBACK_HASH_FAILED_INCOMPLETE_RUN"
                return out
    except OSError:
        out["reason"] = "LOCAL_WRITE_FAILED_PARTIAL_RUN_NOT_TRUSTED"
        return out
    out.update({
        "state": "LAB_FX28_CANONICAL_ROSTER_ARCHIVED_NOT_POSTED_NO_GO",
        "reason": "INPUT_IS_UNAUTHENTICATED_NO_PUBLIC_FIRST_SEEN_WITNESS",
        "archive_dir": str(directory), "roster_sha256": digest,
        "manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "window": horizon + ":" + start.isoformat(),
        "pairs_supplied": 28,
    })
    return out


def verify_roster_archive_lab(directory: Path) -> dict[str, Any]:
    """Recheck retained original bytes vs canonical data, witness and receipt."""
    if not isinstance(directory, Path) or not directory.is_dir() or directory.is_symlink():
        raise ValueError("ROSTER_ARCHIVE_NOT_DIRECTORY")
    names = ("original_input.json", "canonical_forecasts.json",
             "witness_body_NOT_POSTED.txt", "receipt.json")
    files = [directory / name for name in names]
    if any(file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_INPUT_BYTES
           for file in files):
        raise ValueError("ROSTER_FILE_MISSING_OR_UNSAFE")
    raw, canonical, body, receipt_raw = (file.read_bytes() for file in files)
    try:
        receipt = json.loads(receipt_raw, object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, ValueError, TypeError):
        raise ValueError("INVALID_RECEIPT") from None
    if (type(receipt) is not dict or receipt.get("schema") != SCHEMA
            or receipt.get("external_comment_posted") is not False
            or receipt.get("issuance_and_sources_independently_attested") is not False
            or receipt.get("trade_authorized") is not False
            or receipt.get("forecast_records") != 28
            or sha256(raw).hexdigest() != receipt.get("input_sha256")
            or sha256(canonical).hexdigest() != receipt.get("canonical_roster_sha256")
            or sha256(body).hexdigest() != receipt.get("public_witness_body_sha256")):
        raise ValueError("ROSTER_RECEIPT_OR_SHA_MISMATCH")
    created = _stamp(receipt.get("archived_at_utc_local_clock_claim", "").replace("+00:00", "Z"))
    if created is None:
        raise ValueError("ROSTER_ARCHIVE_CLOCK_INVALID")
    parsed = _load_input(raw, created)
    if parsed is None:
        raise ValueError("ORIGINAL_ROSTER_NO_LONGER_VALID")
    (horizon, start, end), records = parsed
    prepared = prepare_window_witness_body_lab(
        horizon=horizon, start_at=start, end_at=end,
        forecast_roster=tuple(records), prepared_at=created)
    if (receipt.get("input_schema") != INPUT_SCHEMA
            or receipt.get("research_only") is not True
            or receipt.get("model_prediction_accuracy") is not None
            or receipt.get("horizon") != horizon
            or receipt.get("start_utc") != start.isoformat()
            or receipt.get("end_utc") != end.isoformat()):
        raise ValueError("RECEIPT_CAMPAIGN_WINDOW_METADATA_MISMATCH")
    if (prepared["state"] != "LAB_WITNESS_BODY_PREPARED_NOT_POSTED"
            or prepared["canonical_forecast_json"].encode("ascii") != canonical
            or (prepared["body"] + "\n").encode("utf-8") != body):
        raise ValueError("RECONSTRUCTED_WITNESS_NOT_EQUAL_TO_ARCHIVED_BYTES")
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_ROSTER_LOCAL_HASH_REVERIFIED_NOT_POSTED_NO_GO",
        "pairs_reconciled": 28, "horizon": horizon,
        "start_utc": start.isoformat(), "digest": sha256(canonical).hexdigest(),
        "manifest_sha256": sha256(receipt_raw).hexdigest(),
        "original_source_authenticated": False, "github_first_seen_verified": False,
        "trade_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Explicit FX28 roster archive, NO posting/trades")
    cli.add_argument("--roster-input", type=Path, required=False)
    cli.add_argument("--archive-root", type=Path, required=False)
    cli.add_argument("--verify", type=Path, required=False)
    args = cli.parse_args(argv)
    if args.verify is not None and args.roster_input is None and args.archive_root is None:
        try:
            report = verify_roster_archive_lab(args.verify)
        except (ValueError, OSError, UnicodeError, OverflowError) as exc:
            print(json.dumps({"state": "BLOCKED","reason":str(exc)}))
            return 2
        print(json.dumps(report, sort_keys=True))
        return 0
    if args.verify is not None or args.roster_input is None or args.archive_root is None:
        cli.error("select --verify OR --roster-input AND --archive-root")
    try:
        if (not args.roster_input.is_absolute() or args.roster_input.is_symlink()
                or not args.roster_input.is_file() or
                args.roster_input.stat().st_size > MAX_INPUT_BYTES):
            raise ValueError("ROSTER_INPUT_FILE_MISSING_OR_UNSAFE")
        raw = args.roster_input.read_bytes()
        report = archive_explicit_roster_lab(
            raw_input=raw, output_root=args.archive_root,
            inspected_at_utc=datetime.now(timezone.utc).replace(microsecond=0))
    except (ValueError, OSError):
        report = _blocked("ROSTER_INPUT_READ_FAILED_OR_UNSAFE")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["state"] == "LAB_FX28_CANONICAL_ROSTER_ARCHIVED_NOT_POSTED_NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
