"""Streamlit panel for AION Replay inside the Laboratory workspace.

Presentation only. Replay state is session-local; this module never writes the
Checkpoint Mestre, runtime, feature flags, entitlements, provider state or
trading state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import streamlit as st

from atlasquant_aion_replay_lab import (
    build_news_replay_package,
    news_replay_catalog,
    reveal_news_replay_outcome,
    submit_news_replay_decision,
)


_PACKAGE_KEY = "aion_replay_lab_package_v1"
_SESSION_KEY = "aion_replay_lab_session_v1"


def _session() -> dict[str, Any] | None:
    value = st.session_state.get(_SESSION_KEY)
    return dict(value) if isinstance(value, Mapping) else None


def _package() -> dict[str, Any] | None:
    value = st.session_state.get(_PACKAGE_KEY)
    return dict(value) if isinstance(value, Mapping) else None


def _reset() -> None:
    st.session_state.pop(_PACKAGE_KEY, None)
    st.session_state.pop(_SESSION_KEY, None)


def render_replay_lab_panel(checkpoint: Mapping[str, Any] | None) -> None:
    st.markdown("#### ⏪ Modo Replay · treinamento point-in-time")
    st.caption(
        "Treine usando somente informação comprovadamente disponível no instante histórico. "
        "O Replay não consulta dado ao vivo, não grava Checkpoint e nunca executa trade."
    )

    catalog = news_replay_catalog(checkpoint)
    scenarios = [
        dict(item)
        for item in list(catalog.get("scenarios") or [])
        if isinstance(item, Mapping)
    ]

    active_package = _package()
    active_session = _session()

    if active_package is None or active_session is None:
        if not scenarios:
            st.info(
                "Ainda não existe cenário histórico elegível no Live Event Journal. "
                "O AION não fabrica cenário: sincronize/registre histórico com first_seen_at válido "
                "e volte ao Replay."
            )
            st.caption(
                "Research refs sem available_at explícito não entram automaticamente no Replay."
            )
            return

        labels: dict[str, dict[str, Any]] = {}
        for item in scenarios:
            cutoff = str(item.get("replay_at") or "")
            title = str(item.get("title") or "Evento")
            label = f"{cutoff[:16].replace('T', ' ')} · {title[:110]}"
            labels[label] = item

        selected_label = st.selectbox(
            "Cenário histórico",
            list(labels.keys()),
            key="aion_replay_lab_scenario",
        )
        selected = labels[selected_label]
        window = st.select_slider(
            "Janela posterior para comparação",
            options=[60, 120, 240, 480, 720, 1440],
            value=240,
            format_func=lambda value: f"{int(value)} min",
            key="aion_replay_lab_window",
            help=(
                "A janela só é usada depois que sua decisão for registrada. "
                "Nenhum evento futuro é mostrado antes disso."
            ),
        )
        if st.button(
            "Iniciar Replay",
            key="aion_replay_lab_start",
            type="primary",
            width="stretch",
        ):
            package = build_news_replay_package(
                checkpoint,
                event_id=selected.get("event_id"),
                outcome_window_minutes=window,
            )
            session = (
                package.get("session")
                if isinstance(package.get("session"), Mapping)
                else None
            )
            if package.get("state") == "READY" and session:
                st.session_state[_PACKAGE_KEY] = package
                st.session_state[_SESSION_KEY] = dict(session)
                st.rerun()
            else:
                st.warning(
                    "Esse cenário não pôde ser aberto com segurança. "
                    "Nenhuma evidência futura foi mostrada."
                )
        st.caption(
            "Fonte atual: Live Event Journal · snapshot histórico campo-a-campo completo: NÃO · "
            "campos mutáveis posteriores são ocultados."
        )
        return

    session = active_session
    package = active_package
    frame = (
        session.get("frame")
        if isinstance(session.get("frame"), Mapping)
        else {}
    )

    st.info(
        f"**{session.get('title') or 'Replay'}** · corte histórico "
        f"{str(session.get('replay_at') or '')[:19].replace('T', ' ')} UTC"
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Estado", str(session.get("state") or "UNKNOWN"))
    c2.metric("Evidências visíveis", int((frame.get("counts") or {}).get("visible") or 0))
    c3.metric("Point-in-time", "SIM" if frame.get("point_in_time_verified") else "PARCIAL")

    rows = [
        dict(item)
        for item in list(package.get("visible_rows") or [])
        if isinstance(item, Mapping)
    ]
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.caption("Nenhuma evidência histórica estava visível nesse corte.")

    state = str(session.get("state") or "UNKNOWN").upper()

    if state == "ACTIVE":
        with st.form("aion_replay_lab_decision_form", clear_on_submit=False):
            choice = st.radio(
                "Sua leitura naquele instante",
                ("AGUARDAR", "VIÉS DE ALTA", "VIÉS DE BAIXA", "INDEFINIDO"),
                horizontal=True,
            )
            rationale = st.text_area(
                "Por quê?",
                max_chars=1600,
                placeholder="Registre somente o raciocínio possível com a evidência acima.",
            )
            confidence = st.slider(
                "Confiança na sua leitura",
                min_value=0,
                max_value=100,
                value=50,
                help="Autoconfiança de treinamento; não é probabilidade de lucro.",
            )
            submitted = st.form_submit_button(
                "Registrar decisão",
                type="primary",
                width="stretch",
            )
        if submitted:
            updated = submit_news_replay_decision(
                session,
                choice=choice,
                rationale=rationale,
                confidence_pct=confidence,
                submitted_at=datetime.now(timezone.utc).isoformat(),
            )
            st.session_state[_SESSION_KEY] = updated
            st.rerun()

    elif state == "DECISION_RECORDED":
        decision = (
            session.get("decision")
            if isinstance(session.get("decision"), Mapping)
            else {}
        )
        st.success(
            "Decisão registrada antes da revelação: "
            + str(decision.get("choice") or "—")
            + "."
        )
        st.caption(
            "Agora o resultado posterior pode ser consultado sem alterar sua decisão registrada."
        )
        outcome = (
            package.get("outcome")
            if isinstance(package.get("outcome"), Mapping)
            else None
        )
        if outcome:
            if st.button(
                "Revelar o que aconteceu depois",
                key="aion_replay_lab_reveal",
                type="primary",
                width="stretch",
            ):
                updated = reveal_news_replay_outcome(
                    session,
                    outcome,
                    revealed_at=datetime.now(timezone.utc).isoformat(),
                )
                st.session_state[_SESSION_KEY] = updated
                st.rerun()
        else:
            st.info(
                "Não há evidência posterior registrada no Journal dentro da janela escolhida. "
                "O AION não inventa desfecho."
            )

    elif state == "REVEALED":
        outcome = (
            session.get("outcome")
            if isinstance(session.get("outcome"), Mapping)
            else {}
        )
        payload = (
            outcome.get("payload")
            if isinstance(outcome.get("payload"), Mapping)
            else {}
        )
        later = [
            dict(item)
            for item in list(payload.get("later_events") or [])
            if isinstance(item, Mapping)
        ]
        st.markdown("**O que apareceu depois da sua decisão**")
        if later:
            st.dataframe(
                [
                    {
                        "Quando apareceu": item.get("first_seen_at"),
                        "Tipo": item.get("kind"),
                        "Evento": item.get("headline"),
                    }
                    for item in later
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("Nenhum evento posterior foi registrado nessa janela.")
        st.caption(
            "Comparação: "
            + str(session.get("evaluation") or "UNSCORED")
            + " · descritiva apenas. Resultado posterior não prova qualidade da decisão "
            "e não representa probabilidade de lucro."
        )

    else:
        st.warning(
            "O Replay entrou em estado bloqueado: "
            + str(session.get("reason") or "UNKNOWN")
            + "."
        )

    if st.button(
        "Encerrar Replay desta sessão",
        key="aion_replay_lab_reset",
        width="stretch",
    ):
        _reset()
        st.rerun()

    st.caption(
        "Treinamento somente · dados ao vivo: NÃO · Checkpoint escrito: NÃO · "
        "promoção automática: NÃO · execução real: BLOQUEADA."
    )


__all__ = ["render_replay_lab_panel"]
