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


def _explicit_false_flag(value:Any)->bool:
    """Only a proven false value can mean 'not invalidated'.

    Missing/ambiguous flags fail closed so an old or partial institutional
    payload cannot become a research candidate.
    """
    if value is False:
        return True
    if isinstance(value,bool):
        return False
    if isinstance(value,(int,float)):
        try:
            return isfinite(float(value)) and float(value)==0.0
        except Exception:
            return False
    return str(value or "").strip().casefold() in {"false","0","nao","não","no"}


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
    institutional_snapshot:Mapping[str,Any]|None=None,
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

    # Fifth research model: structure break + explicit Order Block.
    # It is appended after the four ICT-owned models because its evidence comes
    # from the institutional snapshot generated from the same closed M15 data.
    institutional=dict(institutional_snapshot or {})
    structure=dict(institutional.get("structure",{}) or {})
    order_block=dict(institutional.get("order_block",{}) or {})

    structure_event=str(structure.get("event") or "").strip().upper()
    structure_side=str(structure.get("event_side") or "").strip().upper()
    structure_status=str(structure.get("status") or "").strip()
    ob_status=str(order_block.get("status") or "").strip()
    ob_side=str(order_block.get("side") or "").strip().upper()
    zone_low=_finite(order_block.get("zone_low"))
    zone_high=_finite(order_block.get("zone_high"))
    zone_valid=bool(
        zone_low is not None
        and zone_high is not None
        and zone_low < zone_high
    )
    ob_not_invalidated=_explicit_false_flag(order_block.get("invalidated"))

    structure_valid=bool(
        structure_event in {"BOS","CHOCH"}
        and structure_side==direction
        and structure_status.startswith("🟢")
    )
    ob_valid=bool(
        "ORDER BLOCK" in ob_status.upper()
        and "SEM ORDER BLOCK" not in ob_status.upper()
        and "INVALIDADO" not in ob_status.upper()
        and ob_side==direction
        and ob_not_invalidated
        and zone_valid
    )

    bos_ob_evidence={
        key:value for key,value in {
            "structure_status":structure_status,
            "structure_event":structure_event,
            "structure_side":structure_side,
            "structure_level":structure.get("level"),
            "break_time":structure.get("break_time"),
            "order_block_status":ob_status,
            "order_block_side":ob_side,
            "zone_low":zone_low,
            "zone_high":zone_high,
            "origin_time":order_block.get("origin_time"),
            "mitigation_depth_pct":_finite(order_block.get("mitigation_depth_pct")),
            "invalidated":order_block.get("invalidated"),
        }.items() if value not in (None,"")
    }
    bos_confirmed=bool(
        direction in {"BUY","SELL"}
        and captured
        and structure_valid
        and ob_valid
    )
    bos_score_candidates=[
        x for x in (
            _finite(structure.get("score")),
            _finite(order_block.get("score")),
        ) if x is not None
    ]
    bos_score=min(bos_score_candidates) if len(bos_score_candidates)==2 else None
    bos_identity={
        "pair":pair_name,
        "side":direction,
        "setup_id":"bos-choch-ob",
        "captured_at":captured,
        "status":f"{structure_event} + {ob_status}".strip(" +"),
        "evidence":bos_ob_evidence,
    }
    bos_episode=_candidate_id({
        "pair":pair_name,
        "side":direction,
        "setup_id":"bos-choch-ob",
        "structure_event":structure_event,
        "break_time":structure.get("break_time"),
        "zone_low":zone_low,
        "zone_high":zone_high,
        "origin_time":order_block.get("origin_time"),
    })
    rows.append({
        "candidate_id":_candidate_id(bos_identity),
        "episode_id":bos_episode,
        "setup_id":"bos-choch-ob",
        "setup_label":"BOS/CHOCH + Order Block",
        "source_model":"BOS_CHOCH_OB",
        "source_timeframe":"M15",
        "pair":pair_name,
        "side":direction,
        "captured_at":captured,
        "status":bos_identity["status"] or "SEM EVIDÊNCIA INSTITUCIONAL",
        "score":bos_score,
        "research_candidate":bos_confirmed,
        "setup_attribution":"SOURCE_MODEL_EXPLICIT",
        "evidence":bos_ob_evidence,
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
