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
    request_investments_page,
    request_return_to_aion,
    request_surface_revalidation,
)
from atlasquant_ui_v1 import hero_html, section_title_html, state_badge_html
from atlasquant_aion_internal_roles import internal_roles_snapshot
from atlasquant_ecosystem_workspace_ui import (
    WORKSPACE_CSS,
    central_reference_card_html,
    workspace_cockpit_html,
)

_AREA_ORDER = ("trader", "negocios", "investimentos", "aion")
CENTRAL_ROOT = "central_root"
CENTRAL_CHOICE_KEY = "atlasquant_central_choice"
LOGIN_GREETING_KEY = "aion_login_greeting_shown"
HUMAN_OWNER_ID = "HUMAN_OWNER"
_HUMAN_OWNER_ALIASES = frozenset({"mikael", "aparecidomikael"})
_ROOT_TOKENS = {"central", "central root", "ecosystem root", "central principal"}

_AREAS = {
    "aion": {
        "label": "AION",
        "sentence": "Núcleo inteligente transversal do ecossistema, com módulos evoluindo sob controle e auditoria.",
        "private": True,
    },
    "negocios": {
        "label": "Negócios",
        "sentence": "Automação B2B, Revenue Ops, Micro-SaaS, serviços internacionais e produtos digitais próprios.",
        "private": True,
    },
    "trader": {
        "label": "Trader",
        "sentence": "Mercado, macro, micro, geopolítica, fundamentalista, ICT/SMC, calendário e risco.",
        "private": False,
    },
    "investimentos": {
        "label": "Investimentos",
        "sentence": "Central de investimentos para comparação e leitura, sem execução financeira automática.",
        "private": True,
    },
}

# AION Home presents the eight canonical internal roles inside one shared Core.
# These are responsibilities, not eight autonomous AIs. Navigation only reuses
# already existing workspaces and never grants execution authority.
AION_MODULE_WORKSPACES = {
    "orchestrator": "🧠 Central",
    "architect": "🛠️ Desenvolvimento",
    "guardian": "🧠 Central",
    "executor": "🧠 Central",
    "memory": "📚 Biblioteca",
    "finops": "💼 Negócios",
    "observability": "🗂️ Secretaria",
    "customer_success": "💼 Negócios",
}
AION_MODULE_JUMP_KEY = "aion_admin_workspace_jump"

_LEGACY_AION_MODULE_ALIASES = {
    "administracao": "orchestrator",
    "memoria": "memory",
    "desenvolvedor": "architect",
    "automacao": "executor",
    "seguranca": "guardian",
    "observabilidade": "observability",
}


def _canonical_aion_modules() -> tuple[dict[str, Any], ...]:
    snapshot = internal_roles_snapshot()
    modules: list[dict[str, Any]] = []
    for row in snapshot.get("roles", ()):
        if not isinstance(row, Mapping):
            continue
        role_id = str(row.get("role_id") or "").strip()
        label = str(row.get("label") or "").strip()
        purpose = str(row.get("purpose") or "").strip()
        if not role_id or not label or not purpose:
            continue
        modules.append({
            "id": role_id,
            "title": label,
            "sentence": purpose,
            "dependency": "",
            "shared_core": bool(row.get("shared_core", True)),
            "independent_ai": bool(row.get("independent_ai", False)),
            "external_action_authority": bool(row.get("external_action_authority", False)),
        })
    return tuple(modules)


_AION_MODULES = _canonical_aion_modules()

_CENTRAL_CSS = """
<style>
.aq-central-layout{display:grid;grid-template-columns:96px minmax(0,1fr);gap:0;align-items:stretch;width:100%;margin:0 0 18px;min-height:760px;background:#020610;border:1px solid rgba(74,136,220,.14);border-radius:22px;overflow:hidden}
.aq-central-rail{display:flex;flex-direction:column;gap:8px;min-width:0}
.aq-central-rail-fold{display:flex;flex-direction:column;gap:8px;height:100%;padding:10px 8px 16px;border:0;border-right:1px solid rgba(69,138,232,.18);border-radius:0;background:linear-gradient(180deg,#061326 0%,#030b18 100%);box-shadow:inset -12px 0 34px rgba(0,0,0,.25)}.aq-central-rail-logo{display:grid;place-items:center;width:54px;height:54px;margin:2px auto 2px;color:#e4f7ff;font-size:2rem;font-weight:1000;text-shadow:0 0 18px #2d9fff}
.aq-central-rail-fold>summary{display:none;cursor:pointer;color:var(--aq-text);font-size:.78rem;font-weight:800;letter-spacing:.08em;list-style:none}
.aq-central-kicker{color:#72cfff;font-size:.58rem;font-weight:900;letter-spacing:.14em;margin:0 2px 8px;text-align:center}
.aq-central-link{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;min-height:78px;text-decoration:none;color:#aebed5;border:1px solid transparent;border-radius:13px;padding:8px 5px;background:rgba(5,15,31,.5);text-align:center}
.aq-central-link small{color:var(--aq-muted);font-size:.68rem;font-weight:650}
.aq-central-link strong{font-size:.62rem;line-height:1.15}.aq-central-link .aq-central-art{width:34px;height:28px}.aq-central-nav-icon{display:grid;place-items:center;width:30px;height:30px;color:#aebed5;font-size:1.15rem}.aq-central-link[aria-current="page"] .aq-central-nav-icon{color:#55c6ff;text-shadow:0 0 12px rgba(85,198,255,.8)}
.aq-central-priority{border-color:rgba(67,166,255,.35);box-shadow:0 0 22px rgba(34,126,255,.12),inset 0 0 18px rgba(34,126,255,.08)}
.aq-central-link[aria-current="page"]{color:#eef8ff;border-color:#268dff;background:linear-gradient(180deg,rgba(19,91,166,.55),rgba(6,33,72,.76));box-shadow:0 0 24px rgba(32,137,255,.22),inset 3px 0 0 #2aa8ff}
.aq-central-stage{min-width:0;background:radial-gradient(circle at 52% 16%,rgba(15,91,170,.10),transparent 34rem),linear-gradient(180deg,#020914,#020610);}
.aq-central-card,.aq-aion-module{border:1px solid var(--aq-line);border-radius:18px;padding:14px;background:linear-gradient(180deg,rgba(16,24,46,.92),rgba(7,17,31,.9));min-width:0}
.aq-central-card h2,.aq-aion-module h3{margin:.35rem 0 .2rem;color:var(--aq-text);font-size:1rem}
.aq-central-card p,.aq-aion-module p{margin:0;color:var(--aq-muted);font-size:.8rem;line-height:1.35}
.aq-central-art{display:block;width:72px;height:48px}
.aq-central-rail .aq-central-art{width:44px;height:30px}
.aq-aion-module .aq-central-art{width:42px;height:42px}
.aq-aion-home{border:1px solid var(--aq-aion,#b48cff);border-radius:18px;padding:12px 14px;background:linear-gradient(180deg,rgba(180,140,255,.18),rgba(7,17,31,.55));transition:border-color .2s ease}
.aq-aion-priority{margin:0 0 8px;color:var(--aq-aion,#b48cff);font-size:.62rem;font-weight:800;letter-spacing:.14em}
.aq-aion-core-note{margin:0 0 10px;color:var(--aq-text);font-size:.8rem;line-height:1.45;border-left:3px solid var(--aq-aion,#b48cff);padding:8px 10px;background:rgba(180,140,255,.08);border-radius:0 10px 10px 0}
.aq-aion-shared{margin-top:8px!important;color:#d8c6ff!important;font-size:.68rem!important;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
.aq-aion-motto{margin:8px 0 12px;color:var(--aq-warn);font-size:.78rem;font-weight:900;letter-spacing:.05em}
.aq-aion-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-top:12px}
.aq-central-denied{margin:0;color:var(--aq-warn);font-size:.82rem;font-weight:750}
.aq-aion-presence{border:1px solid var(--aq-aion,#b48cff);border-radius:18px;padding:12px 14px;margin:0 0 14px;background:linear-gradient(180deg,rgba(180,140,255,.18),rgba(7,17,31,.55))}
.aq-aion-presence-kicker{margin:0;color:var(--aq-aion,#b48cff);font-size:.62rem;font-weight:800;letter-spacing:.14em}
.aq-aion-presence-state{margin:.25rem 0 .4rem;color:var(--aq-text);font-size:.78rem;font-weight:800;letter-spacing:.08em}
.aq-aion-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#8fd0c4;margin-right:6px}
.aq-aion-presence-line{margin:.15rem 0;color:var(--aq-text);font-size:.92rem;line-height:1.4}
.aq-central-root{position:relative;overflow:hidden;border:0;border-radius:0;padding:0 20px 18px;background:transparent;box-shadow:none;min-height:760px}
.aq-central-root:before{content:"";position:absolute;inset:auto 0 0;height:155px;background:radial-gradient(ellipse at 50% 110%,rgba(41,151,255,.40) 0%,rgba(16,66,130,.22) 30%,transparent 66%);border-top:1px solid rgba(77,157,255,.14);pointer-events:none}
.aq-central-root>*{position:relative;z-index:1}
.aq-central-root h2{margin:.2rem 0 .15rem;color:#f6f8ff;font-size:clamp(1.65rem,2.6vw,2.2rem);letter-spacing:-.03em}
.aq-central-root-copy{margin:0 0 1.1rem;color:#9ba9bf;font-size:.82rem}
.aq-central-choices{display:grid;grid-template-columns:1fr;gap:12px}
.aq-central-choice{position:relative;overflow:hidden;display:flex;flex-direction:column;align-items:flex-start;justify-content:space-between;gap:8px;min-height:168px;text-decoration:none;color:var(--aq-text);border:1px solid var(--aq-line);border-radius:20px;padding:16px;background:linear-gradient(180deg,rgba(18,28,52,.94),rgba(7,17,31,.92));box-shadow:inset 0 1px 0 rgba(255,255,255,.035)}
.aq-central-choice[data-central-area="trader"]{border-color:rgba(84,215,255,.28)}
.aq-central-choice[data-central-area="negocios"]{border-color:rgba(242,193,78,.28)}
.aq-central-choice[data-central-area="investimentos"]{border-color:rgba(66,211,146,.24)}
.aq-central-choice[data-central-area="aion"]{border-color:rgba(180,140,255,.34)}
.aq-central-choice-index{position:absolute;right:14px;top:10px;color:rgba(203,214,255,.28);font-size:1.35rem;font-weight:900;letter-spacing:.06em}
.aq-central-choice strong{font-size:1.05rem;letter-spacing:-.01em}
.aq-central-choice small{color:var(--aq-muted);font-size:.75rem;line-height:1.45;max-width:31rem}
.aq-central-route{display:inline-flex;align-items:center;gap:5px;margin-top:3px;border:1px solid rgba(79,163,255,.34);border-radius:999px;padding:4px 8px;color:#dbeaff;font-size:.62rem;font-weight:850;letter-spacing:.06em;background:rgba(79,163,255,.08)}
.aq-central-route:before{content:"";width:6px;height:6px;border-radius:50%;background:#8fd0c4}
.aq-central-back{color:var(--aq-aion,#b48cff);font-weight:800;text-decoration:none}
.aq-central-root>.aq-aion-presence{display:none}
.aq-central-topbar{display:grid;grid-template-columns:minmax(230px,.8fr) minmax(280px,1.45fr) minmax(220px,.8fr);align-items:center;gap:18px;min-height:72px;margin:0 -20px 18px;padding:0 22px;border-bottom:1px solid rgba(69,139,232,.16);background:linear-gradient(180deg,rgba(3,12,26,.98),rgba(3,10,22,.94));box-shadow:0 12px 28px rgba(0,0,0,.22)}
.aq-central-brand{display:flex;align-items:center;gap:10px;color:#f2f6ff;font-weight:950;letter-spacing:.12em}.aq-central-brand-mark{display:grid;place-items:center;width:42px;height:42px;font-size:1.65rem;font-weight:1000;color:#dff7ff;text-shadow:0 0 18px #36a9ff}.aq-central-brand-copy{display:flex;flex-direction:column}.aq-central-brand-copy strong{font-size:1rem}.aq-central-brand-copy small{color:#7f91aa;font-size:.53rem;letter-spacing:.08em}
.aq-central-search{height:38px;border:1px solid rgba(113,158,218,.23);border-radius:20px;background:rgba(7,18,37,.72);color:#61748e;display:flex;align-items:center;padding:0 16px;font-size:.69rem}.aq-central-search:before{content:"⌕";margin-right:9px;color:#8ab5e6;font-size:1rem}
.aq-central-user{display:flex;align-items:center;justify-content:flex-end;gap:10px;color:#f4f7ff}.aq-central-user-icons{display:flex;gap:8px;color:#9fb5d1}.aq-central-avatar{display:grid;place-items:center;width:38px;height:38px;border:1px solid #3e80ff;border-radius:50%;background:linear-gradient(145deg,#102b58,#151c4f);box-shadow:0 0 18px rgba(61,122,255,.22);font-weight:900}.aq-central-user-copy{display:flex;flex-direction:column;line-height:1.15}.aq-central-user-copy strong{font-size:.72rem}.aq-central-user-copy small{color:#7f91aa;font-size:.57rem}
.aq-central-welcome{text-align:center;margin:4px auto 18px}.aq-central-welcome h2{font-size:clamp(1.75rem,2.4vw,2.35rem);font-weight:680}.aq-central-welcome h2 b{color:#3b94ff}.aq-central-welcome p{margin:.25rem 0 0;color:#909db1;font-size:.82rem}
.aq-central-footer{position:relative;overflow:hidden;display:flex;align-items:flex-end;justify-content:space-between;gap:24px;min-height:118px;margin:14px 0 0;padding:26px 20px 14px;border:1px solid rgba(66,132,214,.16);border-radius:15px;background:radial-gradient(ellipse at 52% 118%,rgba(40,142,255,.48),rgba(11,48,100,.28) 34%,transparent 65%),linear-gradient(180deg,rgba(4,13,28,.72),rgba(2,8,18,.94))}.aq-central-footer:before{content:"";position:absolute;left:10%;right:10%;bottom:-78px;height:150px;border-radius:50% 50% 0 0;border-top:2px solid rgba(73,172,255,.5);box-shadow:0 -10px 44px rgba(40,140,255,.20)}.aq-central-footer>*{position:relative;z-index:1}.aq-central-footer strong{display:block;color:#f4f8ff;font-size:.85rem}.aq-central-footer span{color:#8e9bb0;font-size:.64rem}.aq-central-footer-brand{text-align:right;letter-spacing:.08em}.aq-central-footer-brand strong{font-size:1rem}
@media (min-width:900px){.aq-central-choices{grid-template-columns:repeat(4,minmax(0,1fr))}}
.aq-aion-home .aq-hero{margin-bottom:8px}
@media (max-width:760px){
  .aq-central-layout{grid-template-columns:1fr;gap:0;width:100%;margin:0 0 12px;border-radius:16px}
  .aq-central-root{padding:0 16px 16px;border-radius:0;min-height:0}
  .aq-central-topbar{grid-template-columns:1fr auto;margin:0 -16px 14px;padding:8px 12px;min-height:62px}
  .aq-central-search{display:none}.aq-central-user-copy{display:none}.aq-central-brand-copy small{display:none}
  .aq-central-choice{min-height:150px}
  .aq-central-rail{display:none}
  .aq-central-rail-fold{padding:8px}
  .aq-central-rail-fold>summary{display:flex;align-items:center;min-height:36px}
  .aq-central-link{padding:8px 10px}
  .aq-central-footer{min-height:105px;flex-direction:column;align-items:flex-start}.aq-central-footer-brand{text-align:left}
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
    Investimentos opens the existing 💰 Investir page. The central root only
    records the selector.
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
    if area_id == "investimentos":
        return request_investments_page(session_state)
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
        "shell": False,
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
        '<svg class="aq-central-art" viewBox="0 0 320 180" aria-hidden="true">'
        '<defs><radialGradient id="aionOrb" cx="50%" cy="45%" r="58%">'
        '<stop offset="0" stop-color="#8c44ff" stop-opacity=".88"/><stop offset=".58" stop-color="#35126f" stop-opacity=".82"/>'
        '<stop offset="1" stop-color="#06091a" stop-opacity="0"/></radialGradient></defs>'
        '<rect width="320" height="180" fill="#06081b"/><circle cx="244" cy="84" r="70" fill="url(#aionOrb)"/>'
        '<g fill="none" stroke="#bb69ff" opacity=".62"><circle cx="244" cy="84" r="46"/><ellipse cx="244" cy="84" rx="46" ry="18"/>'
        '<path d="M198 84h92M244 38c-13 13-20 29-20 46s7 33 20 46M244 38c13 13 20 29 20 46s-7 33-20 46"/></g>'
        '<path d="M68 151 C55 122 58 94 75 72 C87 56 103 45 123 42 C144 38 159 45 170 60 C181 75 180 91 170 104'
        ' C163 112 159 124 159 151 Z" fill="#120d32" stroke="#ba68ff" stroke-width="2"/>'
        '<path d="M100 61 C116 50 139 53 151 67 L145 84 L132 90 L129 111 L115 121 L96 111 L88 88 Z"'
        ' fill="#4a2587" stroke="#de9cff" stroke-width="1.5"/>'
        '<circle cx="124" cy="78" r="5" fill="#e5b5ff"/><path d="M126 78 L165 64 M126 78 L171 95 M126 78 L152 126"'
        ' stroke="#c978ff" stroke-width="1.2" opacity=".8"/><g fill="#d88cff"><circle cx="165" cy="64" r="3"/><circle cx="171" cy="95" r="3"/><circle cx="152" cy="126" r="3"/></g>'
        '<path d="M18 148 H302" stroke="#8f4cff" stroke-opacity=".45"/><path d="M15 162 C90 139 229 141 305 160" stroke="#6224bf" fill="none" opacity=".7"/>'
        '</svg>'
    )


def _svg_business() -> str:
    return (
        '<svg class="aq-central-art" viewBox="0 0 320 180" aria-hidden="true">'
        '<defs><linearGradient id="bizBg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#052c24"/><stop offset="1" stop-color="#06121b"/></linearGradient></defs>'
        '<rect width="320" height="180" fill="url(#bizBg)"/><g opacity=".2" stroke="#38e5ad"><path d="M0 145H320M0 120H320M0 95H320"/>'
        '<path d="M55 0V180M105 0V180M155 0V180M205 0V180M255 0V180"/></g>'
        '<rect x="190" y="42" width="98" height="70" rx="5" fill="#09291f" stroke="#28dca2"/><path d="M202 92 L221 76 L238 83 L264 58 L279 63" fill="none" stroke="#67ffc9" stroke-width="3"/>'
        '<g fill="#59462d" stroke="#8f7549"><rect x="104" y="94" width="53" height="42"/><rect x="151" y="80" width="56" height="56"/><rect x="72" y="113" width="42" height="30"/></g>'
        '<g stroke="#d9b46f" opacity=".75"><path d="M104 108h53M151 96h56M72 125h42"/><path d="M130 94v42M179 80v56M93 113v30"/></g>'
        '<path d="M27 82 h20 l9 45 h74 l11-34 H52" fill="none" stroke="#45f2ba" stroke-width="4" stroke-linejoin="round"/>'
        '<circle cx="69" cy="139" r="7" fill="#0b2e25" stroke="#45f2ba" stroke-width="3"/><circle cx="119" cy="139" r="7" fill="#0b2e25" stroke="#45f2ba" stroke-width="3"/>'
        '<path d="M16 153 H304" stroke="#35d9a5" stroke-opacity=".45"/></svg>'
    )


def _svg_trader() -> str:
    return (
        '<svg class="aq-central-art" viewBox="0 0 320 180" aria-hidden="true">'
        '<defs><radialGradient id="earth" cx="45%" cy="35%" r="65%"><stop offset="0" stop-color="#2c9cff"/><stop offset=".55" stop-color="#103c87"/><stop offset="1" stop-color="#04132f"/></radialGradient></defs>'
        '<rect width="320" height="180" fill="#04101f"/><circle cx="222" cy="88" r="74" fill="url(#earth)" stroke="#43b7ff" stroke-opacity=".75"/>'
        '<g fill="none" stroke="#64c6ff" stroke-opacity=".38"><ellipse cx="222" cy="88" rx="74" ry="26"/><ellipse cx="222" cy="88" rx="30" ry="74"/>'
        '<path d="M148 88h148M161 49c35 18 88 18 122 0M160 127c38-18 89-18 125 0"/></g>'
        '<path d="M152 74l18-8 13 12 20-9 14 7 20-16 18 8 17-12" fill="none" stroke="#7ee6ff" stroke-width="2" opacity=".8"/>'
        '<g stroke-width="2"><path d="M24 38v81" stroke="#6bbcff"/><path d="M18 55h12" stroke="#59e6b5"/><path d="M45 44v96" stroke="#7bbcff"/>'
        '<path d="M39 78h12" stroke="#ff627b"/><path d="M67 26v100" stroke="#6bbcff"/><path d="M61 48h12" stroke="#59e6b5"/>'
        '<path d="M90 50v91" stroke="#6bbcff"/><path d="M84 92h12" stroke="#f3c45e"/><path d="M112 34v82" stroke="#6bbcff"/><path d="M106 67h12" stroke="#59e6b5"/></g>'
        '<polyline points="15,132 45,116 73,121 103,92 129,99 157,72 183,78 207,52" fill="none" stroke="#33b8ff" stroke-width="3"/>'
        '<path d="M12 153 H307" stroke="#258ee5" stroke-opacity=".55"/></svg>'
    )


def _svg_investments() -> str:
    return (
        '<svg class="aq-central-art" viewBox="0 0 320 180" aria-hidden="true">'
        '<defs><radialGradient id="goldGlow"><stop stop-color="#e7a82f" stop-opacity=".38"/><stop offset="1" stop-color="#080d17" stop-opacity="0"/></radialGradient></defs>'
        '<rect width="320" height="180" fill="#0d0c0a"/><circle cx="214" cy="73" r="100" fill="url(#goldGlow)"/>'
        '<g fill="#b77616" stroke="#ffd36e" stroke-width="1.4"><ellipse cx="76" cy="131" rx="35" ry="9"/><path d="M41 110v21c0 5 16 9 35 9s35-4 35-9v-21"/>'
        '<ellipse cx="76" cy="110" rx="35" ry="9"/><path d="M46 91v19c0 5 14 8 30 8s30-3 30-8V91"/><ellipse cx="76" cy="91" rx="30" ry="8"/>'
        '<ellipse cx="159" cy="132" rx="29" ry="8"/><path d="M130 112v20c0 4 13 8 29 8s29-4 29-8v-20"/><ellipse cx="159" cy="112" rx="29" ry="8"/>'
        '<ellipse cx="231" cy="134" rx="24" ry="7"/><path d="M207 120v14c0 4 11 7 24 7s24-3 24-7v-14"/><ellipse cx="231" cy="120" rx="24" ry="7"/></g>'
        '<g fill="#986711" opacity=".72"><rect x="180" y="86" width="12" height="35"/><rect x="202" y="72" width="12" height="49"/><rect x="224" y="56" width="12" height="65"/><rect x="246" y="41" width="12" height="80"/></g>'
        '<path d="M132 94 L164 78 L188 82 L215 58 L244 49 L268 25" fill="none" stroke="#ffd86e" stroke-width="4"/><path d="M255 26h15v15" fill="none" stroke="#ffe49b" stroke-width="4"/>'
        '<path d="M25 153 H297" stroke="#c98e28" stroke-opacity=".55"/></svg>'
    )


def _svg_module(module_id: str) -> str:
    paths = {
        "orchestrator": "M20 8 V14 M20 26 V32 M8 20 H14 M26 20 H32 M11 11 L15 15 M25 25 L29 29 M11 29 L15 25 M25 15 L29 11",
        "architect": "M8 30 L20 10 L32 30 M13 24 H27 M16 30 V23 M24 30 V23",
        "guardian": "M20 10 L30 14 V22 C30 28 20 34 20 34 C20 34 10 28 10 22 V14 Z M15 22 L19 26 L26 18",
        "executor": "M10 12 H30 V32 H10 Z M15 21 L19 25 L26 17",
        "memory": "M10 14 H30 V34 H10 Z M14 18 H26 M14 23 H26 M14 28 H22",
        "finops": "M10 30 V20 H16 V30 M18 30 V12 H24 V30 M26 30 V17 H32 V30 M8 32 H34",
        "observability": "M8 26 C14 16 26 16 32 26 C26 36 14 36 8 26 M20 26 A2 2 0 1 0 19.9 26",
        "customer_success": "M12 14 A5 5 0 1 0 12.1 14 M28 14 A5 5 0 1 0 28.1 14 M7 32 C8 24 16 24 17 32 M23 32 C24 24 32 24 33 32 M18 20 L22 24",
    }
    path = paths.get(module_id, paths["orchestrator"])
    return (
        '<svg class="aq-central-art" viewBox="0 0 40 40" aria-hidden="true">'
        f'<path d="{path}" fill="none" stroke="#b48cff" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )

_ART = {
    "aion": _svg_aion,
    "negocios": _svg_business,
    "trader": _svg_trader,
    "investimentos": _svg_investments,
}


def ecosystem_rail_html(access: Mapping[str, Any] | None, active_area: Any = None) -> str:
    """Vertical ecosystem rail. Root follows the approved hub reference."""
    model = central_visibility_model(access)
    current = ""
    if str(active_area or "").strip() and not _explicit_root(active_area):
        try:
            current = assert_area_access(access, active_area)
        except ValueError:
            current = "" if model["admin"] else "trader"
    elif not model["admin"]:
        current = "trader"

    links: list[str] = []
    if model["admin"] and not current:
        root_items = (
            ("⌂", "Início", True),
            ("♙", "Perfil", False),
            ("♢", "Segurança", False),
            ("⚙", "Configurações", False),
            ("?", "Ajuda", False),
        )
        for icon, label, active in root_items:
            current_attr = ' aria-current="page"' if active else ""
            links.append(
                f'<div class="aq-central-link" data-central-nav="{escape(label.casefold())}"{current_attr}>'
                f'<span class="aq-central-nav-icon">{escape(icon)}</span>'
                f'<strong>{escape(label)}</strong></div>'
            )
    else:
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
        + WORKSPACE_CSS
        + '<nav class="aq-central-rail" aria-label="Ecossistema AtlasQuant">'
        + '<details class="aq-central-rail-fold" open>'
        + "<summary>Ecossistema</summary>"
        + '<div class="aq-central-rail-logo" aria-hidden="true">A</div>'
        + '<div class="aq-central-kicker">ATLASQUANT</div>'
        + body
        + "</details></nav>"
    )


def central_card_html(area: Any) -> str:
    """Visual route state for one connected ecosystem area.

    CONNECTED describes only the validated navigation path. It is not a claim
    that every feature inside the destination is complete or production-ready.
    """
    area_id = _canon_area(area)
    if area_id not in _AREAS:
        raise ValueError("unknown central area")
    spec = _AREAS[area_id]
    badge = state_badge_html("NAVEGAÇÃO CONECTADA", "info")
    return (
        '<article class="aq-central-card" data-area="'
        + escape(area_id)
        + '" data-truth="UNKNOWN" data-route-state="CONNECTED">'
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
            direct = supplied.get(spec["id"])
            if direct is None:
                for legacy_id, canonical_id in _LEGACY_AION_MODULE_ALIASES.items():
                    if canonical_id == spec["id"] and legacy_id in supplied:
                        direct = supplied.get(legacy_id)
                        break
            claims[spec["id"]] = normalize_home_claim(direct)
    if claims["observability"]["truth_state"] == "CONFIRMED":
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
            claims["observability"] = claim
            break
    return claims


def aion_home_html(claims: Mapping[str, Any] | None = None, **_ignored: Any) -> str:
    """Eight canonical internal roles. One shared AION Core; incomplete claims stay UNKNOWN."""
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
            + '<p class="aq-aion-shared">Núcleo interno · AION Core compartilhado</p>'
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
        + section_title_html("AION · 8 PAPÉIS INTERNOS")
        + '<p class="aq-aion-core-note"><strong>8 núcleos especializados, 1 AION Core.</strong> Cada cartão representa uma responsabilidade interna coordenada pelo mesmo núcleo. Não são oito IAs independentes e nenhum núcleo recebe autoridade autônoma para merge, deploy, publicação, cobrança ou trade real.</p>'
        + '<p class="aq-aion-motto">Poderoso por dentro. Simples por fora.</p>'
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
    module = _LEGACY_AION_MODULE_ALIASES.get(module, module)
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


def _owner_alias_token(value: Any) -> str:
    """Normalize only for owner-alias comparison; never for authentication."""
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def owner_session_context(access: Mapping[str, Any] | None) -> dict[str, Any]:
    """Derive UX owner context from an already-authenticated ADMIN session.

    This is presentation/session binding only. It never grants signing,
    deployment, Worker, financial, trading or other privileged authority.
    """
    denied = {
        "is_human_owner": False,
        "owner_id": "",
        "name": "",
        "session_bound": False,
    }
    if not _admin(access):
        return denied
    if str(access.get("mode") or "").strip().upper() != "AUTHENTICATED":
        return denied
    session = _session_map(access)
    if str(session.get("role") or "").strip().upper() != "ADMIN":
        return denied
    if not session.get("authenticated_at"):
        return denied
    username = _owner_alias_token(session.get("username"))
    if username not in _HUMAN_OWNER_ALIASES:
        return denied
    return {
        "is_human_owner": True,
        "owner_id": HUMAN_OWNER_ID,
        "name": "Mikael",
        "session_bound": True,
    }


def _greeting_name(access: Mapping[str, Any]) -> str:
    """Use Mikael only for a proven owner session; other admins stay neutral."""
    owner = owner_session_context(access)
    if owner["is_human_owner"]:
        return str(owner["name"])
    session = _session_map(access)
    for raw in (
        access.get("display_name"),
        session.get("display_name"),
        access.get("username"),
        session.get("username"),
    ):
        name = " ".join(str(raw or "").split())
        if name:
            return name[:64]
    return "Administrador"


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
        return {
            "show": False,
            "text": "",
            "period": "",
            "name": "",
            "status": "",
            "owner_id": "",
            "is_human_owner": False,
            "session_bound": False,
        }
    period = greeting_period(now, timezone_name=timezone_name).casefold()
    owner = owner_session_context(access)
    name = _greeting_name(access)
    owner_sentence = (
        "Contexto HUMAN_OWNER reconhecido nesta sessão. "
        if owner["is_human_owner"]
        else ""
    )
    text = (
        f"{name}, {period}. AION ativo. "
        + owner_sentence
        + "Bem-vindo ao AtlasQuant. O que você gostaria de saber ou fazer?"
    )
    return {
        "show": True,
        "text": text,
        "period": period,
        "name": name,
        "status": confirmed_status_line(confirmed_status),
        "owner_id": owner["owner_id"],
        "is_human_owner": owner["is_human_owner"],
        "session_bound": owner["session_bound"],
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
    owner_line = ""
    if greeting.get("is_human_owner") is True:
        owner_line = (
            '<p class="aq-aion-presence-line" data-owner-context="HUMAN_OWNER">'
            "HUMAN_OWNER · sessão autenticada</p>"
        )
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
        + owner_line
        + '<p class="aq-aion-presence-line">Bem-vindo ao AtlasQuant. O que você gostaria de saber ou fazer?</p>'
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
    """Four approved visual cards, each is the access itself."""
    if not central_visibility_model(access)["admin"]:
        return ""
    from atlasquant_reference_ui import CSS, reference_html
    return "<style>" + CSS.read_text(encoding="utf-8") + "</style>" + reference_html("central", name="")


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
    """Only the selected environment. No cross-sector rail or duplicate access."""
    resolved = resolve_central_area(access, requested)
    if resolved["denied"]:
        return '<p class="aq-central-denied">Área privada indisponível para esta sessão.</p>'
    if resolved["root"]:
        return central_selector_html(access, now=now, confirmed_status=confirmed_status, timezone_name=timezone_name)
    if resolved["area"] == "trader":
        return ""
    from atlasquant_reference_ui import CSS, reference_html
    return "<style>" + CSS.read_text(encoding="utf-8") + "</style>" + reference_html(resolved["area"])


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
        st.caption("8 núcleos internos do AION · navegação na mesma sessão, sem autoridade autônoma")
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


def _render_central_navigation_controls(st, access, resolved):
    """Compatibility edge: card events are mounted directly, with no duplicate strip."""
    return None


def render_central_hub(
    access: Mapping[str, Any] | None,
    requested: Any = None,
    *,
    now: datetime | None = None,
    confirmed_status: Mapping[str, Any] | None = None,
    timezone_name: str | None = None,
    home_claims: Mapping[str, Any] | None = None,
    defer_aion_home: bool = False,
    aion_chat_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Mount same-session clickable reference UI after the unchanged area gate."""
    import streamlit as st
    resolved = resolve_central_area(access, requested)
    if resolved["denied"]:
        st.error("Área privada indisponível para esta sessão.")
        return resolved
    if resolved.get("root"):
        try:
            acknowledge_login_greeting(st.session_state, access, now=now,
                confirmed_status=confirmed_status, timezone_name=timezone_name)
        except Exception:
            pass
    area = "central" if resolved.get("root") else resolved["area"]
    if area != "trader":
        from atlasquant_reference_ui import render_reference_workspace
        if area == "aion" and aion_chat_binding is not None:
            render_reference_workspace(
                st,
                access,
                area,
                aion_chat_binding=dict(aion_chat_binding),
            )
        else:
            render_reference_workspace(st, access, area)
        resolved["shell"] = True
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
    "owner_session_context",
    "HUMAN_OWNER_ID",
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
