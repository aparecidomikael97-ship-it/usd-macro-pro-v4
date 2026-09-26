"""AtlasQuant session availability profiles.

Presentation/research helpers only. Session profiles prioritize information for
the user's available trading window; they do not create directions, orders or
profit probabilities.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

NY_TZ=ZoneInfo("America/New_York")

SESSION_PROFILES={
    "Todos os horários":("ASIA","LONDON","NEW_YORK","AFTER_NEW_YORK","TRANSITION","UNKNOWN"),
    "Noite/madrugada · Ásia + Londres":("ASIA","LONDON"),
    "Dia · Nova York + continuidade":("NEW_YORK","AFTER_NEW_YORK"),
}

# User-facing Radar filters. They only alias the profiles above.
SESSION_FILTERS=(
    ("Ambos","Todos os horários"),
    ("Noite","Noite/madrugada · Ásia + Londres"),
    ("Dia","Dia · Nova York + continuidade"),
)
SESSION_FILTER_OPTIONS=tuple(label for label,_profile in SESSION_FILTERS)

SESSION_LABELS={
    "ASIA":"Ásia",
    "LONDON":"Londres",
    "NEW_YORK":"Nova York",
    "AFTER_NEW_YORK":"Depois de Nova York",
    "TRANSITION":"Transição",
    "UNKNOWN":"Sessão não informada",
}


def _norm(value:Any)->str:
    return str(value or "").strip().casefold()


def session_bucket_from_label(value:Any)->str:
    raw=_norm(value)
    if not raw:
        return "UNKNOWN"
    if any(term in raw for term in ("asia","ásia","tokyo","tóquio","asian")):
        return "ASIA"
    if any(term in raw for term in ("london","londres")):
        return "LONDON"
    if any(term in raw for term in ("new york","nova york","ny killzone","ny am","ny pm")):
        return "NEW_YORK"
    if any(term in raw for term in ("after new york","depois de nova york","pós ny","pos ny")):
        return "AFTER_NEW_YORK"
    if any(term in raw for term in ("transition","transição","transicao","fora")):
        return "TRANSITION"
    return "UNKNOWN"


def session_bucket_from_timestamp(value:Any)->str:
    """Classify a timestamp into broad NY-time work windows.

    These are product availability buckets, not an exchange-hours oracle.
    DST is handled by America/New_York.
    """
    if value in (None,""):
        return "UNKNOWN"
    try:
        if isinstance(value,datetime):
            dt=value
        else:
            text=str(value)
            if text.endswith("Z"):
                text=text[:-1]+"+00:00"
            dt=datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=NY_TZ)
        ny=dt.astimezone(NY_TZ)
    except Exception:
        return "UNKNOWN"

    hour=ny.hour+ny.minute/60.0
    if hour>=19 or hour<2:
        return "ASIA"
    if 2<=hour<7:
        return "LONDON"
    if 7<=hour<12:
        return "NEW_YORK"
    if 12<=hour<18:
        return "AFTER_NEW_YORK"
    return "TRANSITION"


def extract_session_bucket(pack:Mapping[str,Any]|None)->str:
    p=dict(pack or {})
    candidates=(
        p.get("active_session"),
        p.get("session_name"),
        p.get("killzone"),
        p.get("session"),
    )
    for value in candidates:
        if isinstance(value,Mapping):
            value=value.get("name") or value.get("session") or value.get("label") or value.get("status")
        bucket=session_bucket_from_label(value)
        if bucket!="UNKNOWN":
            return bucket

    inst=dict(p.get("inst",{}) or {})
    inst_session=inst.get("session")
    if isinstance(inst_session,Mapping):
        for key in ("active_session","name","session","killzone"):
            bucket=session_bucket_from_label(inst_session.get(key))
            if bucket!="UNKNOWN":
                return bucket

    for key in ("updated_at","captured_at","processado_em"):
        bucket=session_bucket_from_timestamp(p.get(key))
        if bucket!="UNKNOWN":
            return bucket
    return "UNKNOWN"


def profile_for_filter(value:Any)->str:
    """Map Dia / Noite / Ambos, and the legacy labels, to one session profile."""
    raw=str(value or "").strip()
    if raw in SESSION_PROFILES:
        return raw
    folded=raw.casefold()
    for label, profile in SESSION_FILTERS:
        if folded==label.casefold() or folded==profile.casefold():
            return profile
    return "Todos os horários"


def filter_label_for_profile(value:Any)->str:
    profile=profile_for_filter(value)
    for label, candidate in SESSION_FILTERS:
        if candidate==profile:
            return label
    return "Ambos"


def normalize_session_profile(value:Any)->str:
    return profile_for_filter(value)


def session_profile_match(bucket:Any, profile:Any)->str:
    b=str(bucket or "UNKNOWN").strip().upper()
    p=normalize_session_profile(profile)
    if p=="Todos os horários":
        return "MATCH"
    if b=="UNKNOWN":
        return "UNKNOWN"
    return "MATCH" if b in SESSION_PROFILES[p] else "OUTSIDE"


def prioritize_rows_for_session(
    rows:Sequence[Mapping[str,Any]]|None,
    profile:Any,
)->list[dict[str,Any]]:
    p=normalize_session_profile(profile)
    out=[]
    for raw in list(rows or []):
        row=dict(raw)
        bucket=str(row.get("session_bucket") or extract_session_bucket(row)).upper()
        match=session_profile_match(bucket,p)
        row["session_bucket"]=bucket
        row["session_label"]=SESSION_LABELS.get(bucket,SESSION_LABELS["UNKNOWN"])
        row["session_profile"]=p
        row["session_match"]=match
        out.append(row)

    rank={"MATCH":0,"UNKNOWN":1,"OUTSIDE":2}
    out.sort(
        key=lambda x:(
            rank.get(str(x.get("session_match")),1),
            0 if str(x.get("action"))!="NÃO OPERAR" else 1,
            -float(x.get("priority",0) or 0),
            -float(x.get("data_score",0) or 0),
        )
    )
    return out


def session_profile_summary(
    rows:Sequence[Mapping[str,Any]]|None,
    profile:Any,
)->dict[str,Any]:
    prioritized=prioritize_rows_for_session(rows,profile)
    return {
        "profile":normalize_session_profile(profile),
        "total":len(prioritized),
        "matching":sum(1 for x in prioritized if x.get("session_match")=="MATCH"),
        "unknown":sum(1 for x in prioritized if x.get("session_match")=="UNKNOWN"),
        "outside":sum(1 for x in prioritized if x.get("session_match")=="OUTSIDE"),
        "real_orders_enabled":False,
        "automatic_execution":False,
        "interpretation":(
            "O perfil de sessão reorganiza a atenção conforme disponibilidade. "
            "Ele não cria viés, não aumenta score e não garante oportunidade."
        ),
    }


__all__=[
    "SESSION_PROFILES","SESSION_LABELS","SESSION_FILTERS","SESSION_FILTER_OPTIONS",
    "session_bucket_from_label","session_bucket_from_timestamp",
    "extract_session_bucket","normalize_session_profile",
    "profile_for_filter","filter_label_for_profile",
    "session_profile_match","prioritize_rows_for_session",
    "session_profile_summary",
]
