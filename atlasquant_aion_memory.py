"""AION canonical memory and Checkpoint Mestre persistence.

Static project memory is read from versioned AtlasQuant documents.
Mutable AION checkpoints are stored only on the dedicated runtime-data branch
when explicit GitHub runtime credentials are available.

This module never silently claims persistence. Every load/save returns a
truthful status with provenance.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import base64
import hashlib
import json
import os
import re
import unicodedata

import requests

from atlasquant_runtime_store import resolve_runtime_branch, require_runtime_branch
from atlasquant_aion_operations import normalize_queue, queue_digest
from atlasquant_aion_observability import normalize_events, events_digest
from atlasquant_aion_model_router import normalize_budget
from atlasquant_aion_studio import normalize_projects, studio_digest
from atlasquant_aion_business import normalize_products, business_digest
from atlasquant_aion_promotions import normalize_campaigns, promotion_digest

SCHEMA = "ATLASQUANT_AION_MEMORY_V1"
RUNTIME_PATH = "dados/aion/checkpoint_master.json"
MAX_DOC_BYTES = 1_500_000
MAX_RUNTIME_BYTES = 2_000_000
MAX_SEARCH_RESULTS = 8

CANONICAL_FILES = (
    "CONTEXTO_DO_PROJETO.md",
    "HISTORICO_DE_ALTERACOES.md",
    "docs/release/ATLASQUANT_RELEASE_FINAL.md",
)

APPROVED_AION_FOUNDATION = (
    "Prioridade: Interface + Modo Administrador + Central AION + Memória/Checkpoint + Segurança antes de novo refinamento operacional.",
    "AION oficial é assistente central do administrador: secretário, desenvolvedor, orquestrador, Guardian e memória persistente.",
    "AION deve atualizar o administrador sobre sistema, pendências, mercado quando houver dados frescos, clientes quando houver fonte confirmada e conteúdos aguardando aprovação.",
    "AION deve separar contextos: Trading, Studio, Negócios, Laboratório, Secretaria/Agenda, Desenvolvimento e Promoções.",
    "AION Studio deve preparar vídeos, imagens, roteiros, capas, legendas e conteúdo para Instagram, TikTok e YouTube; publicação externa permanece condicionada a aprovação e integração.",
    "AION Negócios deve apoiar pesquisa de produtos, tendências, margem, fornecedores e vendas em canais como Mercado Livre e TikTok Shop, isolado do núcleo de trading.",
    "Receita da área Negócios pode ser acompanhada contra custos do AtlasQuant para buscar sustentabilidade financeira do ecossistema.",
    "Administrador deve prever promoções/códigos/links com período grátis ou desconto; ativação real depende do provedor comercial e aprovação.",
    "AION Desenvolvedor deve usar Checkpoint Mestre, trabalhar por missões, revisar código/testes e nunca publicar mudança crítica sem aprovação.",
    "Camada de Verdade obrigatória: não inventar; declarar desconhecido quando não houver confirmação; separar fato, inferência e hipótese.",
    "Modo Custo Zero é padrão: nenhuma cobrança, upgrade ou serviço pago sem preço, justificativa, alternativa gratuita e aprovação.",
    "Feature Flags, permissões, observabilidade, privacidade/ciclo de vida dos dados, Sandbox, revisão, rollback e recuperação de desastre fazem parte da fundação.",
    "Interface deve ser futurística/premium com 3D/glass/microinterações, mas manter contraste, acessibilidade, velocidade e adaptação mobile.",
    "Assistente de voz deve ser contextual por área e opcional; não deve falar automaticamente sem controle do usuário.",
    "Fase futura: cada assinante poderá ter AION pessoal isolado; o AION oficial do administrador mantém privilégios superiores.",
    "Memória do AION deve carregar os registros canônicos do projeto desde 15/09/2026 e continuar com checkpoints versionados.",
    "Execução real em corretora continua bloqueada; backtest/paper/forward e pesquisa não equivalem a autorização real.",
)

STOPWORDS = {
    "a","o","as","os","de","da","do","das","dos","e","em","um","uma","para","por",
    "com","que","na","no","nas","nos","se","ao","aos","ou","como","mais","ser","ficar",
    "isso","esse","essa","ele","ela","eu","nos","nós",
}


@dataclass(frozen=True)
class RuntimeConfig:
    token: str
    repo: str
    branch: str
    path: str = RUNTIME_PATH

    @property
    def ready(self) -> bool:
        return bool(self.token and self.repo and self.branch)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _tokens(value: object) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9._/-]{2,}", _norm(value))
    return [w for w in words if w not in STOPWORDS]


def config_from_mapping(values: Mapping[str, Any] | None = None) -> RuntimeConfig:
    cfg = dict(values or {})
    token = str(
        cfg.get("GITHUB_TOKEN_HISTORICO")
        or os.getenv("GITHUB_TOKEN_HISTORICO", "")
        or ""
    ).strip()
    repo = str(
        cfg.get("GITHUB_REPO_HISTORICO")
        or os.getenv("GITHUB_REPO_HISTORICO", "")
        or ""
    ).strip()
    explicit = str(
        cfg.get("GITHUB_DATA_BRANCH")
        or os.getenv("GITHUB_DATA_BRANCH", "")
        or ""
    ).strip()
    legacy = str(
        cfg.get("GITHUB_BRANCH_HISTORICO")
        or os.getenv("GITHUB_BRANCH_HISTORICO", "")
        or ""
    ).strip()
    branch = resolve_runtime_branch(explicit, legacy)
    return RuntimeConfig(token=token, repo=repo, branch=branch)


def _safe_read(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        if path.stat().st_size > MAX_DOC_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def canonical_documents(base_dir: str | Path | None = None) -> list[dict[str, Any]]:
    root = Path(base_dir or Path(__file__).resolve().parent)
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()

    candidates = [root / rel for rel in CANONICAL_FILES]
    continuity = root / "docs" / "continuidade"
    if continuity.is_dir():
        candidates.extend(sorted(continuity.rglob("*.md"))[:80])

    for path in candidates:
        try:
            rel = str(path.relative_to(root)).replace("\\", "/")
        except Exception:
            rel = str(path)
        if rel in seen:
            continue
        seen.add(rel)
        text = _safe_read(path)
        if not text:
            continue
        docs.append({
            "path": rel,
            "text": text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "chars": len(text),
        })

    foundation = "\n".join(f"- {item}" for item in APPROVED_AION_FOUNDATION)
    docs.append({
        "path": "AION_APPROVED_FOUNDATION_2026-09-23",
        "text": foundation,
        "sha256": hashlib.sha256(foundation.encode("utf-8")).hexdigest(),
        "chars": len(foundation),
    })
    return docs


def canonical_memory_summary(base_dir: str | Path | None = None) -> dict[str, Any]:
    docs = canonical_documents(base_dir)
    return {
        "schema": SCHEMA,
        "status": "CONFIRMED" if docs else "UNKNOWN",
        "document_count": len(docs),
        "total_chars": sum(int(d.get("chars", 0)) for d in docs),
        "sources": [d["path"] for d in docs],
        "foundation_items": len(APPROVED_AION_FOUNDATION),
        "checked_at": _now(),
    }


def search_canonical_memory(
    query: object,
    *,
    base_dir: str | Path | None = None,
    limit: int = MAX_SEARCH_RESULTS,
) -> list[dict[str, Any]]:
    tokens = list(dict.fromkeys(_tokens(query)))
    if not tokens:
        return []
    hits: list[dict[str, Any]] = []
    for doc in canonical_documents(base_dir):
        text = str(doc["text"])
        normalized = _norm(text)
        score = sum(normalized.count(tok) for tok in tokens)
        if score <= 0:
            continue
        lines = text.splitlines()
        best_line = ""
        best_score = -1
        for line in lines:
            nline = _norm(line)
            line_score = sum(2 if tok in nline else 0 for tok in tokens)
            if line_score > best_score and line.strip():
                best_score = line_score
                best_line = line.strip()
        excerpt = best_line[:700] if best_line else text[:700]
        hits.append({
            "path": doc["path"],
            "score": score + max(0, best_score),
            "excerpt": excerpt,
            "sha256": doc["sha256"],
        })
    hits.sort(key=lambda x: (-int(x["score"]), str(x["path"])))
    return hits[: max(1, min(int(limit or MAX_SEARCH_RESULTS), MAX_SEARCH_RESULTS))]


def default_checkpoint() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "checkpoint_version": 4,
        "created_at": _now(),
        "updated_at": _now(),
        "project": "AtlasQuant",
        "aion": {
            "version": "0.1-foundation",
            "priority": "AION + Interface + Administrador",
            "truth_policy": "never_invent",
            "cost_mode": "ZERO_COST_DEFAULT",
            "real_trading": False,
            "model_budget": normalize_budget({}),
        },
        "areas": {
            "central": "FOUNDATION",
            "trading": "CONNECTED_READ_ONLY",
            "studio": "WORKSPACE_READY_EXTERNAL_PUBLISH_OFF",
            "business": "WORKSPACE_READY_EXTERNAL_PUBLISH_OFF",
            "laboratory": "CONNECTED_SAFE",
            "secretary": "FOUNDATION",
            "development": "FOUNDATION",
            "promotions": "WORKSPACE_READY_PROVIDER_ACTIVATION_OFF",
        },
        "approved_foundation": list(APPROVED_AION_FOUNDATION),
        "pending": [
            "Validar AION em produção privada.",
            "Configurar provedor de modelo externo somente se aprovado e necessário.",
            "Configurar integrações sociais/marketplaces somente atrás de feature flags.",
            "Validar persistência runtime do Checkpoint Mestre.",
        ],
        "evidence": {
            "canonical_sources": list(CANONICAL_FILES),
            "conversation_seed": "approved project decisions consolidated on 2026-09-23",
        },
        "operating": {
            "tasks": [],
            "events": [],
            "task_digest": queue_digest([]),
            "event_digest": events_digest([]),
            "dirty": False,
        },
        "studio": {
            "projects": [],
            "digest": studio_digest([]),
        },
        "business": {
            "products": [],
            "digest": business_digest([]),
        },
        "promotions": {
            "campaigns": [],
            "redemptions": [],
            "digest": promotion_digest([], []),
        },
    }


def ensure_operating_checkpoint(checkpoint: Mapping[str, Any] | None) -> dict[str, Any]:
    """Upgrade older checkpoints in memory without inventing persisted state."""
    payload = dict(checkpoint or {})
    if not payload:
        payload = default_checkpoint()
    aion = payload.get("aion")
    if not isinstance(aion, dict):
        aion = {}
        payload["aion"] = aion
    aion["model_budget"] = normalize_budget(
        aion.get("model_budget") if isinstance(aion.get("model_budget"), Mapping) else {}
    )

    studio = payload.get("studio")
    if not isinstance(studio, Mapping):
        studio = {}
    studio_projects = normalize_projects(
        studio.get("projects") if isinstance(studio, Mapping) else []
    )
    payload["studio"] = {
        "projects": studio_projects,
        "digest": studio_digest(studio_projects),
    }

    business = payload.get("business")
    if not isinstance(business, Mapping):
        business = {}
    business_products = normalize_products(
        business.get("products") if isinstance(business, Mapping) else []
    )
    payload["business"] = {
        "products": business_products,
        "digest": business_digest(business_products),
    }

    promotions = payload.get("promotions")
    if not isinstance(promotions, Mapping):
        promotions = {}
    promo_campaigns = normalize_campaigns(
        promotions.get("campaigns") if isinstance(promotions, Mapping) else []
    )
    promo_redemptions = [
        dict(x) for x in list(
            promotions.get("redemptions") if isinstance(promotions, Mapping) else []
        )[:2000]
        if isinstance(x, Mapping)
    ]
    payload["promotions"] = {
        "campaigns": promo_campaigns,
        "redemptions": promo_redemptions,
        "digest": promotion_digest(promo_campaigns, promo_redemptions),
    }

    operating = payload.get("operating")
    if not isinstance(operating, Mapping):
        operating = {}
    tasks = normalize_queue(operating.get("tasks") if isinstance(operating, Mapping) else [])
    events = normalize_events(operating.get("events") if isinstance(operating, Mapping) else [])
    payload["checkpoint_version"] = max(4, int(payload.get("checkpoint_version") or 1))
    payload["operating"] = {
        "tasks": tasks,
        "events": events,
        "task_digest": queue_digest(tasks),
        "event_digest": events_digest(events),
        "dirty": bool((operating or {}).get("dirty", False)),
    }
    return payload


def update_operating_checkpoint(
    checkpoint: Mapping[str, Any] | None,
    *,
    tasks: Any = None,
    events: Any = None,
    dirty: bool = True,
) -> dict[str, Any]:
    """Return a normalized checkpoint with task/event operating memory."""
    payload = ensure_operating_checkpoint(checkpoint)
    current = payload["operating"]
    task_rows = normalize_queue(current["tasks"] if tasks is None else tasks)
    event_rows = normalize_events(current["events"] if events is None else events)
    payload["operating"] = {
        "tasks": task_rows,
        "events": event_rows,
        "task_digest": queue_digest(task_rows),
        "event_digest": events_digest(event_rows),
        "dirty": bool(dirty),
    }
    payload["updated_at"] = _now()
    return payload


def update_studio_checkpoint(
    checkpoint: Mapping[str, Any] | None,
    *,
    projects: Any,
    dirty: bool = True,
) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    rows = normalize_projects(projects)
    payload["studio"] = {
        "projects": rows,
        "digest": studio_digest(rows),
    }
    payload["operating"]["dirty"] = bool(dirty)
    payload["updated_at"] = _now()
    return payload


def update_business_checkpoint(
    checkpoint: Mapping[str, Any] | None,
    *,
    products: Any,
    dirty: bool = True,
) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    rows = normalize_products(products)
    payload["business"] = {
        "products": rows,
        "digest": business_digest(rows),
    }
    payload["operating"]["dirty"] = bool(dirty)
    payload["updated_at"] = _now()
    return payload


def update_promotions_checkpoint(
    checkpoint: Mapping[str, Any] | None,
    *,
    campaigns: Any,
    redemptions: Any = None,
    dirty: bool = True,
) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    rows = normalize_campaigns(campaigns)
    current = payload.get("promotions") if isinstance(payload.get("promotions"), Mapping) else {}
    redemption_rows = [
        dict(x) for x in list(
            current.get("redemptions", []) if redemptions is None else redemptions
        )[:2000]
        if isinstance(x, Mapping)
    ]
    payload["promotions"] = {
        "campaigns": rows,
        "redemptions": redemption_rows,
        "digest": promotion_digest(rows, redemption_rows),
    }
    payload["operating"]["dirty"] = bool(dirty)
    payload["updated_at"] = _now()
    return payload


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _contents_url(cfg: RuntimeConfig) -> str:
    return f"https://api.github.com/repos/{cfg.repo}/contents/{cfg.path}"


def load_runtime_checkpoint(
    config: RuntimeConfig | None = None,
    *,
    timeout: float = 12.0,
) -> dict[str, Any]:
    cfg = config or config_from_mapping()
    try:
        require_runtime_branch(cfg.branch)
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "source": "runtime",
            "checkpoint": None,
            "reason": f"unsafe runtime branch: {type(exc).__name__}",
            "checked_at": _now(),
        }
    if not cfg.ready:
        return {
            "schema": SCHEMA,
            "status": "UNAVAILABLE",
            "source": "runtime",
            "checkpoint": None,
            "reason": "GitHub runtime credentials not configured.",
            "checked_at": _now(),
        }
    try:
        response = requests.get(
            _contents_url(cfg),
            headers=_headers(cfg.token),
            params={"ref": cfg.branch},
            timeout=timeout,
        )
        if response.status_code == 404:
            return {
                "schema": SCHEMA,
                "status": "NOT_FOUND",
                "source": f"GitHub:{cfg.branch}:{cfg.path}",
                "checkpoint": None,
                "sha": "",
                "reason": "Checkpoint Mestre ainda não existe no runtime.",
                "checked_at": _now(),
            }
        response.raise_for_status()
        obj = response.json()
        raw = base64.b64decode(str(obj.get("content") or "")).decode("utf-8")
        if len(raw.encode("utf-8")) > MAX_RUNTIME_BYTES:
            raise ValueError("runtime checkpoint too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("checkpoint is not an object")
        return {
            "schema": SCHEMA,
            "status": "CONFIRMED",
            "source": f"GitHub:{cfg.branch}:{cfg.path}",
            "checkpoint": payload,
            "sha": str(obj.get("sha") or ""),
            "reason": "",
            "checked_at": _now(),
        }
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "ERROR",
            "source": f"GitHub:{cfg.branch}:{cfg.path}",
            "checkpoint": None,
            "sha": "",
            "reason": type(exc).__name__,
            "checked_at": _now(),
        }


def save_runtime_checkpoint(
    checkpoint: Mapping[str, Any],
    config: RuntimeConfig | None = None,
    *,
    approved: bool = False,
    expected_sha: str = "",
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Persist a checkpoint only after explicit administrator approval."""
    cfg = config or config_from_mapping()
    if not approved:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "reason": "Explicit administrator approval required.",
            "checked_at": _now(),
        }
    try:
        require_runtime_branch(cfg.branch)
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "reason": f"unsafe runtime branch: {type(exc).__name__}",
            "checked_at": _now(),
        }
    if not cfg.ready:
        return {
            "schema": SCHEMA,
            "status": "UNAVAILABLE",
            "saved": False,
            "reason": "GitHub runtime credentials not configured.",
            "checked_at": _now(),
        }
    payload = dict(checkpoint or {})
    payload["schema"] = SCHEMA
    payload["updated_at"] = _now()
    raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str).encode("utf-8")
    if len(raw) > MAX_RUNTIME_BYTES:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "reason": "Checkpoint exceeds size limit.",
            "checked_at": _now(),
        }
    body: dict[str, Any] = {
        "message": "AION: atualizar Checkpoint Mestre",
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": cfg.branch,
    }
    if str(expected_sha or "").strip():
        body["sha"] = str(expected_sha).strip()
    try:
        response = requests.put(
            _contents_url(cfg),
            headers=_headers(cfg.token),
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        obj = response.json()
        content = obj.get("content") if isinstance(obj, dict) else {}
        return {
            "schema": SCHEMA,
            "status": "CONFIRMED",
            "saved": True,
            "source": f"GitHub:{cfg.branch}:{cfg.path}",
            "sha": str((content or {}).get("sha") or ""),
            "checked_at": _now(),
        }
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "ERROR",
            "saved": False,
            "reason": type(exc).__name__,
            "checked_at": _now(),
        }


def merged_checkpoint(
    runtime_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Prefer confirmed mutable runtime checkpoint, otherwise return static seed.

    The returned provenance makes fallback explicit.
    """
    result = dict(runtime_result or {})
    if result.get("status") == "CONFIRMED" and isinstance(result.get("checkpoint"), Mapping):
        return {
            "checkpoint": ensure_operating_checkpoint(result["checkpoint"]),
            "provenance": result.get("source", "runtime"),
            "runtime_confirmed": True,
        }
    return {
        "checkpoint": ensure_operating_checkpoint(default_checkpoint()),
        "provenance": "static-seed",
        "runtime_confirmed": False,
        "runtime_status": result.get("status", "UNAVAILABLE"),
    }


def checkpoint_digest(checkpoint: Mapping[str, Any] | None) -> str:
    raw = json.dumps(dict(checkpoint or {}), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def checkpoint_source_digest(checkpoint: Mapping[str, Any] | None) -> str:
    """Stable digest for conflict detection, ignoring volatile timestamps/dirty flag."""
    payload = ensure_operating_checkpoint(checkpoint)
    payload = deepcopy(payload)
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    operating = payload.get("operating")
    if isinstance(operating, dict):
        operating["dirty"] = False
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
