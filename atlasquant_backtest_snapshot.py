"""AtlasQuant reproducible Backtest snapshot / fingerprint tools.

A snapshot fingerprints:
- the original uploaded CSV bytes;
- normalized OHLC candle content;
- Backtest settings;
- relevant research code files;
- the consolidated evidence bundle.

The snapshot id is content-derived. Timestamps are metadata only and do not
change the id. Comparison is descriptive: it reports what changed without
ranking or promoting strategies.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import hashlib
import json
import math

import pandas as pd


SCHEMA="ATLASQUANT_BACKTEST_SNAPSHOT_V1"
ROOT=Path(__file__).resolve().parent
CODE_FILES=(
    "atlasquant_operational_backtest.py",
    "atlasquant_strategy_replay.py",
    "atlasquant_fvg_replay.py",
    "atlasquant_ote_replay.py",
    "atlasquant_crt_replay.py",
    "atlasquant_amd_replay.py",
    "atlasquant_strategy_comparator.py",
    "atlasquant_strategy_stability.py",
    "atlasquant_strategy_walkforward.py",
    "atlasquant_strategy_friction.py",
    "atlasquant_strategy_parameter_robustness.py",
    "atlasquant_backtest_evidence.py",
    "atlasquant_backtest_snapshot.py",
    "atlasquant_tradingview_parity.py",
    "atlasquant_backtest_panel.py",
    "tradingview/atlasquant_bos_choch_ob_strategy_v1.pine",
    "tradingview/atlasquant_fvg_strategy_v1.pine",
    "tradingview/atlasquant_ote_strategy_v1.pine",
    "tradingview/atlasquant_crt_strategy_v1.pine",
    "tradingview/atlasquant_amd_strategy_v1.pine",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value,pd.Timestamp):
        return value.isoformat()
    if isinstance(value,(str,bool,int)):
        return value
    if isinstance(value,float):
        return value if math.isfinite(value) else None
    if hasattr(value,"item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value,Mapping):
        return {str(k):_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",",":"),
    )


def settings_fingerprint(settings: Mapping[str,Any] | None) -> dict[str,Any]:
    values={str(k):_json_safe(v) for k,v in dict(settings or {}).items()}
    raw=canonical_json(values).encode("utf-8")
    return {"sha256":_sha256_bytes(raw),"values":values}


def normalized_candles_fingerprint(candles: pd.DataFrame) -> dict[str,Any]:
    if not isinstance(candles,pd.DataFrame) or candles.empty:
        payload={"rows":0,"columns":[],"records":[]}
        return {
            "sha256":_sha256_bytes(canonical_json(payload).encode("utf-8")),
            "rows":0,
            "start_time":None,
            "end_time":None,
        }

    preferred=[c for c in ("datetime","open","high","low","close","volume") if c in candles.columns]
    if not preferred:
        preferred=[str(c) for c in candles.columns]

    records=[]
    times=[]
    for _,row in candles[preferred].reset_index(drop=True).iterrows():
        item={}
        for col in preferred:
            value=row[col]
            if col=="datetime":
                ts=pd.to_datetime(value,utc=True,errors="coerce")
                safe=None if pd.isna(ts) else pd.Timestamp(ts).isoformat()
                if safe is not None:
                    times.append(pd.Timestamp(ts))
                item[col]=safe
            else:
                try:
                    num=float(value)
                    item[col]=round(num,12) if math.isfinite(num) else None
                except Exception:
                    item[col]=_json_safe(value)
        records.append(item)

    payload={"rows":len(records),"columns":preferred,"records":records}
    return {
        "sha256":_sha256_bytes(canonical_json(payload).encode("utf-8")),
        "rows":len(records),
        "start_time":min(times).isoformat() if times else None,
        "end_time":max(times).isoformat() if times else None,
    }


def code_fingerprint(
    *,
    root: Path | None = None,
    paths: Iterable[str] = CODE_FILES,
) -> dict[str,Any]:
    base=Path(root) if root is not None else ROOT
    files=[]
    for rel in paths:
        path=base/str(rel)
        if path.exists() and path.is_file():
            data=path.read_bytes()
            files.append({
                "path":str(rel),
                "sha256":_sha256_bytes(data),
                "bytes":len(data),
                "missing":False,
            })
        else:
            files.append({
                "path":str(rel),
                "sha256":None,
                "bytes":0,
                "missing":True,
            })
    aggregate=[{"path":x["path"],"sha256":x["sha256"],"missing":x["missing"]} for x in files]
    return {
        "sha256":_sha256_bytes(canonical_json(aggregate).encode("utf-8")),
        "files":files,
    }


def build_backtest_snapshot(
    *,
    raw_csv: bytes,
    candles: pd.DataFrame,
    settings: Mapping[str,Any],
    evidence_bundle: Mapping[str,Any],
    code_root: Path | None = None,
    code_paths: Iterable[str] = CODE_FILES,
) -> dict[str,Any]:
    raw=bytes(raw_csv or b"")
    raw_file={
        "sha256":_sha256_bytes(raw),
        "bytes":len(raw),
    }
    normalized=normalized_candles_fingerprint(candles)
    settings_fp=settings_fingerprint(settings)
    code_fp=code_fingerprint(root=code_root,paths=code_paths)
    evidence_safe=_json_safe(dict(evidence_bundle or {}))
    evidence_hash=_sha256_bytes(canonical_json(evidence_safe).encode("utf-8"))

    identity={
        "raw_csv_sha256":raw_file["sha256"],
        "normalized_data_sha256":normalized["sha256"],
        "settings_sha256":settings_fp["sha256"],
        "code_sha256":code_fp["sha256"],
        "evidence_sha256":evidence_hash,
    }
    snapshot_id=_sha256_bytes(canonical_json(identity).encode("utf-8"))

    return {
        "schema":SCHEMA,
        "snapshot_id":snapshot_id,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "research_only":True,
        "no_live_gate_effect":True,
        "identity":identity,
        "raw_csv":raw_file,
        "normalized_data":normalized,
        "settings":settings_fp,
        "code":code_fp,
        "evidence":{
            "sha256":evidence_hash,
            "bundle":evidence_safe,
        },
    }


def snapshot_json(snapshot: Mapping[str,Any]) -> str:
    return json.dumps(_json_safe(dict(snapshot)),ensure_ascii=False,sort_keys=True,indent=2)


def load_snapshot_json(raw: str | bytes) -> dict[str,Any]:
    text=raw.decode("utf-8-sig") if isinstance(raw,(bytes,bytearray)) else str(raw)
    data=json.loads(text)
    if not isinstance(data,dict) or data.get("schema")!=SCHEMA:
        raise ValueError("snapshot schema inválido")
    if not data.get("snapshot_id"):
        raise ValueError("snapshot sem snapshot_id")
    return data


def _settings_changes(a: Mapping[str,Any], b: Mapping[str,Any]) -> list[dict[str,Any]]:
    av=dict(((a.get("settings") or {}).get("values") or {}))
    bv=dict(((b.get("settings") or {}).get("values") or {}))
    rows=[]
    for key in sorted(set(av)|set(bv)):
        if av.get(key)!=bv.get(key):
            rows.append({"setting":key,"before":av.get(key),"after":bv.get(key)})
    return rows


def _evidence_rows(snapshot: Mapping[str,Any]) -> dict[str,dict[str,Any]]:
    bundle=((snapshot.get("evidence") or {}).get("bundle") or {})
    rows=bundle.get("evidence_summary") or []
    out={}
    for row in rows:
        if isinstance(row,dict) and row.get("strategy"):
            out[str(row["strategy"])]=dict(row)
    return out


def _metric_deltas(a: Mapping[str,Any], b: Mapping[str,Any]) -> list[dict[str,Any]]:
    aa=_evidence_rows(a)
    bb=_evidence_rows(b)
    metrics=("trades","expectancy_r","net_r","max_drawdown_r")
    rows=[]
    for strategy in sorted(set(aa)|set(bb)):
        before=aa.get(strategy,{})
        after=bb.get(strategy,{})
        item={"strategy":strategy}
        changed=False
        for metric in metrics:
            old=before.get(metric)
            new=after.get(metric)
            item[f"{metric}_before"]=old
            item[f"{metric}_after"]=new
            delta=None
            try:
                if old is not None and new is not None:
                    delta=round(float(new)-float(old),6)
            except Exception:
                delta=None
            item[f"{metric}_delta"]=delta
            if old!=new:
                changed=True
        if changed:
            rows.append(item)
    return rows


def compare_backtest_snapshots(
    before: Mapping[str,Any],
    after: Mapping[str,Any],
) -> dict[str,Any]:
    if before.get("schema")!=SCHEMA or after.get("schema")!=SCHEMA:
        raise ValueError("snapshot schema inválido")

    ai=dict(before.get("identity") or {})
    bi=dict(after.get("identity") or {})
    flags={
        "raw_csv_changed":ai.get("raw_csv_sha256")!=bi.get("raw_csv_sha256"),
        "normalized_data_changed":ai.get("normalized_data_sha256")!=bi.get("normalized_data_sha256"),
        "settings_changed":ai.get("settings_sha256")!=bi.get("settings_sha256"),
        "code_changed":ai.get("code_sha256")!=bi.get("code_sha256"),
        "evidence_changed":ai.get("evidence_sha256")!=bi.get("evidence_sha256"),
    }
    causes=[key.replace("_changed","") for key,value in flags.items() if value]
    return {
        "schema":"ATLASQUANT_BACKTEST_SNAPSHOT_DIFF_V1",
        "before_snapshot_id":before.get("snapshot_id"),
        "after_snapshot_id":after.get("snapshot_id"),
        "same_snapshot":before.get("snapshot_id")==after.get("snapshot_id"),
        **flags,
        "change_causes":causes,
        "settings_changes":_settings_changes(before,after),
        "evidence_metric_deltas":_metric_deltas(before,after),
        "note":"Deltas são descritivos; não indicam melhora, piora ou recomendação.",
    }
