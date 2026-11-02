"""Authenticated, quota-conscious calendar adapter for AtlasQuant Trader.

Only performs one read request per UTC hour key while the Painel Mestre
is visited, using the existing EODHD entitlement if configured.
No AION Worker, cron, payment, order, or unsupervised external action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import os
from typing import Any, Mapping

from atlasquant_trader_economic_calendar import (
    normalize_events, request_eodhd_daily,
)
from atlasquant_trader_opening_collector import brasilia_clock

SESSION_CONSENSUS = "atlasquant_calendar_manual_consensus"
SESSION_MODEL = "atlasquant_calendar_latest_read_model"


def _token(st: Any) -> str:
    """Use the existing token privately; never write/log or render its value."""
    existing = os.environ.get("CHAVE_EODHD")
    if existing and existing.strip():
        return existing.strip()
    try:
        value = st.secrets.get("CHAVE_EODHD", "")
        return str(value).strip()
    except Exception:
        return ""


@lru_cache(maxsize=12)
def _hourly_feed(token: str, date_brt: str, hour_utc: int) -> dict[str, Any]:
    # Date and hourly keys force the cache to refresh when the app is open.
    # The token is never exposed; only this process holds it in memory.
    return request_eodhd_daily(token)


def _identity(access: Mapping[str, Any]) -> str:
    session = access.get("session") or {}
    if not isinstance(session, Mapping):
        session = {}
    return str(access.get("username") or session.get("username") or "").strip()[:80]


def read_calendar(st: Any, access: Mapping[str, Any],
                  *, at: datetime | None = None) -> dict[str, Any]:
    """Safe lazy fetch, only called after authenticated Trader access validation."""
    if access.get("allowed") is not True:
        raise PermissionError("calendar access denied")
    now = at or datetime.now(timezone.utc)
    local = brasilia_clock(now)
    identity = _identity(access)
    stored = st.session_state.get(SESSION_CONSENSUS) or {}
    # Session-only, scoped to same signed-in identity.
    manual = {
        key: item for key, item in stored.items()
        if identity and isinstance(item, Mapping) and item.get("author") == identity
    } if isinstance(stored, dict) else {}
    token = _token(st)
    if token:
        hour_key = int(now.timestamp()) // 3600
        response = _hourly_feed(token, local.date().isoformat(), hour_key)
    else:
        response = {"ok": False, "reason": "NO_EXISTING_TOKEN", "data": []}
    model = normalize_events(response, at=now, manual=manual)
    st.session_state[SESSION_MODEL] = model
    return model


def manual_consensus_controls(st: Any, access: Mapping[str, Any]) -> None:
    """Explicit ADMIN manual override; session-limited, never automatic truth."""
    if access.get("allowed") is not True or str(access.get("role") or "").upper() != "ADMIN":
        return
    identity = _identity(access)
    if not identity:
        return
    model = st.session_state.get(SESSION_MODEL)
    if not isinstance(model, Mapping) or model.get("state") != "READY":
        return
    now = datetime.now(timezone.utc)
    candidates = []
    for item in model.get("events", []):
        if (not isinstance(item, Mapping) or item.get("consensus") is not None
                or not item.get("id")):
            continue
        try:
            released = datetime.fromisoformat(str(item["release_utc"]))
        except (ValueError, TypeError):
            continue
        if released > now:
            candidates.append(item)
    if not candidates:
        return
    with st.expander("Consenso manual · somente ADMIN (quando o provedor não informar)", expanded=False):
        st.caption("Use apenas um número obtido de fonte identificada. Esta entrada é "
                   "temporária na sessão e não substitui o consenso oficial. "
                   "Não persiste após reiniciar a hospedagem.")
        options = {
            str(e["id"]): (
                str(e.get("time_brt") or "") + " · " +
                str(e.get("country") or "") + " · " +
                str(e.get("title") or "") + " (" +
                str(e.get("comparison") or "nível") + ")"
            ) for e in candidates
        }
        with st.form("atlasquant_calendar_consensus_admin_form", clear_on_submit=False):
            event_id = st.selectbox("Evento do calendário", options=list(options),
                                    format_func=lambda key: options[key])
            value = st.number_input("Consenso numérico", min_value=-1000000.0,
                                    max_value=1000000.0, value=0.0, step=0.1,
                                    format="%.3f")
            source = st.text_input("Fonte consultada (obrigatória)",
                                   placeholder="Instituição, relatório ou publicação",
                                   max_chars=180)
            confirm = st.form_submit_button("Registrar consenso manual")
        if confirm:
            if not source.strip():
                st.error("Informe a fonte do número.")
                return
            event = next((e for e in candidates if e["id"] == event_id), None)
            if not event:
                st.error("Evento sem validação.")
                return
            try:
                release_at = datetime.fromisoformat(event["release_utc"])
            except (ValueError, TypeError):
                st.error("Horário inválido; não registrei o consenso.")
                return
            if datetime.now(timezone.utc) >= release_at:
                st.error("O evento já passou. Não é permitido inserir consenso retroativo.")
                return
            entries = dict(st.session_state.get(SESSION_CONSENSUS) or {})
            entries[event_id] = {
                "event_id": event_id,
                "value": float(value),
                "source": source.strip(),
                "author": identity,
                "entered_at": datetime.now(timezone.utc).isoformat(),
            }
            st.session_state[SESSION_CONSENSUS] = entries
            st.success("Consenso temporário registrado com origem manual identificada.")
            st.rerun()


__all__ = ["read_calendar", "manual_consensus_controls", "SESSION_CONSENSUS"]
