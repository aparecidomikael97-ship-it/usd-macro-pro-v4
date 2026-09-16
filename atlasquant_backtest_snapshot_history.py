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
    return f"{_safe_created_at(clean)}_{clean['snapshot_id'][:16]}.json"


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

    for existing in directory.glob(f"*_{clean['snapshot_id'][:16]}.json"):
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
        "schema":"ATLASQUANT_BACKTEST_SNAPSHOT_HISTORY_V1",
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
