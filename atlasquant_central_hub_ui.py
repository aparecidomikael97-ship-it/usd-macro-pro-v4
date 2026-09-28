"""Central AtlasQuant e Home AION IA.

Pure presentation and access checks. The role already lives on the access
mapping produced by the existing gate. This module does not create accounts
or a second admin source, and it does not execute anything.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

from atlasquant_ui_v1 import hero_html, section_title_html, state_badge_html

_AREA_ORDER = ("aion", "negocios", "trader", "investimentos")

_AREAS = {
    "aion": {
        "label": "AION IA",
        "sentence": "Inteligência do ecossistema, ainda em construção.",
        "private": True,
    },
    "negocios": {
        "label": "Negócios",
        "sentence": "Casca visual de crescimento e receita.",
        "private": True,
    },
    "trader": {
        "label": "Trader",
        "sentence": "Console operacional já existente do AtlasQuant.",
        "private": False,
    },
    "investimentos": {
        "label": "Renda Fixa / Investimentos",
        "sentence": "Casca visual de proteção e patrimônio.",
        "private": True,
    },
}

_AION_MODULES = (
    {
        "id": "administracao",
        "title": "Administração",
        "sentence": "Sessão, papéis e portas do ecossistema.",
        "dependency": "",
    },
    {
        "id": "memoria",
        "title": "Memória / Checkpoint Mestre",
        "sentence": "Registro mestre do que a AION já consolidou.",
        "dependency": "",
    },
    {
        "id": "desenvolvedor",
        "title": "Desenvolvedor",
        "sentence": "Contratos e revisão antes de qualquer execução.",
        "dependency": "Memória / Checkpoint Mestre",
    },
    {
        "id": "pesquisa",
        "title": "Pesquisa",
        "sentence": "Leitura e hipóteses ainda sem publicação.",
        "dependency": "",
    },
    {
        "id": "voz",
        "title": "Voz",
        "sentence": "Canal de fala da AION, ainda sem operação.",
        "dependency": "",
    },
    {
        "id": "conteudo",
        "title": "Conteúdo",
        "sentence": "Peças e roteiros ainda não publicados.",
        "dependency": "",
    },
    {
        "id": "automacao",
        "title": "Automação",
        "sentence": "Rotinas futuras, sem disparo nesta camada.",
        "dependency": "Desenvolvedor",
    },
    {
        "id": "seguranca",
        "title": "Segurança",
        "sentence": "Limites e fail-closed desta central.",
        "dependency": "Administração",
    },
    {
        "id": "observabilidade",
        "title": "Observabilidade",
        "sentence": "Sinais de saúde ainda sem fonte ligada.",
        "dependency": "Segurança",
    },
)

_CENTRAL_CSS = """
<style>
.aq-central-layout{display:grid;grid-template-columns:228px minmax(0,1fr);gap:16px;align-items:start;margin:0 0 18px}
.aq-central-rail{display:flex;flex-direction:column;gap:8px;min-width:0}
.aq-central-rail-fold{display:flex;flex-direction:column;gap:8px;padding:12px;border:1px solid var(--aq-line);border-radius:18px;background:linear-gradient(180deg,rgba(12,18,36,.94),rgba(7,17,31,.92));box-shadow:0 16px 40px rgba(0,0,0,.22)}
.aq-central-rail-fold>summary{display:none;cursor:pointer;color:var(--aq-text);font-size:.78rem;font-weight:800;letter-spacing:.08em;list-style:none}
.aq-central-kicker{color:var(--aq-warn);font-size:.62rem;font-weight:800;letter-spacing:.14em;margin:0 2px 2px}
.aq-central-link{display:flex;flex-direction:column;gap:2px;text-decoration:none;color:var(--aq-text);border:1px solid transparent;border-radius:14px;padding:10px 12px;background:rgba(8,16,32,.55)}
.aq-central-link small{color:var(--aq-muted);font-size:.68rem;font-weight:650}
.aq-central-link strong{font-size:.92rem}
.aq-central-priority{border-color:var(--aq-aion,#b48cff);box-shadow:inset 0 0 0 1px rgba(180,140,255,.28)}
.aq-central-link[aria-current="page"]{background:rgba(180,140,255,.14)}
.aq-central-stage{min-width:0}
.aq-central-card,.aq-aion-module{border:1px solid var(--aq-line);border-radius:18px;padding:14px;background:linear-gradient(180deg,rgba(16,24,46,.92),rgba(7,17,31,.9));min-width:0}
.aq-central-card h2,.aq-aion-module h3{margin:.35rem 0 .2rem;color:var(--aq-text);font-size:1rem}
.aq-central-card p,.aq-aion-module p{margin:0;color:var(--aq-muted);font-size:.8rem;line-height:1.35}
.aq-central-art{display:block;width:72px;height:48px}
.aq-aion-module .aq-central-art{width:42px;height:42px}
.aq-aion-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-top:12px}
.aq-central-denied{margin:0;color:var(--aq-warn);font-size:.82rem;font-weight:750}
.aq-aion-home .aq-hero{margin-bottom:8px}
@media (max-width:760px){
  .aq-central-layout{grid-template-columns:1fr;gap:10px}
  .aq-central-rail-fold{padding:8px}
  .aq-central-rail-fold>summary{display:flex;align-items:center;min-height:36px}
  .aq-central-link{padding:8px 10px}
  .aq-aion-grid{grid-template-columns:1fr}
}
</style>
"""


def _role(access: Mapping[str, Any] | None) -> str:
    if not isinstance(access, Mapping):
        return ""
    return str(access.get("role") or "").strip().upper()


def _admin(access: Mapping[str, Any] | None) -> bool:
    """True only when the existing gate already marked this session ADMIN."""
    return isinstance(access, Mapping) and access.get("allowed") is True and _role(access) == "ADMIN"


def _canon_area(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    compact = " ".join(raw.replace("-", " ").replace("_", " ").replace("/", " ").split())
    aliases = {
        "aion": "aion",
        "aion ia": "aion",
        "negocios": "negocios",
        "negócios": "negocios",
        "trader": "trader",
        "investimentos": "investimentos",
        "renda fixa": "investimentos",
        "renda fixa investimentos": "investimentos",
    }
    return aliases.get(compact, "")


def central_visibility_model(access: Mapping[str, Any] | None) -> dict[str, Any]:
    """Areas this session may see. Non-admin sessions receive only Trader."""
    admin = _admin(access)
    area_ids = _AREA_ORDER if admin else ("trader",)
    areas = [
        {"id": area_id, "label": _AREAS[area_id]["label"], "private": _AREAS[area_id]["private"]}
        for area_id in area_ids
    ]
    return {
        "role": _role(access),
        "admin": admin,
        "area_ids": area_ids,
        "areas": areas,
        "default_area": "trader",
        "priority_area": "aion" if admin else "trader",
    }


def assert_area_access(access: Mapping[str, Any] | None, area: Any) -> str:
    """Fail closed. A direct private id is denied for every non-admin session."""
    area_id = _canon_area(area)
    visible = central_visibility_model(access)["area_ids"]
    if area_id not in visible:
        raise ValueError("central area access denied")
    return area_id


def resolve_central_area(access: Mapping[str, Any] | None, requested: Any = None) -> dict[str, Any]:
    """Resolve a request without copying private labels into the denial."""
    model = central_visibility_model(access)
    token = str(requested or "").strip()
    if not token:
        return {"area": model["default_area"], "denied": False, "shell": False}
    try:
        area_id = assert_area_access(access, token)
    except ValueError:
        return {"area": "trader", "denied": True, "shell": False}
    return {
        "area": area_id,
        "denied": False,
        "shell": area_id in {"negocios", "investimentos"},
    }


def _svg_aion() -> str:
    return (
        '<svg class="aq-central-art" viewBox="0 0 72 48" aria-hidden="true">'
        '<g fill="none" stroke="#b48cff" stroke-width="1.4">'
        '<circle cx="14" cy="30" r="3" fill="#b48cff"/>'
        '<circle cx="32" cy="14" r="3.5" fill="#d8c6ff"/>'
        '<circle cx="50" cy="24" r="3" fill="#b48cff"/>'
        '<circle cx="62" cy="12" r="2" fill="#f2c14e"/>'
        '<path d="M14 30 L32 14 L50 24 L62 12 M32 14 L50 36 M14 30 L50 24"/>'
        '<circle cx="50" cy="36" r="2.4" fill="#f2c14e" stroke="none"/>'
        "</g></svg>"
    )


def _svg_business() -> str:
    return (
        '<svg class="aq-central-art" viewBox="0 0 72 48" aria-hidden="true">'
        '<g fill="none" stroke="#f2c14e" stroke-width="1.6">'
        '<path d="M8 38 H64"/>'
        '<path d="M12 34 L24 26 L34 30 L48 16 L62 12"/>'
        '<path d="M54 12 H62 V20" stroke="#b48cff"/>'
        "</g></svg>"
    )


def _svg_trader() -> str:
    return (
        '<svg class="aq-central-art" viewBox="0 0 72 48" aria-hidden="true">'
        '<g stroke="#9eb6d4" stroke-width="1.3">'
        '<path d="M16 10 V34 M28 16 V38 M40 8 V30 M52 18 V40" fill="none"/>'
        '<path d="M12 22 H20" stroke="#42d392"/>'
        '<path d="M24 20 H32" stroke="#ff6b7a"/>'
        '<path d="M36 14 H44" stroke="#42d392"/>'
        '<path d="M48 26 H56" stroke="#f2c14e"/>'
        "</g></svg>"
    )


def _svg_investments() -> str:
    return (
        '<svg class="aq-central-art" viewBox="0 0 72 48" aria-hidden="true">'
        '<g fill="none" stroke="#f2c14e" stroke-width="1.5">'
        '<path d="M36 6 L58 16 V28 C58 38 36 44 36 44 C36 44 14 38 14 28 V16 Z"/>'
        '<path d="M28 26 L34 32 L46 20" stroke="#b48cff"/>'
        "</g></svg>"
    )


def _svg_module(module_id: str) -> str:
    paths = {
        "administracao": "M8 24 H32 M20 12 V36 M12 16 H28 V32 H12 Z",
        "memoria": "M10 14 H30 V34 H10 Z M14 18 H26 M14 23 H26 M14 28 H22",
        "desenvolvedor": "M12 16 L8 24 L12 32 M28 16 L32 24 L28 32 M16 34 L24 14",
        "pesquisa": "M16 16 A8 8 0 1 1 15.9 16 M22 28 L30 36",
        "voz": "M20 12 V24 A6 6 0 0 0 26 24 V12 M14 22 A8 8 0 0 0 28 22 M20 30 V36",
        "conteudo": "M12 12 H24 L30 18 V36 H12 Z M24 12 V18 H30",
        "automacao": "M20 12 V18 M20 30 V36 M12 24 H18 M26 24 H32 M14 16 L18 20 M26 28 L30 32 M14 32 L18 28 M26 20 L30 16",
        "seguranca": "M20 10 L30 14 V22 C30 28 20 34 20 34 C20 34 10 28 10 22 V14 Z",
        "observabilidade": "M8 26 C14 16 26 16 32 26 C26 36 14 36 8 26 M20 26 A2 2 0 1 0 19.9 26",
    }
    return (
        '<svg class="aq-central-art" viewBox="0 0 40 40" aria-hidden="true">'
        f'<path d="{paths[module_id]}" fill="none" stroke="#b48cff" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


_ART = {
    "aion": _svg_aion,
    "negocios": _svg_business,
    "trader": _svg_trader,
    "investimentos": _svg_investments,
}


def ecosystem_rail_html(access: Mapping[str, Any] | None, active_area: Any = None) -> str:
    """Vertical ecosystem rail. Hidden areas are omitted from the markup."""
    model = central_visibility_model(access)
    try:
        current = assert_area_access(access, active_area) if str(active_area or "").strip() else model["default_area"]
    except ValueError:
        current = model["default_area"]
    links = []
    for area in model["areas"]:
        area_id = area["id"]
        current_attr = ' aria-current="page"' if area_id == current else ""
        priority = " aq-central-priority" if area_id == model["priority_area"] else ""
        label = escape(area["label"])
        links.append(
            f'<a class="aq-central-link{priority}" href="?central={area_id}"{current_attr}>'
            f"<strong>{label}</strong></a>"
        )
    body = "".join(links)
    return (
        _CENTRAL_CSS
        + '<nav class="aq-central-rail" aria-label="Ecossistema AtlasQuant">'
        + '<details class="aq-central-rail-fold" open>'
        + "<summary>Ecossistema</summary>"
        + '<div class="aq-central-kicker">ATLASQUANT</div>'
        + body
        + "</details></nav>"
    )


def central_card_html(area: Any) -> str:
    """Visual shell for one ecosystem area. Not a product implementation."""
    area_id = _canon_area(area)
    if area_id not in _AREAS:
        raise ValueError("unknown central area")
    spec = _AREAS[area_id]
    badge = state_badge_html("EM CONSTRUÇÃO", "warn")
    return (
        '<article class="aq-central-card" data-area="'
        + escape(area_id)
        + '" data-truth="UNKNOWN">'
        + _ART[area_id]()
        + "<h2>"
        + escape(spec["label"])
        + "</h2><p>"
        + escape(spec["sentence"])
        + "</p><p>"
        + badge
        + "</p></article>"
    )


def aion_home_html(*_ignored: Any, **_claims: Any) -> str:
    """Nine AION modules. Caller status claims are not a source of truth."""
    del _ignored, _claims
    modules = []
    for spec in _AION_MODULES:
        dependency = ""
        if spec["dependency"]:
            dependency = "<p>Depende de " + escape(spec["dependency"]) + ".</p>"
        modules.append(
            '<article class="aq-aion-module" data-module="'
            + escape(spec["id"])
            + '" data-truth="UNKNOWN">'
            + _svg_module(spec["id"])
            + "<h3>"
            + escape(spec["title"])
            + "</h3><p>"
            + escape(spec["sentence"])
            + "</p><p>"
            + state_badge_html("EM CONSTRUÇÃO", "warn")
            + "</p>"
            + dependency
            + "</article>"
        )
    return (
        '<section class="aq-aion-home" data-truth="UNKNOWN">'
        + hero_html("AION", "LOCAL")
        + section_title_html("AION IA")
        + '<div class="aq-aion-grid">'
        + "".join(modules)
        + "</div></section>"
    )


def central_surface_html(access: Mapping[str, Any] | None, requested: Any = None) -> str:
    """Rail plus the allowed stage. A denial does not leak private labels."""
    resolved = resolve_central_area(access, requested)
    rail = ecosystem_rail_html(access, active_area=resolved["area"])
    if resolved["denied"]:
        stage = '<p class="aq-central-denied">Área privada indisponível para esta sessão.</p>'
    elif resolved["area"] == "aion":
        stage = aion_home_html()
    else:
        stage = central_card_html(resolved["area"])
    return (
        '<div class="aq-central-layout">'
        + rail
        + '<div class="aq-central-stage">'
        + stage
        + "</div></div>"
    )


def render_central_hub(access: Mapping[str, Any] | None, requested: Any = None) -> dict[str, Any]:
    """Streamlit edge. Import stays local so pure tests need no server."""
    import streamlit as st

    resolved = resolve_central_area(access, requested)
    st.markdown(central_surface_html(access, requested), unsafe_allow_html=True)
    if resolved["denied"]:
        st.error("Área privada indisponível para esta sessão.")
    return resolved


__all__ = [
    "central_visibility_model",
    "assert_area_access",
    "resolve_central_area",
    "ecosystem_rail_html",
    "central_card_html",
    "aion_home_html",
    "central_surface_html",
    "render_central_hub",
]
