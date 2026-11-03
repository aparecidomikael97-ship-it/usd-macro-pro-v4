"""Local READ-ONLY Copom evidence check, LAB/HARD NO-GO.

Usage:
 python atlasquant_trader_copom_readiness_cli_lab.py \
   --as-of 2026-11-03T20:30:00Z
 python atlasquant_trader_copom_readiness_cli_lab.py \
   --as-of 2026-11-05T13:00:00Z --format json

Optionally supply an authorized, independently reviewed CSV and its
provenance manifesto (not a source endorsement). Do NOT collect B3 bulletins
automatically. The CLI reads existing files only, does not write, fetch,
schedule, trade or change Render/UI. Supplied --as-of is only a CLAIMED clock.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence

from atlasquant_trader_copom_evidence_readiness_lab import (
    build_copom_evidence_readiness_lab,
    DENIED, MISSING_EVIDENCE,
)

PRE_EVENT_SNAPSHOT = (Path(__file__).resolve().parent / "docs" /
                      "continuidade" /
                      "TRADER_COPOM_20261104_FROZEN_PRE_EVENT_20261103.json")
ISO_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
                     r"[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
MAX_CSV_BYTES = 4000
MAX_MANIFEST_BYTES = 4096


def _parse_clock(raw: str) -> datetime:
    if not isinstance(raw, str) or ISO_UTC.fullmatch(raw) is None:
        raise ValueError("Use UTC explícito no formato AAAA-MM-DDTHH:MM:SSZ")
    try:
        clock = datetime.fromisoformat(raw[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("Horário UTC impossível ou inválido") from exc
    return clock.astimezone(timezone.utc)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Chave repetida no manifesto: " + key)
        out[key] = value
    return out


def _read_limited(path: Path, *, max_bytes: int) -> bytes:
    # Works only on user-requested local files, never network URLs.
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("Arquivo ausente, inválido ou acima do limite de tamanho")
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError("Arquivo acima do limite de tamanho")
    return data


def _text_report(report: dict[str, Any], declared_clock: str) -> str:
    out = [
        "ATLASQUANT TRADER — COPOM | CONSULTA LAB / HARD NO-GO",
        "Relógio informado pelo operador (NÃO atestado): " + declared_clock,
        "Estado: " + report["state"],
        "Checkpoint original de 03/11 preservado: " +
        ("SIM, apenas integridade do conteúdo Git" if report[
            "pre_event_source_content_matches_original"] else "NÃO VERIFICADO"),
        "Resultado oficial Copom: " + report["decision_status"],
        "Horários da B3: " + report["session_status"],
        "Cotações WIN/WDO: " + report["quote_status"],
        "Viés para negociação: AGUARDAR",
        "Pendências independentes (" +
        str(len(report["missing_independent_evidence"])) + "):",
    ]
    for i, gap in enumerate(report["missing_independent_evidence"], 1):
        out.append("  " + str(i) + ". " + gap)
    if report["reason"] is not None:
        out.append("Motivo da recusa: " + report["reason"])
    out.extend([
        "Fonte e horário independentes, negociação e acerto NÃO foram comprovados.",
        "Sem coleta automática, Radar live, ordens, Worker, Render ou custos.",
    ])
    return "\n".join(out)


def run_copom_readiness_cli_lab(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resumo offline de prontidão Copom, sem ordens nem coleta B3")
    parser.add_argument("--as-of", required=True, metavar="UTC_ISO_Z",
                        help="Horário declarado, sem carimbo independente; AAAA-MM-DDTHH:MM:SSZ")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--csv", type=Path, help="Exportação local já autorizada, não coletada pelo CLI")
    parser.add_argument("--manifest", type=Path, help="Arquivo JSON local de origem/direitos do CSV")
    args = parser.parse_args(argv)

    try:
        when = _parse_clock(args.as_of)
        if (args.csv is None) != (args.manifest is None):
            raise ValueError("CSV e manifesto devem ser fornecidos juntos")
        frozen = _read_limited(PRE_EVENT_SNAPSHOT, max_bytes=4096)
        csv_data: bytes | None = None
        manifest: Any = None
        if args.csv is not None:
            csv_data = _read_limited(args.csv, max_bytes=MAX_CSV_BYTES)
            raw_manifest = _read_limited(args.manifest, max_bytes=MAX_MANIFEST_BYTES)
            manifest = json.loads(raw_manifest.decode("utf-8"),
                                  object_pairs_hook=_no_duplicate_keys)
        report = build_copom_evidence_readiness_lab(
            frozen, evaluated_at=when, price_export_csv=csv_data,
            price_export_manifest=manifest)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print("CONSULTA RECUSADA — " + str(exc), file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps({
            "mode": "LAB_HARD_NO_GO",
            "declared_clock_utc_unattested": args.as_of,
            "wall_clock_independently_verified": False,
            "report": report,
        }, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_text_report(report, args.as_of))
    return 2 if report["state"] == DENIED else 0


if __name__ == "__main__":
    raise SystemExit(run_copom_readiness_cli_lab())


__all__ = [
    "PRE_EVENT_SNAPSHOT", "MISSING_EVIDENCE", "run_copom_readiness_cli_lab",
]
