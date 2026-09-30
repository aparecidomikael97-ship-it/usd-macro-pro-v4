"""Central AtlasQuant e Home AION IA.

Pure presentation and access checks. The role already lives on the access
mapping produced by the existing gate. This module does not create accounts
or a second admin source, and it does not execute anything.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

from atlasquant_aion_clock import (
    DEFAULT_TIMEZONE,
    application_timezone,
    greeting_period,
)
from atlasquant_navigation_bridge import (
    request_business_workspace,
    request_return_to_aion,
    request_surface_revalidation,
)
from atlasquant_aion_business_demo import business_demo_html
from atlasquant_ui_v1 import hero_html, section_title_html, state_badge_html

_AREA_ORDER = ("aion", "negocios", "trader", "investimentos")
CENTRAL_ROOT = "central_root"
CENTRAL_CHOICE_KEY = "atlasquant_central_choice"
LOGIN_GREETING_KEY = "aion_login_greeting_shown"
_ROOT_TOKENS = {"central", "central root", "ecosystem root", "central principal"}

_AREAS = {
    "aion": {
        "label": "AION IA",
        "sentence": "Inteligência do ecossistema, ainda em construção.",
        "private": True,
    },
    "negocios": {
        "label": "Negócios",
        "sentence": "Cockpit operacional Business do AION, com pesquisa, economia unitária e aprovação humana.",
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

# Seven home cards open an existing workspace. Pesquisa and Voz stay unlinkable.
AION_MODULE_WORKSPACES = {
    "administracao": "🧠 Central",
    "memoria": "🧠 Central",
    "desenvolvedor": "🛠️ Desenvolvimento",
    "conteudo": "🎬 Studio",
    "automacao": "🧠 Central",
    "seguranca": "🧠 Central",
    "observabilidade": "🧠 Central",
}
AION_MODULE_JUMP_KEY = "aion_admin_workspace_jump"

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
.aq-central-link{display:flex;flex-direction:column;align-items:flex-start;gap:4px;text-decoration:none;color:var(--aq-text);border:1px solid transparent;border-radius:14px;padding:10px 12px;background:rgba(8,16,32,.55)}
.aq-central-link small{color:var(--aq-muted);font-size:.68rem;font-weight:650}
.aq-central-link strong{font-size:.92rem}
.aq-central-priority{border-color:var(--aq-aion,#b48cff);box-shadow:inset 0 0 0 1px rgba(180,140,255,.28)}
.aq-central-link[aria-current="page"]{background:rgba(180,140,255,.14)}
.aq-central-stage{min-width:0}
.aq-central-card,.aq-aion-module{border:1px solid var(--aq-line);border-radius:18px;padding:14px;background:linear-gradient(180deg,rgba(16,24,46,.92),rgba(7,17,31,.9));min-width:0}
.aq-central-card h2,.aq-aion-module h3{margin:.35rem 0 .2rem;color:var(--aq-text);font-size:1rem}
.aq-central-card p,.aq-aion-module p{margin:0;color:var(--aq-muted);font-size:.8rem;line-height:1.35}
.aq-central-art{display:block;width:72px;height:48px}
.aq-central-rail .aq-central-art{width:44px;height:30px}
.aq-aion-module .aq-central-art{width:42px;height:42px}
.aq-aion-home{border:1px solid var(--aq-aion,#b48cff);border-radius:18px;padding:12px 14px;background:linear-gradient(180deg,rgba(180,140,255,.18),rgba(7,17,31,.55));transition:border-color .2s ease}
.aq-aion-priority{margin:0 0 8px;color:var(--aq-aion,#b48cff);font-size:.62rem;font-weight:800;letter-spacing:.14em}
.aq-aion-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-top:12px}
.aq-central-denied{margin:0;color:var(--aq-warn);font-size:.82rem;font-weight:750}
.aq-aion-presence{border:1px solid var(--aq-aion,#b48cff);border-radius:18px;padding:12px 14px;margin:0 0 14px;background:linear-gradient(180deg,rgba(180,140,255,.18),rgba(7,17,31,.55))}
.aq-aion-presence-kicker{margin:0;color:var(--aq-aion,#b48cff);font-size:.62rem;font-weight:800;letter-spacing:.14em}
.aq-aion-presence-state{margin:.25rem 0 .4rem;color:var(--aq-text);font-size:.78rem;font-weight:800;letter-spacing:.08em}
.aq-aion-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#8fd0c4;margin-right:6px}
.aq-aion-presence-line{margin:.15rem 0;color:var(--aq-text);font-size:.92rem;line-height:1.4}
.aq-central-root h2{margin:.2rem 0 .8rem;color:var(--aq-text);font-size:1.35rem}
.aq-central-choices{display:grid;grid-template-columns:1fr;gap:12px}
.aq-central-choice{display:flex;flex-direction:column;align-items:flex-start;gap:6px;text-decoration:none;color:var(--aq-text);border:1px solid var(--aq-line);border-radius:18px;padding:14px;background:linear-gradient(180deg,rgba(16,24,46,.92),rgba(7,17,31,.9))}
.aq-central-choice small{color:var(--aq-muted);font-size:.75rem;line-height:1.35}
.aq-central-back{color:var(--aq-aion,#b48cff);font-weight:800;text-decoration:none}
@media (min-width:900px){.aq-central-choices{grid-template-columns:1fr 1fr}}
.aq-aion-home .aq-hero{margin-bottom:8px}
@media (max-width:760px){
  .aq-central-layout{grid-template-columns:1fr;gap:10px}
  .aq-central-rail-fold{padding:8px}
  .aq-central-rail-fold>summary{display:flex;align-items:center;min-height:36px}
  .aq-central-link{padding:8px 10px}
  .aq-aion-grid{grid-template-columns:1fr}
}
@media (prefers-reduced-motion: reduce){
  .aq-aion-home,.aq-aion-presence,.aq-central-link,.aq-central-art{animation:none;transition:none}
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


def _compact(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    return " ".join(raw.replace("-", " ").replace("_", " ").replace("/", " ").split())


def _explicit_root(value: Any) -> bool:
    return _compact(value) in _ROOT_TOKENS


def _canon_area(value: Any) -> str:
    compact = _compact(value)
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
        "default_area": CENTRAL_ROOT if admin else "trader",
        "entry": CENTRAL_ROOT if admin else "trader",
        "priority_area": "aion" if admin else "trader",
    }


def assert_area_access(access: Mapping[str, Any] | None, area: Any) -> str:
    """Fail closed. A direct private id is denied for every non-admin session."""
    area_id = _canon_area(area)
    visible = central_visibility_model(access)["area_ids"]
    if area_id not in visible:
        raise ValueError("central area access denied")
    return area_id


def request_central_destination(session_state, access: Mapping[str, Any] | None, area: Any):
    """Hand a central area to the existing navigation bridge.

    Trader opens the current Radar page. AION opens the existing AION page.
    Negócios opens the existing AION Business workspace in the same session.
    Investimentos remains a shell. The central root only records the selector.
    """
    if _explicit_root(area):
        if not _admin(access):
            raise ValueError("central area access denied")
        _remember_choice(session_state, CENTRAL_ROOT)
        return None
    area_id = assert_area_access(access, area)
    _remember_choice(session_state, area_id)
    if area_id == "aion":
        return request_return_to_aion(session_state)
    if area_id == "negocios":
        return request_business_workspace(session_state)
    if area_id == "trader":
        mode = str(session_state.get("atlasquant_experience_mode") or "")
        surface = "advanced_radar" if mode.casefold().startswith("avan") else "home_radar"
        return request_surface_revalidation(session_state, surface)
    return None


def resolve_central_area(access: Mapping[str, Any] | None, requested: Any = None) -> dict[str, Any]:
    """Resolve a request without copying private labels into the denial.

    An empty request is the central root for ADMIN and Trader for everyone else.
    """
    model = central_visibility_model(access)
    token = str(requested or "").strip()
    if not token or _explicit_root(token):
        if model["admin"]:
            return {"area": CENTRAL_ROOT, "denied": False, "shell": False, "root": True}
        return {"area": "trader", "denied": False, "shell": False, "root": False}
    try:
        area_id = assert_area_access(access, token)
    except ValueError:
        return {"area": "trader", "denied": True, "shell": False, "root": False}
    return {
        "area": area_id,
        "denied": False,
        "shell": area_id in {"investimentos"},
        "root": False,
    }


def _remember_choice(session_state, area_id: str) -> None:
    try:
        session_state[CENTRAL_CHOICE_KEY] = area_id
    except Exception:
        return


def sync_central_choice(session_state, access: Mapping[str, Any] | None, requested: Any = None) -> dict[str, Any]:
    """Remember a validated area. A stored id is rechecked and is not authority."""
    explicit = str(requested or "").strip()
    if not explicit:
        try:
            explicit = str(session_state.get(CENTRAL_CHOICE_KEY) or "").strip()
        except Exception:
            explicit = ""
        if explicit == CENTRAL_ROOT:
            explicit = "central"
    resolved = resolve_central_area(access, explicit or None)
    if resolved.get("root"):
        _remember_choice(session_state, CENTRAL_ROOT)
    elif resolved.get("denied"):
        _remember_choice(session_state, "trader")
    else:
        _remember_choice(session_state, str(resolved.get("area") or "trader"))
    return resolved


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
    current = ""
    if str(active_area or "").strip() and not _explicit_root(active_area):
        try:
            current = assert_area_access(access, active_area)
        except ValueError:
            current = "" if model["admin"] else "trader"
    elif not model["admin"]:
        current = "trader"
    links = []
    for area in model["areas"]:
        area_id = area["id"]
        current_attr = ' aria-current="page"' if area_id == current else ""
        priority = " aq-central-priority" if area_id == model["priority_area"] else ""
        label = escape(area["label"])
        links.append(
            f'<div class="aq-central-link{priority}" data-central-area="{area_id}"{current_attr}>'
            f"{_ART[area_id]()}"
            f"<strong>{label}</strong></div>"
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


def normalize_home_claim(raw: Any) -> dict[str, str]:
    """CONFIRMED only when truth, source and summary are already complete."""
    unknown = {"truth_state": "UNKNOWN", "summary": "", "source": ""}
    if not isinstance(raw, Mapping):
        return unknown
    truth = str(raw.get("truth_state") or "").strip().upper()
    source = " ".join(str(raw.get("source") or "").split())
    summary = " ".join(str(raw.get("summary") or "").split())
    if truth != "CONFIRMED" or not source or not summary:
        return unknown
    return {"truth_state": "CONFIRMED", "summary": summary[:180], "source": source[:120]}


def aion_home_claims(system_context: Mapping[str, Any] | None) -> dict[str, dict[str, str]]:
    """Read claims already present. Missing or partial records stay UNKNOWN.

    A confirmed source observation may fill Observabilidade, using its own
    source and detail. No other module is inferred from file presence or from
    the wrapper truth_state.
    """
    claims = {spec["id"]: normalize_home_claim(None) for spec in _AION_MODULES}
    if not isinstance(system_context, Mapping):
        return claims
    supplied = system_context.get("home_claims")
    if isinstance(supplied, Mapping):
        for spec in _AION_MODULES:
            claims[spec["id"]] = normalize_home_claim(supplied.get(spec["id"]))
    if claims["observabilidade"]["truth_state"] == "CONFIRMED":
        return claims
    observations = system_context.get("source_observations")
    if not isinstance(observations, (list, tuple)):
        return claims
    for row in observations:
        if not isinstance(row, Mapping):
            continue
        claim = normalize_home_claim({
            "truth_state": row.get("truth_state"),
            "source": row.get("source"),
            "summary": row.get("summary") or row.get("detail"),
        })
        if claim["truth_state"] == "CONFIRMED":
            claims["observabilidade"] = claim
            break
    return claims


def aion_home_html(claims: Mapping[str, Any] | None = None, **_ignored: Any) -> str:
    """Nine read-only modules. Incomplete claims stay UNKNOWN."""
    del _ignored
    supplied = claims if isinstance(claims, Mapping) else {}
    modules = []
    for spec in _AION_MODULES:
        claim = normalize_home_claim(supplied.get(spec["id"]))
        confirmed = claim["truth_state"] == "CONFIRMED"
        dependency = ""
        if spec["dependency"]:
            dependency = "<p>Depende de " + escape(spec["dependency"]) + ".</p>"
        summary = ""
        source = ""
        if confirmed:
            summary = "<p>" + escape(claim["summary"]) + "</p>"
            source = "<p>Fonte: " + escape(claim["source"]) + "</p>"
            badge = state_badge_html("CONFIRMADO", "good")
        else:
            badge = state_badge_html("EM CONSTRUÇÃO", "warn")
        workspace = AION_MODULE_WORKSPACES.get(spec["id"], "")
        action = ""
        if workspace:
            action = '<p class="aq-central-back">Abrir pelo controle de módulo abaixo.</p>'
        modules.append(
            '<article class="aq-aion-module" data-module="'
            + escape(spec["id"])
            + '" data-truth="'
            + claim["truth_state"]
            + '">'
            + _svg_module(spec["id"])
            + "<h3>"
            + escape(spec["title"])
            + "</h3><p>"
            + escape(spec["sentence"])
            + "</p>"
            + summary
            + "<p>"
            + badge
            + "</p>"
            + source
            + dependency
            + action
            + "</article>"
        )
    return (
        '<section class="aq-aion-home" data-truth="UNKNOWN">'
        + '<p class="aq-aion-priority">PRIORIDADE ATUAL</p>'
        + hero_html("AION", "LOCAL")
        + section_title_html("AION IA")
        + '<div class="aq-aion-grid">'
        + "".join(modules)
        + "</div></section>"
    )


def aion_home_viewer_html(
    access: Mapping[str, Any] | None,
    system_context: Mapping[str, Any] | None = None,
) -> str:
    """Admin-only home. Non-admin sessions receive no private module markup."""
    if not _admin(access):
        return ""
    return aion_home_html(aion_home_claims(system_context))


def consume_aion_module_jump(session_state, access: Mapping[str, Any] | None, module_id: Any) -> str:
    """Store one existing workspace jump. Unknown ids and non-admins do nothing."""
    if not _admin(access):
        return ""
    module = str(module_id or "").strip()
    workspace = AION_MODULE_WORKSPACES.get(module, "")
    if not workspace:
        return ""
    try:
        session_state[AION_MODULE_JUMP_KEY] = workspace
    except Exception:
        return ""
    return workspace


def _session_map(access: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(access, Mapping):
        return {}
    session = access.get("session")
    return session if isinstance(session, Mapping) else {}


def _greeting_name(access: Mapping[str, Any]) -> str:
    """Name already on the authenticated access mapping. Owner aliases stay Mikael."""
    session = _session_map(access)
    for raw in (
        access.get("display_name"),
        session.get("display_name"),
        access.get("username"),
        session.get("username"),
    ):
        name = " ".join(str(raw or "").split())
        if not name:
            continue
        if name.casefold() in {"mikael", "aparecidomikael"}:
            return "Mikael"
        return name[:64]
    return "Mikael"


def _login_mark(access: Mapping[str, Any]) -> str:
    session = _session_map(access)
    user = str(session.get("username") or access.get("username") or "").strip()
    issued = session.get("authenticated_at", access.get("authenticated_at", ""))
    return f"{user}|{issued}"


def confirmed_status_line(status: Mapping[str, Any] | None) -> str:
    """A short line only when the caller already proved a confirmed source."""
    if not isinstance(status, Mapping):
        return ""
    if str(status.get("truth_state") or "").strip().upper() != "CONFIRMED":
        return ""
    source = " ".join(str(status.get("source") or "").split())
    summary = " ".join(str(status.get("summary") or "").split())
    if not source or not summary:
        return ""
    return summary[:180]


def login_greeting(
    access: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    confirmed_status: Mapping[str, Any] | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Text for a valid ADMIN session. Missing facts stay out of the sentence."""
    if not _admin(access):
        return {"show": False, "text": "", "period": "", "name": "", "status": ""}
    period = greeting_period(now, timezone_name=timezone_name).casefold()
    name = _greeting_name(access)
    text = (
        f"{name}, {period}. AION ativo. "
        "Bem-vindo ao AtlasQuant. O que você gostaria de saber ou fazer?"
    )
    return {
        "show": True,
        "text": text,
        "period": period,
        "name": name,
        "status": confirmed_status_line(confirmed_status),
    }


def aion_login_presence_html(
    access: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    confirmed_status: Mapping[str, Any] | None = None,
    timezone_name: str | None = None,
) -> str:
    """Active AION presence. The workspace stays closed until an explicit click."""
    greeting = login_greeting(
        access,
        now=now,
        confirmed_status=confirmed_status,
        timezone_name=timezone_name,
    )
    if not greeting["show"]:
        return ""
    status = ""
    if greeting["status"]:
        source = ""
        if isinstance(confirmed_status, Mapping):
            source = escape(str(confirmed_status.get("source") or ""))
        status = (
            f'<p class="aq-aion-presence-line" data-confirmed="{source}">'
            f"{escape(greeting['status'])}</p>"
        )
    return (
        '<section class="aq-aion-presence" data-aion="active">'
        '<p class="aq-aion-presence-kicker">AION</p>'
        '<p class="aq-aion-presence-state"><span class="aq-aion-dot" aria-hidden="true"></span>ATIVO</p>'
        f'<p class="aq-aion-presence-line">{escape(greeting["name"])}, {escape(greeting["period"])}. AION ativo.</p>'
        '<p class="aq-aion-presence-line">Bem-vindo ao AtlasQuant. O que você gostaria de saber ou fazer?</p>'
        + status
        + '<p class="aq-central-back">Abrir AION pelos controles de navegação abaixo.</p>'
        "</section>"
    )


def _voice_ready(provider_configured: bool) -> bool:
    """Readiness only. This does not start a provider or a paid service."""
    if not provider_configured:
        return False
    try:
        from atlasquant_voice_readiness import voice_readiness

        ready = voice_readiness(provider_configured=True)
    except Exception:
        return False
    return bool(ready.get("voice_ready"))


def acknowledge_login_greeting(
    session_state,
    access: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    confirmed_status: Mapping[str, Any] | None = None,
    timezone_name: str | None = None,
    provider_configured: bool = False,
    speak=None,
) -> dict[str, Any]:
    """Announce once per authentication. A later rerun keeps the same flag."""
    greeting = login_greeting(
        access,
        now=now,
        confirmed_status=confirmed_status,
        timezone_name=timezone_name,
    )
    greeting["announced"] = False
    greeting["spoken"] = False
    greeting["voice_failed"] = False
    greeting["voice_ready"] = False
    if not greeting["show"]:
        return greeting
    mark = _login_mark(access)
    try:
        previous = session_state.get(LOGIN_GREETING_KEY)
    except Exception:
        previous = None
    already = isinstance(previous, Mapping) and previous.get("mark") == mark and previous.get("shown") is True
    if already:
        return greeting
    try:
        session_state[LOGIN_GREETING_KEY] = {"mark": mark, "shown": True}
    except Exception:
        pass
    greeting["announced"] = True
    greeting["voice_ready"] = _voice_ready(provider_configured)
    if greeting["voice_ready"] and callable(speak):
        try:
            speak(greeting["text"])
            greeting["spoken"] = True
        except Exception:
            greeting["spoken"] = False
            greeting["voice_failed"] = True
    return greeting


def clear_login_greeting(session_state) -> None:
    """Logout drops the flag so the next ADMIN login can greet again."""
    try:
        session_state.pop(LOGIN_GREETING_KEY, None)
    except Exception:
        return


def central_selector_html(
    access: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    confirmed_status: Mapping[str, Any] | None = None,
    timezone_name: str | None = None,
) -> str:
    """Four-sector door for an admin session. Non-admin sessions get no private cards."""
    model = central_visibility_model(access)
    if not model["admin"]:
        return ""
    choices = []
    for area in model["areas"]:
        area_id = area["id"]
        spec = _AREAS[area_id]
        choices.append(
            f'<article class="aq-central-choice" data-central-area="{area_id}">'
            f"{_ART[area_id]()}"
            f"<strong>{escape(spec['label'])}</strong>"
            f"<small>{escape(spec['sentence'])}</small></article>"
        )
    presence = aion_login_presence_html(
        access,
        now=now,
        confirmed_status=confirmed_status,
        timezone_name=timezone_name,
    )
    return (
        '<section class="aq-central-root" data-root="central_root">'
        + presence
        + '<p class="aq-central-kicker">CENTRAL PRINCIPAL</p>'
        "<h2>Escolha um setor</h2>"
        '<div class="aq-central-choices">'
        + "".join(choices)
        + "</div></section>"
    )


def central_surface_html(
    access: Mapping[str, Any] | None,
    requested: Any = None,
    *,
    now: datetime | None = None,
    confirmed_status: Mapping[str, Any] | None = None,
    timezone_name: str | None = None,
    home_claims: Mapping[str, Any] | None = None,
    defer_aion_home: bool = False,
) -> str:
    """Rail plus the allowed stage. A denial does not leak private labels."""
    resolved = resolve_central_area(access, requested)
    at_root = bool(resolved.get("root"))
    rail = ecosystem_rail_html(access, active_area="" if at_root else resolved["area"])
    if resolved["denied"]:
        stage = '<p class="aq-central-denied">Área privada indisponível para esta sessão.</p>'
    elif at_root:
        stage = central_selector_html(
            access,
            now=now,
            confirmed_status=confirmed_status,
            timezone_name=timezone_name,
        )
    elif resolved["area"] == "aion" and defer_aion_home:
        stage = ""
    elif resolved["area"] == "aion":
        stage = aion_home_html(home_claims)
    elif resolved["area"] == "negocios":
        stage = business_demo_html()
    else:
        stage = central_card_html(resolved["area"])
    back = ""
    if _admin(access) and not at_root:
        back = '<p class="aq-central-back">Voltar à Central Principal pelos controles abaixo.</p>'
    return (
        '<div class="aq-central-layout">'
        + rail
        + '<div class="aq-central-stage">'
        + stage
        + back
        + "</div></div>"
    )


def render_aion_home_viewer(
    access: Mapping[str, Any] | None,
    system_context: Mapping[str, Any] | None = None,
) -> str:
    """Paint the home once. This reads the context it is given and does not fetch."""
    import streamlit as st

    html = aion_home_viewer_html(access, system_context)
    if html:
        st.markdown(html, unsafe_allow_html=True)
        modules = [spec for spec in _AION_MODULES if spec["id"] in AION_MODULE_WORKSPACES]
        st.caption("Módulos AION · navegação interna da mesma sessão")
        columns = st.columns(2)
        for index, spec in enumerate(modules):
            with columns[index % 2]:
                if st.button(
                    str(spec["title"]),
                    key=f"aq_aion_module_stateful_{spec['id']}",
                    width="stretch",
                ):
                    consume_aion_module_jump(st.session_state, access, spec["id"])
                    st.rerun()
    return html


def _render_central_navigation_controls(st, access: Mapping[str, Any] | None, resolved: Mapping[str, Any]) -> None:
    """Authenticated navigation stays inside Streamlit session_state.

    HTML cards/rail are presentation only. The existing access mapping remains
    the authority and request_central_destination performs the validated state
    transition before a rerun.
    """
    if not _admin(access):
        return

    current = CENTRAL_ROOT if resolved.get("root") else str(resolved.get("area") or "")
    model = central_visibility_model(access)
    targets = [("central", "Central Principal")] + [
        (str(area["id"]), str(area["label"])) for area in model["areas"]
    ]
    st.markdown("#### Acessos da Central")
    st.caption(
        "Use estes botões para abrir um setor na mesma sessão autenticada. "
        "Os cartões acima são um mapa visual; a navegação real acontece aqui."
    )
    columns = st.columns(2)
    for index, (area_id, label) in enumerate(targets):
        disabled = (current == CENTRAL_ROOT and area_id == "central") or current == area_id
        action_label = (
            "Central Principal"
            if area_id == "central"
            else "Abrir " + label
        )
        with columns[index % 2]:
            if st.button(
                action_label,
                key=f"aq_central_stateful_{area_id}",
                width="stretch",
                disabled=disabled,
            ):
                request_central_destination(st.session_state, access, area_id)
                st.rerun()


def render_central_hub(
    access: Mapping[str, Any] | None,
    requested: Any = None,
    *,
    now: datetime | None = None,
    confirmed_status: Mapping[str, Any] | None = None,
    timezone_name: str | None = None,
    home_claims: Mapping[str, Any] | None = None,
    defer_aion_home: bool = False,
) -> dict[str, Any]:
    """Streamlit edge. Import stays local so pure tests need no server."""
    import streamlit as st

    resolved = resolve_central_area(access, requested)
    st.markdown(
        central_surface_html(
            access,
            requested,
            now=now,
            confirmed_status=confirmed_status,
            timezone_name=timezone_name,
            home_claims=home_claims,
            defer_aion_home=defer_aion_home,
        ),
        unsafe_allow_html=True,
    )
    if resolved.get("root"):
        try:
            acknowledge_login_greeting(
                st.session_state,
                access,
                now=now,
                confirmed_status=confirmed_status,
                timezone_name=timezone_name,
            )
        except Exception:
            pass
    if resolved["denied"]:
        st.error("Área privada indisponível para esta sessão.")
    _render_central_navigation_controls(st, access, resolved)
    return resolved


__all__ = [
    "central_visibility_model",
    "assert_area_access",
    "resolve_central_area",
    "ecosystem_rail_html",
    "central_card_html",
    "aion_home_html",
    "aion_home_claims",
    "aion_home_viewer_html",
    "normalize_home_claim",
    "consume_aion_module_jump",
    "render_aion_home_viewer",
    "AION_MODULE_WORKSPACES",
    "AION_MODULE_JUMP_KEY",
    "central_selector_html",
    "central_surface_html",
    "aion_login_presence_html",
    "login_greeting",
    "application_timezone",
    "greeting_period",
    "DEFAULT_TIMEZONE",
    "acknowledge_login_greeting",
    "clear_login_greeting",
    "request_central_destination",
    "sync_central_choice",
    "render_central_hub",
    "CENTRAL_ROOT",
    "CENTRAL_CHOICE_KEY",
    "LOGIN_GREETING_KEY",
]
