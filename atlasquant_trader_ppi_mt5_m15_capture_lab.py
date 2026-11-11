"""Opt-in PPI 2026-11-13 seven-USD-FX M15 local capture; LAB only.

This module is inert on import. A person must run its CLI on the Windows PC
with an already-open MT5 terminal. Only terminal_info, symbol_info and
copy_rates_range are read; no login, order, position, symbol_select or worker.
The broker identity, UTC clock, price history and first-seen vintage remain
UNATTESTED even when the seven local files pass structural checks.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
from types import SimpleNamespace
import re
from typing import Any, Callable

from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    BASELINE_OPEN_UTC, EVENT_UTC, FIELDS, LAST_REQUIRED_CLOSE_UTC,
    ROWS_REQUIRED, USD_FX, ClaimedLocalPriceArchive,
)

SCHEMA = "ATLASQUANT_TRADER_PPI_MT5_7USD_FX_M15_LOCAL_CAPTURE_LAB_V1"
SOURCE_KIND = "MT5_READONLY_M15_CSV_CLAIM_UNVERIFIED"
EXPECTED_EPOCHS = tuple(int(BASELINE_OPEN_UTC.timestamp()) + 900 * n
                        for n in range(ROWS_REQUIRED))


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PPI_MT5_CAPTURE_BLOCKED",
        "reason": reason, "event_release_utc": EVENT_UTC.isoformat(),
        "required_last_close_utc": LAST_REQUIRED_CLOSE_UTC.isoformat(),
        "expected_symbols": list(USD_FX), "expected_m15_rows_per_symbol": ROWS_REQUIRED,
        "validated_symbols": 0, "validated_bars": 0,
        "directory": None, "sha256_by_symbol": None,
        "local_files_written": 0, "mt5_account_information_accessed": False,
        "orders_or_positions_accessed": False, "symbol_visibility_changed": False,
        "broker_identity_independently_authenticated": False,
        "active_quote_server_independently_verified": False,
        "terminal_company_observation_untrusted": None,
        "symbol_specs_observed_locally": False,
        "symbol_specs_claimed_unattested": None,
        "candle_utc_independently_authenticated": False,
        "point_in_time_market_data_attested": False,
        "operational_bias": "AGUARDAR", "publishable": False,
        "trade_authorized": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def _output_root_ok(root: Any) -> bool:
    return (isinstance(root, Path) and root.is_absolute()
            and root.parts[-3:] == ("AtlasQuant", "LAB", "PPI_20261113_MT5")
            and ".." not in root.parts
            and not any(parent.is_symlink() for parent in (root, *root.parents)))


def _integer(value: Any, *, strictly_positive: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError("INVALID_VOLUME_OR_EPOCH")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("INVALID_VOLUME_OR_EPOCH") from exc
    if number != value or number < (1 if strictly_positive else 0) or number > 999_999_999_999:
        raise ValueError("INVALID_VOLUME_OR_EPOCH")
    return number


def _price(value: Any) -> tuple[Decimal, str]:
    if isinstance(value, (bool, str)):
        raise ValueError("NON_NUMERIC_PRICE")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("NON_NUMERIC_PRICE") from exc
    # No rounding, extrapolation or scientific notation: exact downstream CSV contract.
    printed = format(number, "f")
    if (not number.is_finite() or number <= 0 or len(printed) > 20
            or not re.fullmatch(r"[0-9]{1,7}(?:\.[0-9]{1,9})?", printed)):
        raise ValueError("PRICE_OUTSIDE_FROZEN_CSV_CONTRACT")
    return number, printed


def _symbol_spec_for_capture(info: Any, symbol: str) -> dict[str, Any] | None:
    """Read-only symbol descriptor sanity, not broker/account attestation.

    MetaTrader exposes these via symbol_info(name), and the point is the
    terminal's declared quote increment, not a historical execution quote.
    """
    name = getattr(info, "name", None)
    base = getattr(info, "currency_base", None)
    quote = getattr(info, "currency_profit", None)
    digits = getattr(info, "digits", None)
    point = getattr(info, "point", None)
    if (name != symbol or base != symbol[:3] or quote != symbol[3:]
            or type(digits) is not int or not 2 <= digits <= 6
            or isinstance(point, (str, bool))):
        return None
    try:
        value = Decimal(str(point))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if (not value.is_finite() or value <= 0
            or value != Decimal(1).scaleb(-digits)):
        return None
    return {
        "symbol": symbol, "currency_base_claim": base,
        "currency_profit_claim": quote, "digits_claim": digits,
        "point_quote_units_claim": format(value, "f"),
    }


def _terminal_company_label(terminal: Any) -> str | None:
    """Keep only a public vendor label, never paths, account or server data."""
    company = getattr(terminal, "company", None)
    if (not isinstance(company, str) or not 1 <= len(company) <= 120
            or company != company.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in company)
            or "/" in company or chr(92) in company):
        return None
    return company


def _serialize_exact_window(rates: Any) -> bytes:
    if rates is None or len(rates) != ROWS_REQUIRED:
        raise ValueError("REQUIRE_EXACTLY_17_M15_BARS")
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(FIELDS)
    try:
        for i, bar in enumerate(rates):
            epoch = _integer(bar["time"], strictly_positive=True)
            if epoch != EXPECTED_EPOCHS[i]:
                raise ValueError("PPI_M15_EPOCH_GAP_DUPLICATE_OR_WRONG_TIMEZONE")
            values = [_price(bar[field]) for field in ("open", "high", "low", "close")]
            (op, hi, lo, cl) = (value[0] for value in values)
            if not lo <= min(op, cl) <= max(op, cl) <= hi:
                raise ValueError("PPI_OHLC_INCONSISTENT")
            quantities = [_integer(bar[field], strictly_positive=(field == "tick_volume"))
                          for field in ("tick_volume", "spread", "real_volume")]
            writer.writerow((epoch, *(value[1] for value in values), *quantities))
    except (KeyError, IndexError, TypeError, OverflowError) as exc:
        raise ValueError("MT5_RATE_MISSING_REQUIRED_FIELDS") from exc
    return output.getvalue().encode("utf-8")


def collect_ppi_mt5_m15_capture_lab(
    api: Any, *, terminal_path: Any, output_root: Any,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Fail closed before writing any data unless all seven histories validate."""
    report = _base("INVALID_TERMINAL_PATH_OR_LAB_OUTPUT_ROOT")
    if not _terminal_path_ok(terminal_path) or not _output_root_ok(output_root):
        return report
    try:
        observed = clock()
        if (not isinstance(observed, datetime) or observed.tzinfo is None
                or observed.utcoffset() is None):
            raise ValueError("INVALID_WALL_CLOCK")
        now = observed.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        report["reason"] = "INVALID_WALL_CLOCK"
        return report
    if now < LAST_REQUIRED_CLOSE_UTC:
        report["reason"] = "FOUR_HOUR_M15_WINDOW_NOT_YET_CLOSED"
        return report
    run_dir = output_root / ("PPI7_" + now.strftime("%Y%m%dT%H%M%S%fZ"))
    if run_dir.exists() or run_dir.is_symlink():
        report["reason"] = "CAPTURE_RUN_ALREADY_EXISTS_NO_OVERWRITE"
        return report

    try:
        connected = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, OSError, TypeError, ValueError, RuntimeError):
        report["reason"] = "MT5_INITIALIZATION_EXCEPTION"
        return report
    if not connected:
        report["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
        return report
    pending: dict[str, bytes] = {}
    specs: dict[str, dict[str, Any]] = {}
    terminal_company: str | None = None
    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            report["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
            return report
        terminal_company = _terminal_company_label(terminal)
        for symbol in USD_FX:
            info = api.symbol_info(symbol)
            if info is None or info.visible is not True:
                report["reason"] = "CANONICAL_SYMBOL_NOT_VISIBLE_NO_AUTO_SELECT"
                report["failed_symbol"] = symbol
                return report
            spec = _symbol_spec_for_capture(info, symbol)
            if spec is None:
                report["reason"] = "SYMBOL_BASE_QUOTE_DIGITS_OR_POINT_NOT_VERIFIED"
                report["failed_symbol"] = symbol
                return report
            specs[symbol] = spec
            # MT5's range endpoints are UTC-aware, inclusive open timestamps.
            rates = api.copy_rates_range(
                symbol, api.TIMEFRAME_M15, BASELINE_OPEN_UTC,
                datetime.fromtimestamp(EXPECTED_EPOCHS[-1], tz=timezone.utc),
            )
            try:
                pending[symbol] = _serialize_exact_window(rates)
            except ValueError as exc:
                report["reason"] = str(exc)
                report["failed_symbol"] = symbol
                return report
    except (AttributeError, KeyError, OSError, TypeError, ValueError, RuntimeError):
        report["reason"] = "MT5_READONLY_QUERY_EXCEPTION"
        return report
    finally:
        try:
            api.shutdown()
        except (AttributeError, OSError, TypeError, RuntimeError):
            # If shutdown cannot complete, never claim a successful capture.
            report["reason"] = "MT5_SHUTDOWN_FAILED_NO_ARCHIVE"
            return report

    # All 119 historical bars have now passed. Create a new unique LAB run.
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        run_dir.mkdir(exist_ok=False)
        hashes: dict[str, str] = {}
        for symbol, raw in pending.items():
            name = f"{symbol}_PPI_20261113_M15.csv"
            file = run_dir / name
            with file.open("xb") as handle:
                handle.write(raw)
            report["local_files_written"] += 1
            digest = sha256(raw).hexdigest()
            if sha256(file.read_bytes()).hexdigest() != digest:
                report["reason"] = "LOCAL_READBACK_SHA256_MISMATCH_INCOMPLETE_RUN"
                return report
            hashes[symbol] = digest
        manifest = {
            "schema": SCHEMA,
            "source_kind": SOURCE_KIND,
            "captured_at_utc_local_clock_claim": now.isoformat(),
            "sha256_by_symbol": hashes,
            "symbol_count": len(hashes), "rows_per_symbol": ROWS_REQUIRED,
            "terminal_company_observation_untrusted": terminal_company,
            "active_quote_server_independently_verified": False,
            "symbol_specs_claimed_unattested": specs,
            "symbol_specs_observed_locally": True,
            "broker_identity_independently_authenticated": False,
            "candle_utc_independently_authenticated": False,
            "point_in_time_market_data_attested": False,
            "research_only": True, "operational_bias": "AGUARDAR",
            "publishable": False, "trade_authorized": False,
        }
        with (run_dir / "ppi_mt5_capture_manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, sort_keys=True, indent=2, ensure_ascii=False)
            handle.write("\n")
        report["local_files_written"] += 1
    except (OSError, ValueError):
        report["reason"] = "LOCAL_WRITE_FAILED_INCOMPLETE_RUN_LEFT_UNTOUCHED"
        return report
    report.update({
        "state": "LAB_PPI_7PAIR_LOCAL_M15_CANDIDATE_UNATTESTED",
        "reason": "LOCAL_HASHES_ONLY_NO_BROKER_PIT_OR_CAUSAL_ATTESTATION",
        "validated_symbols": len(USD_FX), "validated_bars": len(USD_FX) * ROWS_REQUIRED,
        "sha256_by_symbol": hashes, "directory": str(run_dir),
        "terminal_company_observation_untrusted": terminal_company,
        "symbol_specs_observed_locally": True,
        "symbol_specs_claimed_unattested": specs,
    })
    return report


def _stored_symbol_specs_valid(manifest: Any) -> bool:
    """Schema sanity only: local manifest does not authenticate any broker."""
    if not isinstance(manifest, dict):
        return False
    specs = manifest.get("symbol_specs_claimed_unattested")
    if (manifest.get("symbol_specs_observed_locally") is not True
            or manifest.get("active_quote_server_independently_verified") is not False
            or manifest.get("broker_identity_independently_authenticated") is not False
            or not isinstance(specs, dict) or set(specs) != set(USD_FX)):
        return False
    public_label = manifest.get("terminal_company_observation_untrusted")
    if public_label is not None and _terminal_company_label(
            SimpleNamespace(company=public_label)) != public_label:
        return False
    for symbol, row in specs.items():
        if (not isinstance(row, dict)
                or set(row) != {"symbol", "currency_base_claim",
                                "currency_profit_claim", "digits_claim",
                                "point_quote_units_claim"}):
            return False
        try:
            observed = SimpleNamespace(
                name=row["symbol"], currency_base=row["currency_base_claim"],
                currency_profit=row["currency_profit_claim"],
                digits=row["digits_claim"],
                point=(Decimal(row["point_quote_units_claim"])
                       if type(row["point_quote_units_claim"]) is str else None))
            expected = _symbol_spec_for_capture(observed, symbol)
        except (ValueError, InvalidOperation, TypeError):
            return False
        if expected is None or expected != row:
            return False
    return True


def load_local_receipt_lab(directory: Path) -> ClaimedLocalPriceArchive:
    """Read the claimed local manifest; the downstream reader rechecks all CSV hashes."""
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("RUN_DIRECTORY_MISSING_OR_SYMLINK")
    file = directory / "ppi_mt5_capture_manifest.json"
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 10_000:
        raise ValueError("MANIFEST_MISSING_OR_UNSAFE")
    try:
        manifest = json.loads(file.read_text(encoding="utf-8"))
        if (manifest["schema"] != SCHEMA or manifest["source_kind"] != SOURCE_KIND
                or set(manifest["sha256_by_symbol"]) != set(USD_FX)):
            raise ValueError("MANIFEST_SCHEMA_OR_COHORT_MISMATCH")
        if not _stored_symbol_specs_valid(manifest):
            raise ValueError("MANIFEST_SYMBOL_SPECS_OR_BROKER_ATTESTATION_INVALID")
        now = datetime.fromisoformat(manifest["captured_at_utc_local_clock_claim"])
        return ClaimedLocalPriceArchive(
            captured_at_utc=now,
            sha256_by_symbol=manifest["sha256_by_symbol"],
            source_kind=manifest["source_kind"],
        )
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("MANIFEST_NOT_PARSEABLE") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="PPI: opt-in read-only MT5 M15 capture (LAB)")
    parser.add_argument("--terminal-path", required=True,
                        help="Explicit existing Windows terminal64.exe path")
    args = parser.parse_args()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        print("BLOCKED: Windows LOCALAPPDATA required")
        return 2
    try:
        import MetaTrader5 as mt5  # optional Windows-only import after explicit CLI invocation
    except ImportError:
        print("BLOCKED: MetaTrader5 Python package unavailable")
        return 2
    report = collect_ppi_mt5_m15_capture_lab(
        mt5, terminal_path=args.terminal_path,
        output_root=Path(local_app_data) / "AtlasQuant" / "LAB" / "PPI_20261113_MT5",
        clock=lambda: datetime.now(timezone.utc),
    )
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if report["validated_bars"] == 119 else 2


if __name__ == "__main__":
    raise SystemExit(main())
