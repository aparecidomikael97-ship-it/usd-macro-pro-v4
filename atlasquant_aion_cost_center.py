"""AtlasQuant / AION Cost Center V1.

Read-only cost truth layer for the administrative Núcleo.

The Cost Center accepts explicit cost evidence for infrastructure, market data,
AI/APIs, voice/TTS and video/content. It separates CONFIRMED, ESTIMATED and
UNKNOWN evidence, refuses negative/non-finite amounts, never mixes currencies
silently, and never turns an estimate into a confirmed expense.

It does not purchase, subscribe, upgrade, charge, renew, call a provider,
change a budget, persist a payment method or authorize trading.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import math


SCHEMA = "ATLASQUANT_AION_COST_CENTER_V1"

CATEGORIES = (
    "infrastructure",
    "market_data",
    "ai_api",
    "voice_tts",
    "video_content",
    "other",
)

CATEGORY_LABELS = {
    "infrastructure": "Infraestrutura",
    "market_data": "Dados de mercado",
    "ai_api": "IA / APIs",
    "voice_tts": "Voz / TTS",
    "video_content": "Vídeo / Conteúdo",
    "other": "Outros",
}

TRUTH_STATES = ("CONFIRMED", "ESTIMATED", "UNKNOWN")
SUPPORTED_CURRENCY = "USD"
SUPPORTED_PERIOD = "MONTHLY"


def _text(value: Any, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _money(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return round(number, 6)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0 or not number.is_integer():
        return None
    return int(number)


def normalize_cost_evidence(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize one cost record without upgrading evidence quality."""
    item = dict(raw or {})
    category = _text(item.get("category"), 80).lower()
    if category not in CATEGORIES:
        category = "other"

    truth = _text(item.get("truth_state"), 40).upper()
    if truth not in TRUTH_STATES:
        truth = "UNKNOWN"

    currency = _text(item.get("currency"), 12).upper()
    period = _text(item.get("period"), 24).upper()
    amount = _money(item.get("amount"))

    reasons: list[str] = []
    usable = True

    if not currency:
        usable = False
        reasons.append("CURRENCY_REQUIRED")
    elif currency != SUPPORTED_CURRENCY:
        usable = False
        reasons.append("UNSUPPORTED_CURRENCY")
    if not period:
        usable = False
        reasons.append("PERIOD_REQUIRED")
    elif period != SUPPORTED_PERIOD:
        usable = False
        reasons.append("UNSUPPORTED_PERIOD")
    if amount is None:
        usable = False
        reasons.append("INVALID_AMOUNT")
    if truth == "UNKNOWN":
        usable = False
        reasons.append("TRUTH_UNKNOWN")

    if truth == "CONFIRMED" and not _text(item.get("source"), 160):
        usable = False
        reasons.append("CONFIRMED_SOURCE_REQUIRED")

    return {
        "id": _text(item.get("id"), 100),
        "label": _text(item.get("label") or item.get("name"), 160),
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "truth_state": truth,
        "amount_usd_monthly": amount if usable else None,
        "currency": currency,
        "period": period,
        "source": _text(item.get("source"), 160),
        "observed_at": _text(item.get("observed_at"), 96),
        "usable": usable,
        "reasons": reasons,
        "automatic_charge": False,
        "automatic_upgrade": False,
        "executes_action": False,
    }


def build_cost_center(
    evidence: Sequence[Mapping[str, Any]] | None,
    *,
    active_users: Any = None,
    active_users_confirmed: bool = False,
) -> dict[str, Any]:
    """Aggregate explicit monthly USD cost evidence with truth separation."""
    rows = [
        normalize_cost_evidence(item)
        for item in list(evidence or [])
        if isinstance(item, Mapping)
    ]

    confirmed_total = 0.0
    estimated_total = 0.0
    confirmed_items = 0
    estimated_items = 0
    rejected = 0
    by_category: dict[str, dict[str, float | int]] = {
        category: {
            "confirmed_usd": 0.0,
            "estimated_usd": 0.0,
            "usable_items": 0,
            "rejected_items": 0,
        }
        for category in CATEGORIES
    }

    for row in rows:
        bucket = by_category[row["category"]]
        if not row["usable"]:
            rejected += 1
            bucket["rejected_items"] = int(bucket["rejected_items"]) + 1
            continue

        amount = float(row["amount_usd_monthly"] or 0.0)
        bucket["usable_items"] = int(bucket["usable_items"]) + 1
        if row["truth_state"] == "CONFIRMED":
            confirmed_items += 1
            confirmed_total += amount
            bucket["confirmed_usd"] = round(
                float(bucket["confirmed_usd"]) + amount, 6
            )
        elif row["truth_state"] == "ESTIMATED":
            estimated_items += 1
            estimated_total += amount
            bucket["estimated_usd"] = round(
                float(bucket["estimated_usd"]) + amount, 6
            )

    users = _positive_int(active_users) if active_users_confirmed else None
    confirmed_per_user = (
        round(confirmed_total / users, 6)
        if users is not None
        else None
    )
    projected_per_user = (
        round((confirmed_total + estimated_total) / users, 6)
        if users is not None
        else None
    )

    if not rows:
        state = "UNKNOWN"
    elif rejected == len(rows):
        state = "UNKNOWN"
    elif estimated_items > 0 or rejected > 0:
        state = "PARTIAL"
    else:
        state = "CONFIRMED"

    return {
        "schema": SCHEMA,
        "state": state,
        "currency": SUPPORTED_CURRENCY,
        "period": SUPPORTED_PERIOD,
        "items": rows,
        "items_total": len(rows),
        "usable_items": sum(1 for row in rows if row["usable"]),
        "confirmed_items": confirmed_items,
        "estimated_items": estimated_items,
        "rejected_items": rejected,
        "confirmed_monthly_usd": round(confirmed_total, 6),
        "estimated_monthly_usd": round(estimated_total, 6),
        "projected_monthly_usd": round(confirmed_total + estimated_total, 6),
        "by_category": by_category,
        "active_users": users,
        "active_users_confirmed": users is not None,
        "confirmed_cost_per_user_usd": confirmed_per_user,
        "projected_cost_per_user_usd": projected_per_user,
        "estimate_is_not_spend": True,
        "automatic_charge": False,
        "automatic_subscription": False,
        "automatic_upgrade": False,
        "automatic_paid_fallback": False,
        "executes_action": False,
        "real_trading_enabled": False,
        "interpretation": (
            "Gasto confirmado e estimativa são mantidos separados. "
            "O valor projetado não prova cobrança, pagamento ou fatura."
        ),
    }


def compact_cost_summary(center: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a compact Admin summary with no billing action."""
    data = dict(center or {})
    state = _text(data.get("state"), 40).upper() or "UNKNOWN"
    confirmed = _money(data.get("confirmed_monthly_usd"))
    estimated = _money(data.get("estimated_monthly_usd"))
    projected = _money(data.get("projected_monthly_usd"))

    return {
        "state": state,
        "confirmed_monthly_usd": confirmed or 0.0,
        "estimated_monthly_usd": estimated or 0.0,
        "projected_monthly_usd": projected or 0.0,
        "confirmed_cost_per_user_usd": _money(
            data.get("confirmed_cost_per_user_usd")
        ),
        "projected_cost_per_user_usd": _money(
            data.get("projected_cost_per_user_usd")
        ),
        "billing_verified": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "CATEGORIES",
    "CATEGORY_LABELS",
    "TRUTH_STATES",
    "normalize_cost_evidence",
    "build_cost_center",
    "compact_cost_summary",
]
