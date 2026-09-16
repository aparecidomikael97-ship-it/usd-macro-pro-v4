"""AtlasQuant Flight Recorder Panel V1.

Session-safe adapter for the AtlasQuant journal foundation. It records only
already-computed decisions/blocks, deduplicates identical states, and exposes a
CSV export. It does not create entries, stops, targets or trade results.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from typing import Any, Mapping, Sequence
import math
import streamlit as st

from atlasquant_journal import make_decision_record, make_blocked_record, to_csv
from atlasquant_flight_recorder_store import persist_records, load_persistent_records
from atlasquant_runtime_store import resolve_runtime_branch


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out=float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def decision_fingerprint(pack: Mapping[str, Any] | None, engine_version: str) -> str:
    p=dict(pack or {})
    dr=dict(p.get("data_ready", {}) or {})
    payload={
        "engine_version": str(engine_version),
        "pair": str(p.get("pair","—")),
        "side": str(p.get("side","NEUTRAL")),
        "state": str(p.get("state","—")),
        "executable": bool(p.get("executable",False)),
        "priority": round(_num(p.get("priority",0)),2),
        "score": round(_num(p.get("score",0)),2),
        "quality": round(_num(p.get("quality",0)),2),
        "data_score": round(_num(dr.get("score",0)),2),
        "data_sufficient": bool(dr.get("sufficient",False)),
        "gate": str(p.get("gate","—")),
        "m15": str(p.get("m15","—")),
        "event": str(p.get("event","—")),
        "hard_blocks": [str(x) for x in (p.get("hard_blocks",[]) or [])],
        "soft_blocks": [str(x) for x in (p.get("soft_blocks",[]) or [])],
    }
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def record_from_pack(pack: Mapping[str, Any] | None, engine_version: str) -> dict[str, Any]:
    p=dict(pack or {})
    dr=dict(p.get("data_ready", {}) or {})
    pair=str(p.get("pair","—"))
    side=str(p.get("side","NEUTRAL")).upper()
    executable=bool(p.get("executable",False))
    sufficient=bool(dr.get("sufficient",False))
    hard=[str(x) for x in (p.get("hard_blocks",[]) or [])]
    soft=[str(x) for x in (p.get("soft_blocks",[]) or [])]
    reason=str(p.get("reason","—"))

    snapshot={
        "state": str(p.get("state","—")),
        "direction": str(p.get("direction","—")),
        "priority": _num(p.get("priority",0)),
        "score": _num(p.get("score",0)),
        "quality": _num(p.get("quality",0)),
        "data_score": _num(dr.get("score",0)),
        "data_sufficient": sufficient,
        "gate": str(p.get("gate","—")),
        "m15": str(p.get("m15","—")),
        "h1": str(p.get("h1","—")),
        "h4": str(p.get("h4","—")),
        "event": str(p.get("event","—")),
        "next_action": str(p.get("next_action","—")),
        "target": str(p.get("target","—")),
    }
    fp=decision_fingerprint(p,engine_version)

    if executable and sufficient and side in ("BUY","SELL"):
        record=make_decision_record(
            asset=pair,
            side=side,
            directional_score=_num(p.get("score",0)),
            data_quality=_num(dr.get("score",0)),
            engine_version=str(engine_version),
            reasons=[reason] + [str(x) for x in (p.get("positives",[]) or [])[:5]],
            contradictions=hard + soft,
            model_versions={"institutional":"pair_intelligence_v110"},
            snapshot=snapshot,
        )
        record["record_type"]="DECISION"
    else:
        reasons=list(hard)
        if not sufficient:
            reasons.append("Dados insuficientes ou sem frescor operacional")
        if not executable and not reasons:
            reasons.append(str(p.get("state","AGUARDAR CONFIRMAÇÃO")))
        record=make_blocked_record(
            asset=pair,
            reasons=reasons,
            engine_version=str(engine_version),
            snapshot=snapshot,
        )
        record["record_type"]="BLOCKED"
        record["side"]=side if side in ("BUY","SELL") else "NO_TRADE"
    record["_fingerprint"]=fp
    return record


def append_unique(records: Sequence[Mapping[str, Any]] | None, record: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    rows=[dict(x) for x in (records or [])]
    fp=str(record.get("_fingerprint",""))
    if fp and any(str(x.get("_fingerprint",""))==fp for x in rows):
        return rows,False
    rows.append(dict(record))
    return rows,True


def recorder_summary(records: Sequence[Mapping[str, Any]] | None) -> dict[str, int]:
    rows=list(records or [])
    return {
        "records":len(rows),
        "decisions":sum(1 for x in rows if x.get("record_type")=="DECISION"),
        "blocked":sum(1 for x in rows if x.get("record_type")=="BLOCKED"),
    }


def _secret_or_env(key: str, default: str = "") -> str:
    try:
        value=st.secrets.get(key, os.getenv(key, default))
    except Exception:
        value=os.getenv(key, default)
    return str(value or "").strip()


def runtime_persistence_config() -> dict[str, str]:
    repo=_secret_or_env(
        "GITHUB_REPO_HISTORICO",
        os.getenv("GITHUB_REPOSITORY", "aparecidomikael97-ship-it/usd-macro-pro-v4"),
    )
    branch=resolve_runtime_branch(
        _secret_or_env("GITHUB_DATA_BRANCH", ""),
        _secret_or_env("GITHUB_BRANCH_HISTORICO", ""),
    )
    token=_secret_or_env("GITHUB_TOKEN_HISTORICO", os.getenv("GITHUB_TOKEN", ""))
    return {"repo":repo,"branch":branch,"token":token}


def persist_current_record(record: Mapping[str, Any]) -> dict[str, Any]:
    cfg=runtime_persistence_config()
    return persist_records(
        [record],
        repo=cfg["repo"],
        branch=cfg["branch"],
        token=cfg["token"],
    )


def hydrate_persistent_records(
    session_records: Sequence[Mapping[str, Any]] | None,
    remote_records: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    rows=[dict(x) for x in (remote_records or [])]
    for raw in (session_records or []):
        row=dict(raw)
        rows,_=append_unique(rows,row)
    return rows


def load_remote_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg=runtime_persistence_config()
    if not cfg["repo"] or not cfg["token"]:
        return [],{"ok":False,"reason":"NOT_CONFIGURED","records":0,"error":""}
    try:
        rows=load_persistent_records(
            repo=cfg["repo"],
            branch=cfg["branch"],
            token=cfg["token"],
        )
        return rows,{"ok":True,"reason":"LOADED","records":len(rows),"error":""}
    except Exception as exc:
        return [],{
            "ok":False,
            "reason":"LOAD_ERROR",
            "records":0,
            "error":f"{type(exc).__name__}: {exc}",
        }


def prepare_flight_capture(
    existing: Sequence[Mapping[str, Any]] | None,
    pack: Mapping[str, Any] | None,
    engine_version: str,
) -> dict[str, Any]:
    current=record_from_pack(pack,engine_version)
    rows,added=append_unique(existing,current)
    return {
        "current":current,
        "rows":rows,
        "added":added,
        "summary":recorder_summary(rows),
    }


def capture_flight_recorder(
    pack: Mapping[str, Any] | None,
    engine_version: str,
) -> dict[str, Any]:
    key="atlasquant_session_flight_recorder"
    hydrated_key="atlasquant_flight_recorder_hydrated"
    load_status_key="atlasquant_flight_recorder_load_status"

    session_rows=list(st.session_state.get(key,[]) or [])
    if not bool(st.session_state.get(hydrated_key,False)):
        remote_rows,load_status=load_remote_records()
        session_rows=hydrate_persistent_records(session_rows,remote_rows)
        st.session_state[key]=session_rows
        st.session_state[hydrated_key]=True
        st.session_state[load_status_key]=load_status

    capture=prepare_flight_capture(
        session_rows,
        pack,
        engine_version,
    )
    st.session_state[key]=capture["rows"]

    persistence=st.session_state.get("atlasquant_flight_recorder_persistence", {})
    if capture["added"]:
        try:
            persistence=persist_current_record(capture["current"])
        except Exception as exc:
            persistence={
                "ok":False,"added":0,"records":0,
                "reason":"PERSISTENCE_EXCEPTION",
                "error":f"{type(exc).__name__}: {exc}",
            }
        st.session_state["atlasquant_flight_recorder_persistence"]=persistence

    capture["persistence"]=persistence
    capture["load_status"]=dict(
        st.session_state.get(
            load_status_key,
            {"ok":False,"reason":"NOT_LOADED","records":0,"error":""},
        ) or {}
    )
    return capture


def render_flight_recorder(
    pack: Mapping[str, Any] | None,
    engine_version: str,
    *,
    capture_result: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    capture=dict(capture_result or capture_flight_recorder(pack,engine_version))
    rows=list(capture.get("rows",[]) or [])
    added=bool(capture.get("added",False))
    summary=dict(capture.get("summary",recorder_summary(rows)) or {})
    persistence=dict(capture.get("persistence",{}) or {})
    load_status=dict(capture.get("load_status",{}) or {})

    st.markdown("### 🧾 Flight Recorder")
    st.caption(
        "Registro automático com hidratação do histórico persistente. "
        "Guarda decisões e bloqueios sem inventar resultado de trade."
    )
    c1,c2,c3=st.columns(3)
    c1.metric("Registros",summary["records"])
    c2.metric("Decisões liberadas",summary["decisions"])
    c3.metric("Bloqueios/esperas",summary["blocked"])
    if added:
        st.caption("Novo estado operacional registrado nesta sessão.")
    else:
        st.caption("Estado idêntico ao último registro; duplicidade evitada.")

    if persistence:
        reason=str(persistence.get("reason",""))
        if bool(persistence.get("ok",False)):
            if reason=="SAVED":
                st.caption(
                    f"☁️ Persistência runtime: +{int(persistence.get('added',0))} registro(s) · "
                    f"{int(persistence.get('records',0))} no histórico persistente."
                )
            elif reason=="ALREADY_PRESENT":
                st.caption("☁️ Estado já existente no Flight Recorder persistente; duplicidade remota evitada.")
        elif reason=="NOT_CONFIGURED":
            st.caption("Persistência permanente aguardando credencial GitHub; registro da sessão preservado localmente.")
        else:
            st.warning(
                "Flight Recorder persistente indisponível neste ciclo; "
                "a decisão da sessão continua preservada localmente."
            )
            if persistence.get("error"):
                st.caption(f"Diagnóstico: {persistence.get('reason','ERRO')} · {persistence.get('error')}")

    if load_status:
        if bool(load_status.get("ok",False)):
            st.caption(
                f"📚 Histórico persistente carregado: {int(load_status.get('records',0))} registro(s)."
            )
        elif load_status.get("reason")=="NOT_CONFIGURED":
            st.caption("Histórico persistente ainda não carregado: credencial GitHub indisponível nesta execução.")
        elif load_status.get("reason") not in ("","NOT_LOADED"):
            st.caption(
                f"Histórico persistente não pôde ser carregado: {load_status.get('reason')}."
            )

    export_rows=[{k:v for k,v in row.items() if k!="_fingerprint"} for row in rows]
    csv_data=to_csv(export_rows)
    st.download_button(
        "📥 Exportar Flight Recorder (CSV)",
        data=csv_data,
        file_name="atlasquant_flight_recorder.csv",
        mime="text/csv",
        disabled=not bool(csv_data),
    )
    return summary
