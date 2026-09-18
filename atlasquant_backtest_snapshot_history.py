"""AtlasQuant local research history for Backtest snapshots.

This store is intentionally separate from operational dados/ and from the
runtime-data branch. Saving is explicit, local and research-only.

On ephemeral hosting the local directory may disappear between deployments, so
the UI also supports exporting the whole history as a ZIP archive.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Mapping
import json
import os
import tempfile
import zipfile

import pandas as pd

from atlasquant_backtest_snapshot import (
    SCHEMA,
    compare_backtest_snapshots,
    snapshot_json,
    validate_snapshot,
)


DEFAULT_HISTORY_DIR=Path(".atlasquant_research")/"backtest_snapshots"
HISTORY_SCHEMA="ATLASQUANT_BACKTEST_SNAPSHOT_HISTORY_V1"
MAX_ARCHIVE_FILES=1000
MAX_ARCHIVE_SNAPSHOTS=500
MAX_ARCHIVE_UNCOMPRESSED_BYTES=100*1024*1024
MAX_SNAPSHOT_BYTES=10*1024*1024


def resolve_history_dir(root: str | Path | None = None) -> Path:
    path=Path(root) if root is not None else DEFAULT_HISTORY_DIR
    return path.expanduser()


def _safe_created_at(snapshot: Mapping[str,Any]) -> str:
    raw=str(snapshot.get("created_at") or "").strip()
    ts=pd.to_datetime(raw,utc=True,errors="coerce")
    if pd.isna(ts):
        ts=pd.Timestamp(datetime.now(timezone.utc))
    return pd.Timestamp(ts).strftime("%Y%m%dT%H%M%SZ")


def snapshot_history_filename(snapshot: Mapping[str,Any]) -> str:
    clean=validate_snapshot(snapshot)
    return f"{_safe_created_at(clean)}_{clean['snapshot_id']}.json"


def save_snapshot_local(
    snapshot: Mapping[str,Any],
    *,
    root: str | Path | None = None,
) -> dict[str,Any]:
    """Persist one validated snapshot atomically in the research-only store."""
    clean=validate_snapshot(snapshot)
    directory=resolve_history_dir(root)
    directory.mkdir(parents=True,exist_ok=True)
    filename=snapshot_history_filename(clean)
    path=directory/filename

    for existing in directory.glob("*.json"):
        try:
            loaded=load_snapshot_file(existing)
        except Exception:
            continue
        if loaded.get("snapshot_id")==clean["snapshot_id"]:
            return {
                "ok":True,
                "reason":"ALREADY_PRESENT",
                "path":str(existing),
                "snapshot_id":clean["snapshot_id"],
            }

    raw=snapshot_json(clean).encode("utf-8")
    fd,tmp=tempfile.mkstemp(prefix=".tmp_snapshot_",suffix=".json",dir=str(directory))
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    return {
        "ok":True,
        "reason":"SAVED",
        "path":str(path),
        "snapshot_id":clean["snapshot_id"],
    }


def load_snapshot_file(path: str | Path) -> dict[str,Any]:
    p=Path(path)
    try:
        data=json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"snapshot local inválido: {p.name}") from exc
    if not isinstance(data,dict) or data.get("schema")!=SCHEMA:
        raise ValueError(f"snapshot local com schema inválido: {p.name}")
    return validate_snapshot(data)


def load_snapshot_history(
    *,
    root: str | Path | None = None,
) -> dict[str,Any]:
    """Load valid snapshots and report invalid files without silently trusting them."""
    directory=resolve_history_dir(root)
    if not directory.exists():
        return {
            "root":str(directory),
            "snapshots":[],
            "invalid_files":[],
        }

    valid=[]
    invalid=[]
    for path in sorted(directory.glob("*.json")):
        try:
            snap=load_snapshot_file(path)
        except Exception as exc:
            invalid.append({"file":path.name,"error":f"{type(exc).__name__}: {exc}"})
            continue
        snap=dict(snap)
        snap["_history_file"]=path.name
        valid.append(snap)

    valid.sort(
        key=lambda x:(
            str(x.get("created_at") or ""),
            str(x.get("snapshot_id") or ""),
        )
    )
    return {
        "root":str(directory),
        "snapshots":valid,
        "invalid_files":invalid,
    }


def history_timeline_frame(snapshots: Iterable[Mapping[str,Any]]) -> pd.DataFrame:
    rows=[]
    for raw in snapshots:
        snap=validate_snapshot(raw)
        bundle=((snap.get("evidence") or {}).get("bundle") or {})
        settings=((snap.get("settings") or {}).get("values") or {})
        normalized=snap.get("normalized_data") or {}
        rows.append({
            "created_at":snap.get("created_at"),
            "snapshot_id":snap.get("snapshot_id"),
            "pair":bundle.get("pair") or settings.get("pair") or "",
            "candles":normalized.get("rows"),
            "data_start":normalized.get("start_time"),
            "data_end":normalized.get("end_time"),
            "cost_r":settings.get("cost_r"),
            "slippage_r":settings.get("slippage_r"),
            "parameter_robustness_ran":settings.get("parameter_robustness_ran"),
            "raw_csv_fp":str((snap.get("identity") or {}).get("raw_csv_sha256") or "")[:12],
            "data_fp":str((snap.get("identity") or {}).get("normalized_data_sha256") or "")[:12],
            "settings_fp":str((snap.get("identity") or {}).get("settings_sha256") or "")[:12],
            "code_fp":str((snap.get("identity") or {}).get("code_sha256") or "")[:12],
            "evidence_fp":str((snap.get("identity") or {}).get("evidence_sha256") or "")[:12],
        })
    if not rows:
        return pd.DataFrame()
    out=pd.DataFrame(rows)
    out["created_at"]=pd.to_datetime(out["created_at"],utc=True,errors="coerce")
    return out.sort_values(["created_at","snapshot_id"]).reset_index(drop=True)


def consecutive_history_diffs(
    snapshots: Iterable[Mapping[str,Any]],
) -> pd.DataFrame:
    valid=[validate_snapshot(x) for x in snapshots]
    valid.sort(key=lambda x:(str(x.get("created_at") or ""),str(x.get("snapshot_id") or "")))
    rows=[]
    for before,after in zip(valid,valid[1:]):
        diff=compare_backtest_snapshots(before,after)
        rows.append({
            "before_created_at":before.get("created_at"),
            "after_created_at":after.get("created_at"),
            "before_snapshot_id":before.get("snapshot_id"),
            "after_snapshot_id":after.get("snapshot_id"),
            "same_snapshot":diff.get("same_snapshot"),
            "raw_csv_changed":diff.get("raw_csv_changed"),
            "normalized_data_changed":diff.get("normalized_data_changed"),
            "settings_changed":diff.get("settings_changed"),
            "code_changed":diff.get("code_changed"),
            "evidence_changed":diff.get("evidence_changed"),
            "settings_changes":len(diff.get("settings_changes") or []),
            "evidence_metric_changes":len(diff.get("evidence_metric_deltas") or []),
            "change_causes":",".join(diff.get("change_causes") or []),
        })
    return pd.DataFrame(rows)


def history_archive_zip(
    snapshots: Iterable[Mapping[str,Any]],
) -> bytes:
    valid=[validate_snapshot(x) for x in snapshots]
    timeline=history_timeline_frame(valid)
    diffs=consecutive_history_diffs(valid)
    manifest={
        "schema":HISTORY_SCHEMA,
        "research_only":True,
        "no_live_gate_effect":True,
        "snapshot_count":len(valid),
        "snapshot_ids":[x["snapshot_id"] for x in valid],
    }

    buf=BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True),
        )
        zf.writestr("timeline.csv",timeline.to_csv(index=False))
        zf.writestr("changes.csv",diffs.to_csv(index=False))
        for snap in valid:
            zf.writestr(
                f"snapshots/{snapshot_history_filename(snap)}",
                snapshot_json(snap),
            )
    return buf.getvalue()



def _safe_archive_member(name: str) -> bool:
    raw=str(name or "")
    if not raw or raw.startswith(("/", "\\")):
        return False
    normalized=raw.replace("\\","/")
    parts=[p for p in normalized.split("/") if p not in ("", ".")]
    if any(p==".." for p in parts):
        return False
    return normalized in {"manifest.json","timeline.csv","changes.csv"} or (
        len(parts)==2
        and parts[0]=="snapshots"
        and parts[1].endswith(".json")
        and parts[1] not in (".json","..json")
    )


def inspect_history_archive(raw_zip: bytes | bytearray | memoryview) -> dict[str,Any]:
    """Validate an exported history ZIP fully in memory before any local write.

    The archive is rejected as a whole when structure, size, manifest or any
    snapshot fails validation. timeline.csv/changes.csv are treated as
    convenience exports only; they are never trusted for restoration.
    """
    raw=bytes(raw_zip or b"")
    if not raw:
        raise ValueError("arquivo ZIP vazio")

    try:
        zf=zipfile.ZipFile(BytesIO(raw),"r")
    except Exception as exc:
        raise ValueError("arquivo ZIP inválido") from exc

    with zf:
        infos=zf.infolist()
        if len(infos)>MAX_ARCHIVE_FILES:
            raise ValueError("arquivo ZIP excede o limite de arquivos")

        if any(int(info.file_size) < 0 or int(info.compress_size) < 0 for info in infos):
            raise ValueError("arquivo ZIP contém metadados de tamanho inválidos")
        total_uncompressed=sum(int(info.file_size) for info in infos)
        if total_uncompressed>MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValueError("arquivo ZIP excede o limite de tamanho descompactado")

        names=[info.filename for info in infos]
        if len(names)!=len(set(names)):
            raise ValueError("arquivo ZIP contém nomes duplicados")
        if any(info.flag_bits & 0x1 for info in infos):
            raise ValueError("arquivo ZIP criptografado não é suportado")
        if any(not _safe_archive_member(name) for name in names):
            raise ValueError("arquivo ZIP contém caminho ou arquivo não permitido")
        if "manifest.json" not in names:
            raise ValueError("manifest.json ausente")
        manifest_info=next(info for info in infos if info.filename=="manifest.json")
        if int(manifest_info.file_size)>MAX_SNAPSHOT_BYTES:
            raise ValueError("manifest.json excede o limite de tamanho")

        try:
            manifest=json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception as exc:
            raise ValueError("manifest.json inválido") from exc

        if not isinstance(manifest,dict) or manifest.get("schema")!=HISTORY_SCHEMA:
            raise ValueError("schema do histórico inválido")
        if manifest.get("research_only") is not True or manifest.get("no_live_gate_effect") is not True:
            raise ValueError("manifesto do histórico sem flags de segurança")

        snapshot_infos=[
            info for info in infos
            if info.filename.replace("\\","/").startswith("snapshots/")
            and info.filename.lower().endswith(".json")
        ]
        if len(snapshot_infos)>MAX_ARCHIVE_SNAPSHOTS:
            raise ValueError("histórico excede o limite de snapshots")

        snapshots=[]
        seen_ids=set()
        for info in snapshot_infos:
            if int(info.file_size)>MAX_SNAPSHOT_BYTES:
                raise ValueError(f"snapshot excede o limite de tamanho: {info.filename}")
            try:
                data=json.loads(zf.read(info).decode("utf-8"))
            except Exception as exc:
                raise ValueError(f"snapshot JSON inválido: {info.filename}") from exc
            if not isinstance(data,dict):
                raise ValueError(f"snapshot inválido: {info.filename}")
            try:
                clean=validate_snapshot(data)
            except Exception as exc:
                raise ValueError(f"snapshot falhou na integridade: {info.filename}: {exc}") from exc
            sid=str(clean.get("snapshot_id") or "")
            if sid in seen_ids:
                raise ValueError("histórico contém snapshot_id duplicado")
            seen_ids.add(sid)
            snapshots.append(clean)

        declared_count=manifest.get("snapshot_count")
        if not isinstance(declared_count,int) or declared_count!=len(snapshots):
            raise ValueError("snapshot_count do manifesto não confere")

        declared_ids=manifest.get("snapshot_ids")
        if not isinstance(declared_ids,list) or any(not isinstance(x,str) for x in declared_ids):
            raise ValueError("snapshot_ids do manifesto inválido")
        if len(declared_ids)!=len(set(declared_ids)):
            raise ValueError("manifesto contém snapshot_ids duplicados")
        if len(declared_ids)!=declared_count:
            raise ValueError("quantidade de snapshot_ids do manifesto não confere")
        if any(len(x)!=64 or any(ch not in "0123456789abcdef" for ch in x.lower()) for x in declared_ids):
            raise ValueError("manifesto contém snapshot_id inválido")
        if set(declared_ids)!=seen_ids:
            raise ValueError("snapshot_ids do manifesto não conferem")

        # Force CRC/decompression validation for every member after structural limits.
        bad=zf.testzip()
        if bad is not None:
            raise ValueError(f"arquivo ZIP corrompido: {bad}")

        snapshots.sort(
            key=lambda x:(str(x.get("created_at") or ""),str(x.get("snapshot_id") or ""))
        )
        return {
            "schema":HISTORY_SCHEMA,
            "snapshot_count":len(snapshots),
            "snapshot_ids":[x["snapshot_id"] for x in snapshots],
            "snapshots":snapshots,
            "archive_files":len(infos),
            "uncompressed_bytes":total_uncompressed,
        }


def restore_history_archive(
    raw_zip: bytes | bytearray | memoryview,
    *,
    root: str | Path | None = None,
) -> dict[str,Any]:
    """Validate the whole archive first, then merge snapshots into local history.

    Existing identical snapshots are preserved and counted as duplicates.
    No file from the ZIP is extracted directly to disk.
    """
    inspected=inspect_history_archive(raw_zip)
    saved=0
    duplicates=0
    paths=[]
    for snap in inspected["snapshots"]:
        result=save_snapshot_local(snap,root=root)
        paths.append(result.get("path"))
        if result.get("reason")=="ALREADY_PRESENT":
            duplicates+=1
        elif result.get("reason")=="SAVED":
            saved+=1
        else:
            raise ValueError("falha inesperada ao restaurar snapshot")

    return {
        "ok":True,
        "reason":"RESTORED",
        "snapshots_validated":inspected["snapshot_count"],
        "saved":saved,
        "duplicates":duplicates,
        "root":str(resolve_history_dir(root)),
        "paths":paths,
    }
