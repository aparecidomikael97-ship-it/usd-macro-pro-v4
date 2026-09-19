"""AtlasQuant Academy media preparation.

Builds deterministic educational video scripts/storyboards from the Academy text.
It does not call video/TTS providers, upload media, change trading logic or mark
unrendered videos as published.
"""
from __future__ import annotations

from typing import Any
from atlasquant_academy import ACADEMY_TOPICS, academy_topic
from atlasquant_academy_video_blueprints import video_blueprint

SCHEMA="ATLASQUANT_ACADEMY_MEDIA_V1"

def academy_video_script(topic_id: object)->dict[str,Any] | None:
    topic=academy_topic(topic_id)
    if topic is None:
        return None
    narration=(
        f"{topic['title']}. {topic['summary']} "
        f"O que observar: {topic['watch']} "
        f"Ligação com Forex: {topic['forex']} "
        f"Erro comum: {topic['pitfall']} "
        "Use este conteúdo como educação e contexto; não como promessa de resultado ou sinal automático."
    )
    scenes=[
        {"order":1,"title":"Conceito","text":topic["summary"]},
        {"order":2,"title":"O que observar","text":topic["watch"]},
        {"order":3,"title":"Aplicação no Forex","text":topic["forex"]},
        {"order":4,"title":"Erro comum","text":topic["pitfall"]},
        {"order":5,"title":"Fechamento","text":"Contexto educacional; valide dados, risco e Safety Core antes de qualquer decisão."},
    ]
    words=len(narration.split())
    seconds=max(45,min(180,round(words/2.35)))
    blueprint=video_blueprint(topic["id"])
    return {
        "schema":SCHEMA,
        "topic_id":topic["id"],
        "title":topic["title"],
        "category":topic["category"],
        "level":topic["level"],
        "narration":narration,
        "scenes":scenes,
        "estimated_seconds":seconds,
        "detailed_blueprint_seconds":int((blueprint or {}).get("total_seconds",0)),
        "detailed_blueprint_ready":bool(blueprint and blueprint.get("within_20_min")),
        "script_ready":True,
        "rendered_video":False,
        "published_video":False,
        "trading_side_effects":False,
    }

def academy_media_catalog()->list[dict[str,Any]]:
    return [academy_video_script(x["id"]) for x in ACADEMY_TOPICS]

def academy_video_scripts_ready()->bool:
    rows=academy_media_catalog()
    ids=[str(x["topic_id"]) for x in rows if x]
    expected=[str(x["id"]) for x in ACADEMY_TOPICS]
    return (
        bool(rows)
        and ids==expected
        and len(ids)==len(set(ids))
        and all(bool(x.get("script_ready")) and len(x.get("scenes",[]))==5 for x in rows)
        and all(not x.get("rendered_video") and not x.get("published_video") for x in rows)
    )

def academy_media_readiness()->dict[str,Any]:
    rows=academy_media_catalog()
    scripts=sum(1 for x in rows if x and x.get("script_ready"))
    rendered=sum(1 for x in rows if x and x.get("rendered_video"))
    published=sum(1 for x in rows if x and x.get("published_video"))
    return {
        "schema":SCHEMA,
        "topics":len(rows),
        "scripts_ready":scripts,
        "all_scripts_ready":academy_video_scripts_ready(),
        "rendered_videos":rendered,
        "published_videos":published,
        "academy_video_ready":bool(rows and published==len(rows)),
        "automatic_publish":False,
        "trading_side_effects":False,
    }

__all__=["SCHEMA","academy_video_script","academy_media_catalog","academy_video_scripts_ready","academy_media_readiness"]
