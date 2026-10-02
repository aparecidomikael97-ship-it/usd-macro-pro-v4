"""Canonical AION ecosystem registry.

Single offline source for workspaces, personas, specialists and capability
membership. This module does not call the network, execute tools, write files,
read secrets, publish, deploy, merge, trade or activate a connector.

Existing modules project their public maps from this registry. Projecting a
persona or workspace never grants an action the Guardian already denies.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_ECOSYSTEM_V1"

FORBIDDEN_ACTIONS = frozenset({
    "real_trade",
    "deploy_production",
    "merge_main",
    "read_secret",
    "write_secret",
})

OFFICIAL_AREA_IDS = (
    "central",
    "library",
    "atlasquant",
    "administration",
    "development",
    "studio",
    "business",
    "laboratory",
    "investments",
)

# Historical portable order, then the areas that were missing from the shell.
PORTABLE_WORKSPACE_ORDER = (
    "central",
    "library",
    "atlasquant",
    "studio",
    "business",
    "development",
    "administration",
    "laboratory",
    "investments",
)

# Historical console persona order, then Investments and Central.
PUBLIC_PERSONA_ORDER = (
    "trader",
    "library",
    "admin",
    "developer",
    "video",
    "business",
    "laboratory",
    "investments",
    "central",
)

REQUIRED_AREA_CAPABILITIES = {
    "central": ("central.conversation",),
    "library": ("research.synthesize",),
    "atlasquant": ("market.explain", "macro.explain", "ict.explain"),
    "administration": ("admin.status",),
    "development": ("development.inspect", "development.sandbox"),
    "studio": ("studio.prepare",),
    "business": ("business.analyze",),
    "laboratory": ("laboratory.inspect",),
    "investments": ("invest.compare",),
}

_READ_ONLY = ("read", "summarize", "search", "draft")

_SPECIALIST_ROWS: tuple[tuple[str, str], ...] = (
    ("core", "atlasquant_aion_gateway.local_answer"),
    ("dev", "atlasquant_aion_developer_engine"),
    ("research", "atlasquant_aion_cognitive_orchestrator"),
    ("market", "atlasquant_radar_board"),
    ("macro", "atlasquant_macro_briefing"),
    ("ict", "atlasquant_lab_matrix"),
    ("risk", "atlasquant_aion_fortress"),
    ("lab", "atlasquant_research_evidence_capture"),
    ("invest", "atlasquant_investment_ecosystem"),
    ("business", "atlasquant_aion_business"),
    ("studio", "atlasquant_content_pipeline"),
    ("admin", "atlasquant_aion_admin"),
)


def _seq(values: Sequence[Any] | None) -> tuple[str, ...]:
    return tuple(str(item) for item in (values or ()))


def _area(
    *,
    workspace_id: str,
    persona_id: str,
    label: str,
    title: str,
    kind: str,
    domain: str,
    purpose: str,
    state: str,
    admin_only: bool,
    specialist_ids: Sequence[str],
    capability_ids: Sequence[str],
    persona_capability_keys: Sequence[str],
    allowed_actions: Sequence[str],
    console_workspace: str,
) -> dict[str, Any]:
    actions = _seq(allowed_actions)
    granted = set(actions) & FORBIDDEN_ACTIONS
    if granted:
        raise RuntimeError(f"canonical area {workspace_id} grants {sorted(granted)}")
    return {
        "area_id": workspace_id,
        "workspace_id": workspace_id,
        "persona_id": persona_id,
        "label": label,
        "title": title,
        "kind": kind,
        "domain": domain,
        "purpose": purpose,
        "state": state,
        "entry_key": workspace_id,
        "admin_only": bool(admin_only),
        "isolated_context": True,
        "specialist_ids": _seq(specialist_ids),
        "capability_ids": _seq(capability_ids),
        "persona_capability_keys": _seq(persona_capability_keys),
        "allowed_actions": actions,
        "console_workspace": console_workspace,
        "external_action_authority": False,
        "real_trading_enabled": False,
    }


_AREAS: tuple[dict[str, Any], ...] = (
    _area(
        workspace_id="central",
        persona_id="central",
        label="AION Central",
        title="AION Central",
        kind="CORE",
        domain="central",
        purpose="Conversa e roteamento local entre áreas. Não executa ações externas nem ordens.",
        state="ACTIVE_LOCAL",
        admin_only=True,
        specialist_ids=("core", "research", "risk"),
        capability_ids=("central.conversation", "research.synthesize", "risk.assess"),
        persona_capability_keys=("conversation", "research", "risk"),
        allowed_actions=_READ_ONLY,
        console_workspace="🧠 Central",
    ),
    _area(
        workspace_id="library",
        persona_id="library",
        label="Biblioteca",
        title="AION Biblioteca",
        kind="KNOWLEDGE_LIBRARY",
        domain="library",
        purpose="Inspecionar, classificar e revisar documentos locais com proveniência; nunca promove memória nem executa OCR automaticamente.",
        state="READY",
        admin_only=True,
        specialist_ids=("research", "risk"),
        capability_ids=("research.synthesize", "risk.assess"),
        persona_capability_keys=(
            "documents", "metadata", "provenance", "quality",
            "classification", "conflicts", "review",
            "temporary_index", "ocr_plan",
        ),
        allowed_actions=_READ_ONLY,
        console_workspace="📚 Biblioteca",
    ),
    _area(
        workspace_id="atlasquant",
        persona_id="trader",
        label="AtlasQuant",
        title="AION Trader",
        kind="TRADING_PLATFORM",
        domain="trading",
        purpose="Ler Radar, macro e pares com a proveniência de cada dado. Nunca envia ordens.",
        state="ACTIVE_LOCAL",
        admin_only=False,
        specialist_ids=("market", "macro", "ict", "risk"),
        capability_ids=("market.explain", "macro.explain", "ict.explain", "risk.assess"),
        persona_capability_keys=("radar", "macro", "pairs", "calendar", "pre_news", "technical_context", "risk"),
        allowed_actions=_READ_ONLY,
        console_workspace="📈 Trading",
    ),
    _area(
        workspace_id="administration",
        persona_id="admin",
        label="Administração / Secretaria",
        title="AION Administrador",
        kind="ADMIN",
        domain="secretary",
        purpose="Resumo do dia, pendências, aprovações e estado do sistema.",
        state="READY",
        admin_only=True,
        specialist_ids=("admin", "risk"),
        capability_ids=("admin.status", "risk.assess"),
        persona_capability_keys=("system_status", "incidents", "pending", "checks", "degraded_sources", "tasks", "checkpoint"),
        allowed_actions=("read", "summarize", "search", "draft", "save_checkpoint", "restore_checkpoint"),
        console_workspace="🗂️ Secretaria",
    ),
    _area(
        workspace_id="development",
        persona_id="developer",
        label="Desenvolvimento",
        title="AION Desenvolvedor",
        kind="DEVELOPMENT",
        domain="development",
        purpose="Planejar missões de código em branch, com testes e revisão humana.",
        state="READY",
        admin_only=True,
        specialist_ids=("dev", "research", "risk"),
        capability_ids=("development.inspect", "development.sandbox", "research.synthesize", "risk.assess"),
        persona_capability_keys=("code", "logs", "tests", "errors", "patch_plan", "rollback"),
        allowed_actions=("read", "summarize", "search", "draft", "save_checkpoint"),
        console_workspace="🛠️ Desenvolvimento",
    ),
    _area(
        workspace_id="studio",
        persona_id="video",
        label="Studio",
        title="AION Vídeo",
        kind="CREATIVE",
        domain="studio",
        purpose="Roteiros e rascunhos de vídeo. Publicação exige aprovação e feature flag.",
        state="READY",
        admin_only=True,
        specialist_ids=("studio", "research", "risk"),
        capability_ids=("studio.prepare", "research.synthesize", "risk.assess"),
        persona_capability_keys=("script", "storyboard", "scenes", "narration", "captions", "thumbnail", "formats", "approval_queue"),
        allowed_actions=("read", "summarize", "search", "draft", "publish_social"),
        console_workspace="🎬 Studio",
    ),
    _area(
        workspace_id="business",
        persona_id="business",
        label="Negócios",
        title="AION Negócios",
        kind="BUSINESS",
        domain="business",
        purpose="Produtos, margens e marketplaces em modo rascunho.",
        state="READY",
        admin_only=True,
        specialist_ids=("business", "research", "risk"),
        capability_ids=("business.analyze", "research.synthesize", "risk.assess"),
        persona_capability_keys=("catalog", "suppliers", "economics", "fees", "cac", "ltv", "funnel", "tracking", "reports"),
        allowed_actions=("read", "summarize", "search", "draft", "publish_marketplace"),
        console_workspace="💼 Negócios",
    ),
    _area(
        workspace_id="laboratory",
        persona_id="laboratory",
        label="Laboratório",
        title="AION Laboratório",
        kind="LABORATORY",
        domain="laboratory",
        purpose="Experimentos e backtests somente com dados reais registrados.",
        state="READY",
        admin_only=True,
        specialist_ids=("lab", "ict", "research", "risk"),
        capability_ids=("laboratory.inspect", "ict.explain", "research.synthesize", "risk.assess"),
        persona_capability_keys=("matrix", "evidence", "history", "comparisons", "setups", "assets", "timeframes", "styles"),
        allowed_actions=("read", "summarize", "search", "draft", "write_runtime"),
        console_workspace="🧪 Laboratório",
    ),
    _area(
        workspace_id="investments",
        persona_id="investments",
        label="Investimentos",
        title="AION Investimentos",
        kind="INVESTMENTS",
        domain="investments",
        purpose="Comparar produtos e cenários com evidência; nunca movimentar dinheiro.",
        state="READY",
        admin_only=True,
        specialist_ids=("invest", "research", "risk"),
        capability_ids=("invest.compare", "research.synthesize", "risk.assess"),
        persona_capability_keys=("products", "rates", "liquidity", "risk", "income", "comparison", "sources"),
        allowed_actions=_READ_ONLY,
        console_workspace="Investimentos",
    ),
)

_AREA_BY_ID = {item["area_id"]: item for item in _AREAS}
_AREA_BY_WORKSPACE = {item["workspace_id"]: item for item in _AREAS}
_AREA_BY_PERSONA = {item["persona_id"]: item for item in _AREAS}
_SPECIALIST_BY_ID = {specialist_id: module for specialist_id, module in _SPECIALIST_ROWS}


def _copy_area(item: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in item.items():
        if isinstance(value, tuple):
            out[key] = tuple(value)
        elif isinstance(value, list):
            out[key] = list(value)
        else:
            out[key] = value
    return out


def _as_areas(registry: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if registry is None:
        return [_copy_area(item) for item in _AREAS]
    raw = registry.get("areas") if isinstance(registry, Mapping) else None
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [_copy_area(item) for item in raw if isinstance(item, Mapping)]


def _as_specialists(registry: Mapping[str, Any] | None) -> list[dict[str, str]]:
    if registry is None:
        return [{"specialist_id": specialist_id, "module": module} for specialist_id, module in _SPECIALIST_ROWS]
    raw = registry.get("specialists") if isinstance(registry, Mapping) else None
    rows: list[dict[str, str]] = []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return rows
    for item in raw:
        if isinstance(item, Mapping):
            rows.append({
                "specialist_id": str(item.get("specialist_id") or ""),
                "module": str(item.get("module") or ""),
            })
    return rows


def _capability_pairs(capabilities: Sequence[Any] | None) -> list[tuple[str, str]]:
    if capabilities is None:
        from atlasquant_aion_capabilities import DEFAULT_CAPABILITIES
        capabilities = DEFAULT_CAPABILITIES
    pairs: list[tuple[str, str]] = []
    for item in capabilities:
        if isinstance(item, Mapping):
            pairs.append((str(item.get("capability_id") or ""), str(item.get("specialist") or "")))
        else:
            pairs.append((str(getattr(item, "capability_id", "") or ""), str(getattr(item, "specialist", "") or "")))
    return pairs


def ecosystem_registry() -> dict[str, Any]:
    """Return a detached copy of the canonical registry."""
    return {
        "schema": SCHEMA,
        "areas": [_copy_area(item) for item in _AREAS],
        "specialists": [{"specialist_id": specialist_id, "module": module} for specialist_id, module in _SPECIALIST_ROWS],
        "external_action_authority": False,
        "real_trading_enabled": False,
    }


def ecosystem_area(area_id: object) -> dict[str, Any] | None:
    item = _AREA_BY_ID.get(str(area_id or "").strip())
    return _copy_area(item) if item else None


def ecosystem_workspace(workspace_id: object) -> dict[str, Any] | None:
    item = _AREA_BY_WORKSPACE.get(str(workspace_id or "").strip())
    if item is None:
        return None
    return {
        "workspace_id": item["workspace_id"],
        "label": item["label"],
        "kind": item["kind"],
        "state": item["state"],
        "isolated_context": item["isolated_context"],
        "admin_only": item["admin_only"],
        "entry_key": item["entry_key"],
        "external_action_authority": False,
        "real_trading_enabled": False,
    }


def ecosystem_persona(persona_id: object) -> dict[str, Any] | None:
    item = _AREA_BY_PERSONA.get(str(persona_id or "").strip())
    if item is None:
        return None
    return {
        "persona_id": item["persona_id"],
        "title": item["title"],
        "workspace_id": item["workspace_id"],
        "console_workspace": item["console_workspace"],
        "domain": item["domain"],
        "purpose": item["purpose"],
        "allowed_actions": tuple(item["allowed_actions"]),
        "persona_capability_keys": tuple(item["persona_capability_keys"]),
        "admin_only": item["admin_only"],
        "label": item["label"],
        "external_action_authority": False,
        "real_trading_enabled": False,
    }


def ecosystem_specialist(specialist_id: object) -> dict[str, Any] | None:
    key = str(specialist_id or "").strip()
    module = _SPECIALIST_BY_ID.get(key)
    if not module:
        return None
    areas = [item["area_id"] for item in _AREAS if key in item["specialist_ids"]]
    return {
        "specialist_id": key,
        "module": module,
        "areas": areas,
        "shared_infrastructure": True,
        "independent_permissions": False,
    }


def ecosystem_capabilities(area_id: object) -> tuple[str, ...]:
    item = _AREA_BY_ID.get(str(area_id or "").strip())
    if item is None:
        return ()
    return tuple(item["capability_ids"])


def specialist_modules() -> dict[str, str]:
    """Compatibility map of specialist id to existing module path."""
    return {specialist_id: module for specialist_id, module in _SPECIALIST_ROWS}


def portable_workspaces() -> tuple[dict[str, Any], ...]:
    """Public DEFAULT_WORKSPACES projection. Safety flags stay on the normalizer."""
    rows: list[dict[str, Any]] = []
    for workspace_id in PORTABLE_WORKSPACE_ORDER:
        item = _AREA_BY_WORKSPACE[workspace_id]
        rows.append({
            "workspace_id": item["workspace_id"],
            "label": item["label"],
            "kind": item["kind"],
            "state": item["state"],
            "isolated_context": item["isolated_context"],
            "admin_only": item["admin_only"],
            "entry_key": item["entry_key"],
        })
    return tuple(rows)


def persona_catalog() -> tuple[dict[str, Any], ...]:
    """Public AION_PERSONAS projection. Only the historical persona keys are exposed."""
    by_persona = _AREA_BY_PERSONA
    rows: list[dict[str, Any]] = []
    for persona_id in PUBLIC_PERSONA_ORDER:
        item = by_persona[persona_id]
        rows.append({
            "id": item["persona_id"],
            "title": item["title"],
            "workspace": item["console_workspace"],
            "domain": item["domain"],
            "purpose": item["purpose"],
            "actions": tuple(item["allowed_actions"]),
        })
    return tuple(rows)


def persona_capability_map() -> dict[str, tuple[str, ...]]:
    """Public PERSONA_CAPABILITIES projection."""
    return {
        persona_id: tuple(_AREA_BY_PERSONA[persona_id]["persona_capability_keys"])
        for persona_id in PUBLIC_PERSONA_ORDER
    }


def ecosystem_integrity_report(
    registry: Mapping[str, Any] | None = None,
    capabilities: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Validate structural references. Broken links return state INVALID.

    The report itself never enables trading or external action authority.
    """
    areas = _as_areas(registry)
    specialists = _as_specialists(registry)
    pairs = _capability_pairs(capabilities)
    errors: list[str] = []
    warnings: list[str] = []

    specialist_ids = [row["specialist_id"] for row in specialists]
    known_specialists = {item for item in specialist_ids if item}
    if len(specialist_ids) != len(set(specialist_ids)):
        errors.append("specialist duplicado")

    capability_ids = [capability_id for capability_id, _specialist in pairs]
    known_capabilities = {item for item in capability_ids if item}
    owner_by_capability: dict[str, str] = {}
    if len(capability_ids) != len(set(capability_ids)):
        errors.append("capability duplicada")
    for capability_id, specialist in pairs:
        if not capability_id:
            errors.append("capability ausente")
            continue
        owner_by_capability.setdefault(capability_id, specialist)
        if specialist not in known_specialists:
            errors.append(f"specialist ausente: {specialist} ({capability_id})")

    workspace_ids: list[str] = []
    persona_ids: list[str] = []
    area_ids: list[str] = []
    assigned: set[str] = set()
    by_area: dict[str, dict[str, Any]] = {}
    for area in areas:
        area_id = str(area.get("area_id") or area.get("workspace_id") or "")
        workspace_id = str(area.get("workspace_id") or "")
        persona_id = str(area.get("persona_id") or "")
        area_ids.append(area_id)
        workspace_ids.append(workspace_id)
        persona_ids.append(persona_id)
        if area_id:
            by_area.setdefault(area_id, area)
        if not workspace_id:
            errors.append("workspace ausente")
        if not persona_id:
            errors.append("persona ausente")
        for specialist_id in _seq(area.get("specialist_ids")):
            if specialist_id not in known_specialists:
                errors.append(f"specialist ausente: {specialist_id}")
        area_specialists = set(_seq(area.get("specialist_ids")))
        area_capabilities = _seq(area.get("capability_ids"))
        for capability_id in area_capabilities:
            if capability_id not in known_capabilities:
                errors.append(f"capability ausente: {capability_id}")
                continue
            assigned.add(capability_id)
            owner = owner_by_capability.get(capability_id, "")
            if owner not in area_specialists:
                errors.append(f"specialist fora da área: {owner} ({capability_id})")
        actions = {item.casefold() for item in _seq(area.get("allowed_actions"))}
        blocked = sorted(actions & FORBIDDEN_ACTIONS)
        if blocked:
            errors.append(f"ação proibida: {', '.join(blocked)}")
        if area.get("external_action_authority") is not False:
            errors.append(f"external_action_authority inválido: {area_id}")
        if area.get("real_trading_enabled") is not False:
            errors.append(f"real_trading_enabled inválido: {area_id}")

    for workspace_id in sorted({item for item in workspace_ids if workspace_ids.count(item) > 1}):
        errors.append(f"workspace duplicado: {workspace_id}")
    for persona_id in sorted({item for item in persona_ids if item and persona_ids.count(item) > 1}):
        errors.append(f"persona duplicada: {persona_id}")
    for area_id in sorted({item for item in area_ids if item and area_ids.count(item) > 1}):
        errors.append(f"área duplicada: {area_id}")

    official = set(OFFICIAL_AREA_IDS)
    observed = {area_id for area_id in area_ids if area_id}
    if len(areas) != len(OFFICIAL_AREA_IDS):
        errors.append(f"contagem de áreas inválida: {len(areas)}")
    for area_id in OFFICIAL_AREA_IDS:
        if area_id not in observed:
            errors.append(f"área ausente: {area_id}")
    for area_id in sorted(observed - official):
        errors.append(f"área desconhecida: {area_id}")
    if registry is not None:
        if registry.get("external_action_authority") is not False:
            errors.append("external_action_authority do registry inválido")
        if registry.get("real_trading_enabled") is not False:
            errors.append("real_trading_enabled do registry inválido")
    for area_id, required in REQUIRED_AREA_CAPABILITIES.items():
        present = set(_seq((by_area.get(area_id) or {}).get("capability_ids")))
        for capability_id in required:
            if capability_id not in present:
                errors.append(f"capability ausente: {capability_id}")
    for capability_id in sorted(known_capabilities - assigned):
        errors.append(f"capability ausente: {capability_id}")

    unique_errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA,
        "state": "VALID" if not unique_errors else "INVALID",
        "areas": len(areas),
        "workspaces": len({item for item in workspace_ids if item}),
        "personas": len({item for item in persona_ids if item}),
        "specialists": len(known_specialists),
        "capabilities": len(known_capabilities),
        "errors": unique_errors,
        "warnings": warnings,
        "real_trading_enabled": False,
        "external_action_authority": False,
    }


__all__ = [
    "FORBIDDEN_ACTIONS",
    "OFFICIAL_AREA_IDS",
    "SCHEMA",
    "ecosystem_area",
    "ecosystem_capabilities",
    "ecosystem_integrity_report",
    "ecosystem_persona",
    "ecosystem_registry",
    "ecosystem_specialist",
    "ecosystem_workspace",
    "persona_capability_map",
    "persona_catalog",
    "portable_workspaces",
    "specialist_modules",
]
