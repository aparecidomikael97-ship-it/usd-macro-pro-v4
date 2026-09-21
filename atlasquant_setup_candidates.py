"""AtlasQuant model-specific setup candidate attribution.

Builds explicit research candidates from model-owned detector outputs at capture
time. A candidate is NOT a trade signal, order, recommendation, or strategy
promotion. The source model supplies the setup_id by construction; nothing is
inferred later from gain/loss.
"""
from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping

SCHEMA="ATLASQUANT_SETUP_CANDIDATES_V1"

MODEL_SPECS={
    "crt":{
        "setup_id":"crt",
        "label":"CRT",
        "timeframe":"H1",
        "confirmed_statuses":{"🟢 CRT CONFIRMADO"},
        "confirmed_phases":{"DISTRIBUIÇÃO"},
    },
    "ote":{
        "setup_id":"ote",
        "label":"OTE / Fibonacci",
        "timeframe":"H1",
        "confirmed_statuses":{"🟢 DENTRO DO OTE"},
        "confirmed_phases":set(),
    },
    "amd":{
        "setup_id":"amd-po3",
        "label":"AMD / PO3",
        "timeframe":"M15",
        "confirmed_statuses":{"🟢 AMD / PO3 EM DISTRIBUIÇÃO"},
        "confirmed_phases":{"DISTRIBUIÇÃO"},
    },
    "fvg":{
        "setup_id":"fvg",
        "label":"FVG / desequilíbrio",
        "timeframe":"M15",
        "confirmed_statuses":{"🟢 FVG EM TESTE"},
        "confirmed_phases":set(),
    },
}

_EVIDENCE_KEYS={
    "crt":("status","score","phase","raid_side","anchor_high","anchor_low","target","invalidation"),
    "ote":("status","score","retracement_pct","zone_low","zone_high","sweet_705","swing_low","swing_high","price"),
    "amd":("status","score","phase","acc_high","acc_low","target","manipulation_side"),
    "fvg":("status","score","zone_low","zone_high","price"),
}

_EPISODE_KEYS={
    "crt":("status","phase","raid_side","anchor_high","anchor_low"),
    "ote":("status","zone_low","zone_high","swing_low","swing_high"),
    "amd":("status","phase","acc_high","acc_low","manipulation_side"),
    "fvg":("status","zone_low","zone_high"),
}


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if isfinite(out) else None
    except Exception:
        return None


def _clean_evidence(model_key:str,raw:Mapping[str,Any]|None)->dict[str,Any]:
    source=dict(raw or {})
    out={}
    for key in _EVIDENCE_KEYS.get(model_key,()):
        value=source.get(key)
        if key=="score":
            value=_finite(value)
        if value not in (None,""):
            out[key]=value
    return out


def _candidate_id(payload:Mapping[str,Any])->str:
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def _episode_id(
    *,
    model_key:str,
    pair:str,
    side:str,
    setup_id:str,
    evidence:Mapping[str,Any],
)->str:
    stable={
        key:evidence.get(key)
        for key in _EPISODE_KEYS.get(model_key,())
        if evidence.get(key) not in (None,"")
    }
    payload={
        "pair":pair,
        "side":side,
        "setup_id":setup_id,
        "source_model":model_key.upper(),
        "stable_evidence":stable,
    }
    return _candidate_id(payload)


def build_setup_candidates(
    *,
    pair:object,
    side:object,
    ict_snapshot:Mapping[str,Any]|None,
    captured_at:object,
)->dict[str,Any]:
    pair_name=str(pair or "").strip().upper()
    direction=str(side or "").strip().upper()
    captured=str(captured_at or "").strip()
    snapshot=dict(ict_snapshot or {})

    rows=[]
    for model_key,spec in MODEL_SPECS.items():
        raw=dict(snapshot.get(model_key,{}) or {})
        evidence=_clean_evidence(model_key,raw)
        status=str(raw.get("status") or "").strip()
        phase=str(raw.get("phase") or "").strip().upper()
        score=_finite(raw.get("score"))
        confirmed=bool(
            direction in {"BUY","SELL"}
            and captured
            and (
                status in spec["confirmed_statuses"]
                or (phase and phase in spec["confirmed_phases"] and status.startswith("🟢"))
            )
        )
        identity={
            "pair":pair_name,
            "side":direction,
            "setup_id":spec["setup_id"],
            "captured_at":captured,
            "status":status,
            "evidence":evidence,
        }
        rows.append({
            "candidate_id":_candidate_id(identity),
            "episode_id":_episode_id(
                model_key=model_key,
                pair=pair_name,
                side=direction,
                setup_id=spec["setup_id"],
                evidence=evidence,
            ),
            "setup_id":spec["setup_id"],
            "setup_label":spec["label"],
            "source_model":model_key.upper(),
            "source_timeframe":spec["timeframe"],
            "pair":pair_name,
            "side":direction,
            "captured_at":captured,
            "status":status,
            "score":score,
            "research_candidate":confirmed,
            "setup_attribution":"SOURCE_MODEL_EXPLICIT",
            "evidence":evidence,
            "paper_trade_created":False,
            "automatic_execution":False,
            "automatic_promotion":False,
            "real_orders_enabled":False,
        })

    confirmed=[x for x in rows if x["research_candidate"]]
    return {
        "schema":SCHEMA,
        "pair":pair_name,
        "side":direction,
        "captured_at":captured,
        "models":rows,
        "candidates":confirmed,
        "candidate_count":len(confirmed),
        "setup_inference_from_outcome":False,
        "automatic_paper_entry":False,
        "automatic_execution":False,
        "real_orders_enabled":False,
        "interpretation":(
            "Candidatos são atribuídos pelo detector de origem no instante da captura. "
            "Eles servem para pesquisa/observação e não criam operação Paper ou real automaticamente."
        ),
    }


def candidate_rows(pack:Mapping[str,Any]|None)->list[dict[str,Any]]:
    rows=[]
    for raw in list(dict(pack or {}).get("candidates",[]) or []):
        row=dict(raw)
        rows.append({
            "candidate_id":row.get("candidate_id"),
            "episode_id":row.get("episode_id"),
            "setup_id":row.get("setup_id"),
            "pair":row.get("pair"),
            "side":row.get("side"),
            "captured_at":row.get("captured_at"),
            "status":row.get("status"),
            "score":row.get("score"),
            "source_model":row.get("source_model"),
            "source_timeframe":row.get("source_timeframe"),
            "research_candidate":bool(row.get("research_candidate")),
        })
    return rows


__all__=[
    "SCHEMA",
    "MODEL_SPECS",
    "build_setup_candidates",
    "candidate_rows",
]
