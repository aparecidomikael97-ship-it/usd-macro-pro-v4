"""AtlasQuant operational research catalog.

A transparent inventory for ICT, SMC and Price Action research. The catalog
records implementation/readiness states without claiming that a concept is
profitable, validated, or exhaustive merely because it appears here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

SCHEMA = "ATLASQUANT_OPERATIONAL_CATALOG_V1"

STATUSES = {
    "CONCEPT",
    "PARTIAL",
    "CODED",
    "BACKTESTED",
    "PAPER",
    "VALIDATED",
    "PAUSED",
}

FAMILIES = {"ICT", "SMC", "PRICE_ACTION", "HYBRID"}


@dataclass(frozen=True)
class OperationalModel:
    model_id: str
    label: str
    family: str
    status: str
    components: tuple[str, ...]
    objective_rules_ready: bool = False
    replay_module: str | None = None
    notes: str = ""


def _model(
    model_id: str,
    label: str,
    family: str,
    status: str,
    components: Iterable[str],
    *,
    objective_rules_ready: bool = False,
    replay_module: str | None = None,
    notes: str = "",
) -> OperationalModel:
    family = str(family).upper()
    status = str(status).upper()
    if family not in FAMILIES:
        raise ValueError("family inválida")
    if status not in STATUSES:
        raise ValueError("status inválido")
    return OperationalModel(
        model_id=str(model_id),
        label=str(label),
        family=family,
        status=status,
        components=tuple(str(x) for x in components),
        objective_rules_ready=bool(objective_rules_ready),
        replay_module=replay_module,
        notes=str(notes),
    )


# Current catalog. "CONCEPT" means planned/documented only; it is not an
# implementation claim. Existing objective replays are marked CODED.
_MASTER = (
    _model(
        "BOS_CHOCH_OB",
        "BOS/CHOCH + Order Block",
        "SMC",
        "CODED",
        ("structure", "bos", "choch", "order_block"),
        objective_rules_ready=True,
        replay_module="atlasquant_strategy_replay",
        notes="Objective historical replay already exists.",
    ),
    _model(
        "FVG",
        "Fair Value Gap",
        "ICT",
        "CODED",
        ("imbalance", "fvg", "revisit"),
        objective_rules_ready=True,
        replay_module="atlasquant_fvg_replay",
        notes="Standalone FVG replay already exists.",
    ),
    _model(
        "OTE",
        "Optimal Trade Entry 62–79%",
        "ICT",
        "CODED",
        ("dealing_range", "premium_discount", "fibonacci", "ote"),
        objective_rules_ready=True,
        replay_module="atlasquant_ote_replay",
    ),
    _model(
        "CRT",
        "Candle Range Theory",
        "ICT",
        "CODED",
        ("range", "liquidity", "displacement", "reversal_or_expansion"),
        objective_rules_ready=True,
        replay_module="atlasquant_crt_replay",
    ),
    _model(
        "AMD_PO3",
        "AMD / Power of Three",
        "ICT",
        "CODED",
        ("accumulation", "manipulation", "distribution"),
        objective_rules_ready=True,
        replay_module="atlasquant_amd_replay",
    ),
    _model(
        "LIQUIDITY_SWEEP_REVERSAL",
        "Liquidity Sweep + Reversal",
        "HYBRID",
        "PARTIAL",
        ("bsl_ssl", "sweep", "displacement", "structure_shift"),
        notes="Shared components exist; dedicated replay must be specified and validated.",
    ),
    _model(
        "BREAKER_MODEL",
        "Breaker Block Model",
        "ICT",
        "PARTIAL",
        ("failed_order_block", "structure_shift", "retest"),
        notes="Conceptual components exist; dedicated objective replay not yet certified.",
    ),
    _model(
        "MITIGATION_MODEL",
        "Mitigation Block Model",
        "ICT",
        "PARTIAL",
        ("order_block", "mitigation", "retest"),
        notes="Needs dedicated entry/invalidation specification.",
    ),
    _model(
        "SILVER_BULLET",
        "ICT Silver Bullet",
        "ICT",
        "CONCEPT",
        ("killzone", "liquidity_sweep", "mss", "fvg"),
        notes="Planned research item; not yet an implemented replay.",
    ),
    _model(
        "TURTLE_SOUP",
        "ICT Turtle Soup",
        "ICT",
        "CONCEPT",
        ("prior_high_low", "liquidity_sweep", "rejection"),
        notes="Planned research item; not yet an implemented replay.",
    ),
    _model(
        "UNICORN",
        "ICT Unicorn Model",
        "ICT",
        "CONCEPT",
        ("breaker", "fvg", "overlap_zone", "retest"),
        notes="Planned research item; not yet an implemented replay.",
    ),
    _model(
        "JUDAS_SWING",
        "ICT Judas Swing",
        "ICT",
        "CONCEPT",
        ("session_open", "false_move", "liquidity", "reversal"),
        notes="Planned research item; session/time rules must be made explicit.",
    ),
    _model(
        "MMXM",
        "Market Maker Buy/Sell Model",
        "ICT",
        "CONCEPT",
        ("liquidity", "displacement", "retracement", "distribution"),
        notes="Requires objective state-machine rules before valid backtesting.",
    ),
    _model(
        "SMT_DIVERGENCE",
        "SMT Divergence",
        "ICT",
        "PARTIAL",
        ("correlated_assets", "relative_high_low", "divergence"),
        notes="Needs synchronized multi-asset historical data for a dedicated replay.",
    ),
    _model(
        "WEEKLY_PROFILE",
        "Weekly Profile / Weekly High-Low Study",
        "ICT",
        "CONCEPT",
        ("day_of_week", "weekly_high_low", "session", "regime"),
        notes="Statistical study only; no fixed Tuesday/Wednesday rule is assumed.",
    ),
    _model(
        "QUARTERLY_THEORY",
        "Quarterly Theory",
        "ICT",
        "CONCEPT",
        ("time_partition", "accumulation", "manipulation", "distribution"),
        notes="Educational/research item; rules require formalization before replay.",
    ),
    _model(
        "PA_SUPPORT_RESISTANCE",
        "Support/Resistance Reaction",
        "PRICE_ACTION",
        "CONCEPT",
        ("support_resistance", "rejection", "confirmation"),
        notes="Bridge model for Price Action users; objective rules still required.",
    ),
    _model(
        "PA_BREAKOUT_RETEST",
        "Breakout + Retest",
        "PRICE_ACTION",
        "CONCEPT",
        ("range_or_level", "breakout", "retest", "confirmation"),
    ),
    _model(
        "PA_TREND_PULLBACK",
        "Trend Pullback",
        "PRICE_ACTION",
        "CONCEPT",
        ("trend", "pullback", "continuation_confirmation"),
    ),
    _model(
        "PA_FALSE_BREAK",
        "False Break / Liquidity Trap",
        "PRICE_ACTION",
        "CONCEPT",
        ("level", "breakout_failure", "reentry", "reversal_confirmation"),
        notes="Useful educational bridge to liquidity concepts without claiming institutional intent.",
    ),
)


def master_operational_catalog() -> tuple[OperationalModel, ...]:
    return tuple(_MASTER)


def catalog_rows() -> list[dict[str, object]]:
    return [asdict(x) for x in _MASTER]


def model_by_id(model_id: object) -> OperationalModel | None:
    target = str(model_id or "").strip().upper()
    return next((x for x in _MASTER if x.model_id == target), None)


def catalog_summary() -> dict[str, object]:
    by_status = {status: 0 for status in sorted(STATUSES)}
    by_family = {family: 0 for family in sorted(FAMILIES)}
    for model in _MASTER:
        by_status[model.status] += 1
        by_family[model.family] += 1
    return {
        "schema": SCHEMA,
        "models": len(_MASTER),
        "by_status": by_status,
        "by_family": by_family,
        "objective_replay_ready": sum(1 for x in _MASTER if x.objective_rules_ready),
        "exhaustive_claim": False,
        "interpretation": (
            "O catálogo é um inventário de pesquisa em evolução. Presença no catálogo "
            "não significa validação, rentabilidade ou recomendação."
        ),
    }


def transition_allowed(current: str, target: str) -> bool:
    """Conservative lifecycle transition contract.

    A setup cannot jump directly from CONCEPT/PARTIAL/CODED into VALIDATED.
    VALIDATED requires prior PAPER state. PAUSED is always reachable.
    """
    current = str(current).upper()
    target = str(target).upper()
    if current not in STATUSES or target not in STATUSES:
        return False
    if current == target:
        return True
    if target == "PAUSED":
        return True
    allowed = {
        "CONCEPT": {"PARTIAL", "CODED"},
        "PARTIAL": {"CODED"},
        "CODED": {"BACKTESTED"},
        "BACKTESTED": {"PAPER"},
        "PAPER": {"VALIDATED"},
        "VALIDATED": {"PAPER"},
        "PAUSED": {"CONCEPT", "PARTIAL", "CODED", "BACKTESTED", "PAPER"},
    }
    return target in allowed.get(current, set())


__all__ = [
    "SCHEMA",
    "STATUSES",
    "FAMILIES",
    "OperationalModel",
    "master_operational_catalog",
    "catalog_rows",
    "model_by_id",
    "catalog_summary",
    "transition_allowed",
]
