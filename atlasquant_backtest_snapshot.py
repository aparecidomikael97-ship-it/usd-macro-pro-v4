"""AtlasQuant reproducible Backtest snapshot / fingerprint tools.

Snapshots are research/audit artifacts only. Loading is fail-closed: the
content-derived identity is recomputed and any tampering/incomplete identity
raises ValueError before comparison.
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
    "atlasquant_operational_backtest.py","atlasquant_strategy_replay.py",
    "atlasquant_fvg_replay.py","atlasquant_ote_replay.py","atlasquant_crt_replay.py",
    "atlasquant_amd_replay.py","atlasquant_strategy_comparator.py",
    "atlasquant_strategy_stability.py","atlasquant_strategy_walkforward.py",
    "atlasquant_strategy_friction.py","atlasquant_strategy_parameter_robustness.py",
    "atlasquant_backtest_evidence.py","atlasquant_backtest_snapshot.py",
    "atlasquant_tradingview_parity.py","atlasquant_backtest_panel.py",
    "tradingview/atlasquant_bos_choch_ob_strategy_v1.pine",
    "tradingview/atlasquant_fvg_strategy_v1.pine","tradingview/atlasquant_ote_strategy_v1.pine",
    "tradingview/atlasquant_crt_strategy_v1.pine","tradingview/atlasquant_amd_strategy_v1.pine",
)
IDENTITY_KEYS=("raw_csv_sha256","normalized_data_sha256","settings_sha256","code_sha256","evidence_sha256")

def _sha256_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()

def _json_safe(value: Any) -> Any:
    if value is None: return None
    if isinstance(value,pd.Timestamp): return value.isoformat()
    if isinstance(value,(str,bool,int)): return value
    if isinstance(value,float): return value if math.isfinite(value) else None
    if hasattr(value,"item"):
        try: return _json_safe(value.item())
        except Exception: pass
    try:
        if pd.isna(value): return None
    except Exception: pass
    if isinstance(value,Mapping): return {str(k):_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_json_safe(v) for v in value]
    return str(value)

def canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value),ensure_ascii=False,sort_keys=True,separators=(",",":"))

def settings_fingerprint(settings: Mapping[str,Any] | None) -> dict[str,Any]:
    values={str(k):_json_safe(v) for k,v in dict(settings or {}).items()}
    return {"sha256":_sha256_bytes(canonical_json(values).encode()),"values":values}

def normalized_candles_fingerprint(candles: pd.DataFrame) -> dict[str,Any]:
    if not isinstance(candles,pd.DataFrame) or candles.empty:
        payload={"rows":0,"columns":[],"records":[]}
        return {"sha256":_sha256_bytes(canonical_json(payload).encode()),"rows":0,"start_time":None,"end_time":None}
    preferred=[c for c in ("datetime","open","high","low","close","volume") if c in candles.columns] or [str(c) for c in candles.columns]
    records=[]; times=[]
    for _,row in candles[preferred].reset_index(drop=True).iterrows():
        item={}
        for col in preferred:
            value=row[col]
            if col=="datetime":
                ts=pd.to_datetime(value,utc=True,errors="coerce"); safe=None if pd.isna(ts) else pd.Timestamp(ts).isoformat()
                if safe is not None: times.append(pd.Timestamp(ts))
                item[col]=safe
            else:
                try:
                    num=float(value); item[col]=round(num,12) if math.isfinite(num) else None
                except Exception: item[col]=_json_safe(value)
        records.append(item)
    payload={"rows":len(records),"columns":preferred,"records":records}
    return {"sha256":_sha256_bytes(canonical_json(payload).encode()),"rows":len(records),"start_time":min(times).isoformat() if times else None,"end_time":max(times).isoformat() if times else None}

def code_fingerprint(*,root: Path|None=None,paths: Iterable[str]=CODE_FILES)->dict[str,Any]:
    base=Path(root) if root is not None else ROOT; files=[]
    for rel in paths:
        path=base/str(rel)
        if path.exists() and path.is_file():
            data=path.read_bytes(); files.append({"path":str(rel),"sha256":_sha256_bytes(data),"bytes":len(data),"missing":False})
        else: files.append({"path":str(rel),"sha256":None,"bytes":0,"missing":True})
    aggregate=[{"path":x["path"],"sha256":x["sha256"],"missing":x["missing"]} for x in files]
    return {"sha256":_sha256_bytes(canonical_json(aggregate).encode()),"files":files}

def _identity(raw_sha,normalized_sha,settings_sha,code_sha,evidence_sha):
    return dict(zip(IDENTITY_KEYS,(raw_sha,normalized_sha,settings_sha,code_sha,evidence_sha)))

def build_backtest_snapshot(*,raw_csv:bytes,candles:pd.DataFrame,settings:Mapping[str,Any],evidence_bundle:Mapping[str,Any],code_root:Path|None=None,code_paths:Iterable[str]=CODE_FILES)->dict[str,Any]:
    raw=bytes(raw_csv or b""); raw_file={"sha256":_sha256_bytes(raw),"bytes":len(raw)}
    normalized=normalized_candles_fingerprint(candles); settings_fp=settings_fingerprint(settings); code_fp=code_fingerprint(root=code_root,paths=code_paths)
    evidence_safe=_json_safe(dict(evidence_bundle or {})); evidence_hash=_sha256_bytes(canonical_json(evidence_safe).encode())
    identity=_identity(raw_file["sha256"],normalized["sha256"],settings_fp["sha256"],code_fp["sha256"],evidence_hash)
    snapshot_id=_sha256_bytes(canonical_json(identity).encode())
    return {"schema":SCHEMA,"snapshot_id":snapshot_id,"created_at":datetime.now(timezone.utc).isoformat(),"research_only":True,"no_live_gate_effect":True,"identity":identity,"raw_csv":raw_file,"normalized_data":normalized,"settings":settings_fp,"code":code_fp,"evidence":{"sha256":evidence_hash,"bundle":evidence_safe}}

def snapshot_json(snapshot:Mapping[str,Any])->str: return json.dumps(_json_safe(dict(snapshot)),ensure_ascii=False,sort_keys=True,indent=2)

def validate_snapshot(snapshot:Mapping[str,Any])->dict[str,Any]:
    data=dict(snapshot or {})
    if data.get("schema")!=SCHEMA: raise ValueError("snapshot schema inválido")
    identity=data.get("identity")
    if not isinstance(identity,dict) or any(not isinstance(identity.get(k),str) or len(identity.get(k))!=64 for k in IDENTITY_KEYS): raise ValueError("snapshot identity incompleta")
    settings=data.get("settings") or {}; evidence=data.get("evidence") or {}; raw=data.get("raw_csv") or {}; normalized=data.get("normalized_data") or {}; code=data.get("code") or {}
    expected=_identity(raw.get("sha256"),normalized.get("sha256"),settings_fingerprint(settings.get("values") or {})["sha256"],code.get("sha256"),_sha256_bytes(canonical_json(evidence.get("bundle") or {}).encode()))
    if identity!=expected: raise ValueError("snapshot adulterado: fingerprints internos não conferem")
    expected_id=_sha256_bytes(canonical_json(identity).encode())
    if data.get("snapshot_id")!=expected_id: raise ValueError("snapshot adulterado: snapshot_id não confere")
    if evidence.get("sha256")!=expected["evidence_sha256"]: raise ValueError("snapshot adulterado: evidence sha256 não confere")
    return data

def load_snapshot_json(raw:str|bytes)->dict[str,Any]:
    text=raw.decode("utf-8-sig") if isinstance(raw,(bytes,bytearray)) else str(raw)
    try: data=json.loads(text)
    except Exception as exc: raise ValueError("snapshot JSON inválido") from exc
    if not isinstance(data,dict): raise ValueError("snapshot deve ser objeto JSON")
    return validate_snapshot(data)

def _settings_changes(a,b):
    av=dict(((a.get("settings") or {}).get("values") or {})); bv=dict(((b.get("settings") or {}).get("values") or {})); return [{"setting":k,"before":av.get(k),"after":bv.get(k)} for k in sorted(set(av)|set(bv)) if av.get(k)!=bv.get(k)]

def _evidence_rows(snapshot):
    rows=(((snapshot.get("evidence") or {}).get("bundle") or {}).get("evidence_summary") or []); return {str(r["strategy"]):dict(r) for r in rows if isinstance(r,dict) and r.get("strategy")}

def _metric_deltas(a,b):
    aa=_evidence_rows(a); bb=_evidence_rows(b); metrics=("trades","expectancy_r","net_r","max_drawdown_r"); rows=[]
    for strategy in sorted(set(aa)|set(bb)):
        before=aa.get(strategy,{}); after=bb.get(strategy,{}); item={"strategy":strategy}; changed=False
        for metric in metrics:
            old=before.get(metric); new=after.get(metric); delta=None
            try:
                if old is not None and new is not None: delta=round(float(new)-float(old),6)
            except Exception: pass
            item.update({f"{metric}_before":old,f"{metric}_after":new,f"{metric}_delta":delta}); changed|=old!=new
        if changed: rows.append(item)
    return rows

def compare_backtest_snapshots(before:Mapping[str,Any],after:Mapping[str,Any])->dict[str,Any]:
    before=validate_snapshot(before); after=validate_snapshot(after); ai=before["identity"]; bi=after["identity"]
    flags={"raw_csv_changed":ai["raw_csv_sha256"]!=bi["raw_csv_sha256"],"normalized_data_changed":ai["normalized_data_sha256"]!=bi["normalized_data_sha256"],"settings_changed":ai["settings_sha256"]!=bi["settings_sha256"],"code_changed":ai["code_sha256"]!=bi["code_sha256"],"evidence_changed":ai["evidence_sha256"]!=bi["evidence_sha256"]}
    return {"schema":"ATLASQUANT_BACKTEST_SNAPSHOT_DIFF_V1","before_snapshot_id":before["snapshot_id"],"after_snapshot_id":after["snapshot_id"],"same_snapshot":before["snapshot_id"]==after["snapshot_id"],**flags,"change_causes":[k.replace("_changed","") for k,v in flags.items() if v],"settings_changes":_settings_changes(before,after),"evidence_metric_deltas":_metric_deltas(before,after),"note":"Deltas são descritivos; não indicam melhora, piora ou recomendação."}
