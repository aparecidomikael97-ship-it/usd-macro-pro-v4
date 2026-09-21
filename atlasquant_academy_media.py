"""AtlasQuant Academy media preparation.

Builds deterministic educational video scripts/storyboards from the Academy text.
It does not call video/TTS providers, upload media, change trading logic or mark
unrendered videos as published.
"""
from __future__ import annotations

from typing import Any
import json
from atlasquant_academy import ACADEMY_TOPICS, academy_topic

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
    return {
        "schema":SCHEMA,
        "topic_id":topic["id"],
        "title":topic["title"],
        "category":topic["category"],
        "level":topic["level"],
        "narration":narration,
        "scenes":scenes,
        "estimated_seconds":seconds,
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

def academy_media_manifest()->dict[str,Any]:
    rows=academy_media_catalog()
    queue=[]
    for index,item in enumerate(rows,1):
        if not item:
            continue
        queue.append({
            "order":index,
            "topic_id":item["topic_id"],
            "title":item["title"],
            "category":item["category"],
            "level":item["level"],
            "estimated_seconds":item["estimated_seconds"],
            "narration":item["narration"],
            "scenes":item["scenes"],
            "suggested_filename":f"atlasquant_academy_{index:02d}_{item['topic_id']}.mp4",
            "status":"SCRIPT_READY_MEDIA_PENDING",
        })
    return {
        "schema":"ATLASQUANT_ACADEMY_PRODUCTION_MANIFEST_V1",
        "items":queue,
        "total_items":len(queue),
        "all_scripts_ready":bool(queue and all(x["status"]=="SCRIPT_READY_MEDIA_PENDING" for x in queue)),
        "rendered_items":0,
        "published_items":0,
        "external_render_required":True,
        "automatic_publish":False,
        "trading_side_effects":False,
    }


def academy_media_manifest_json()->str:
    return json.dumps(academy_media_manifest(),ensure_ascii=False,indent=2,sort_keys=True)


def academy_media_bundle_markdown()->str:
    manifest=academy_media_manifest()
    lines=[
        "# AtlasQuant Academy — pacote de produção de vídeos",
        "",
        f"Total de roteiros: {manifest['total_items']}",
        "",
        "Status: roteiros prontos; mídia ainda não renderizada/publicada.",
        "",
    ]
    for item in manifest["items"]:
        lines.extend([
            f"## {item['order']:02d}. {item['title']}",
            f"- Topic ID: `{item['topic_id']}`",
            f"- Categoria: {item['category']}",
            f"- Nível: {item['level']}",
            f"- Duração estimada: {item['estimated_seconds']}s",
            f"- Arquivo sugerido: `{item['suggested_filename']}`",
            "",
            "### Narração",
            item["narration"],
            "",
            "### Storyboard",
        ])
        for scene in item["scenes"]:
            lines.append(f"{scene['order']}. **{scene['title']}** — {scene['text']}")
        lines.extend(["","---",""])
    return "\n".join(lines).strip()+"\n"

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

__all__=[
    "SCHEMA","academy_video_script","academy_media_catalog","academy_video_scripts_ready",
    "academy_media_manifest","academy_media_manifest_json","academy_media_bundle_markdown",
    "academy_media_readiness",
]
