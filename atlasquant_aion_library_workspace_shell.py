"""Opt-in, information-only AION Library admin workspace shell (sandbox).

No document data, upload, index, approval, PostgreSQL connection, key or identity
provider is reachable from this module. The host must supply trusted server-side
configuration, current user registry and the EXISTING access-panel time check.
A visible shell NEVER means the Library is operational or ready for customers.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping

from atlasquant_access_control import has_permission, session_is_current

WORKSPACE_LABEL = "📚 Biblioteca"
SCHEMA = "ATLASQUANT_AION_LIBRARY_UI_SHELL_SANDBOX_V1"
_SAFE_FINGERPRINT = re.compile(r"[a-f0-9]{24}\Z")
# Fixed, conservative posture. No state is taken from client or runtime claims.
_REMAINING = (
    "ACL persistente e revogação centralizada por cliente/domínio",
    "Integração E2E da autenticação, interface e PostgreSQL com SELECT-only",
    "Verificação independente de direitos e proveniência dos documentos",
    "Backup externo, recuperação operacional e revisão de segurança",
    "Autorização administrativa específica antes de qualquer publicação",
)


def _closed(reason: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "visible": False,
        "reason": reason,
        "operational": False,
        "document_read_enabled": False,
        "upload_enabled": False,
        "index_enabled": False,
        "approval_enabled": False,
        "external_actions_enabled": False,
        "remaining": _REMAINING,
    }


def library_shell_gate(*, access: Mapping | None, users: Mapping | None,
                       environment: str, preview_flag: str, now: int | float,
                       session_time_check: Callable) -> dict[str, object]:
    """Host-only navigation authorization, not document authorization.

    `environment` and `preview_flag` must come ONLY from trusted host config;
    `access` and `users` from the actual AtlasQuant access registry. Never
    expose this function as an endpoint accepting browser-supplied arguments.
    """
    result = _closed("NOT_ENABLED")
    if type(environment) is not str or environment.strip().upper() != "SANDBOX":
        return result
    if type(preview_flag) is not str or preview_flag.strip().lower() not in {"1", "true", "on", "yes"}:
        return result
    if not isinstance(access, Mapping) or access.get("allowed") is not True or access.get("mode") != "AUTHENTICATED":
        return _closed("AUTH_REQUIRED")
    session = access.get("session")
    if not isinstance(session, Mapping) or not isinstance(users, Mapping):
        return _closed("AUTH_REQUIRED")
    if (access.get("role") != "ADMIN" or session.get("role") != "ADMIN" or
            not isinstance(session.get("username"), str) or
            type(session.get("credential_fingerprint")) is not str or
            not _SAFE_FINGERPRINT.fullmatch(session["credential_fingerprint"])):
        return _closed("ADMIN_REQUIRED")
    try:
        # Registry-fresh role, credentials and active status; don't trust a
        # role claim from Streamlit session state without current registry.
        if not session_is_current(session, users):
            return _closed("SESSION_REVOKED")
        if not has_permission(session, "aion:admin"):
            return _closed("ADMIN_PERMISSION_REQUIRED")
        if not callable(session_time_check) or type(now) not in (int, float):
            return _closed("SESSION_INVALID")
        clock = session_time_check(dict(session), now)
        if type(clock) is not dict or clock.get("valid") is not True:
            return _closed("SESSION_EXPIRED")
    except Exception:
        return _closed("SESSION_UNAVAILABLE")
    return {**result, "visible": True, "reason": "STATIC_SANDBOX_PREVIEW_ONLY"}


def library_workspace_choices(*, standard: tuple[str, ...], gate: Mapping) -> tuple[str, ...]:
    """Keep the nine existing AION workspaces unchanged in all environments."""
    if type(standard) is not tuple or not all(type(v) is str for v in standard):
        raise ValueError("stable admin workspace tuple required")
    if WORKSPACE_LABEL in standard:
        raise ValueError("library label must not override an existing workspace")
    if isinstance(gate, Mapping) and gate.get("visible") is True and gate.get("operational") is False:
        return (*standard, WORKSPACE_LABEL)
    return standard


def render_library_shell(st: object, *, gate: Mapping) -> bool:
    """Text-only noninteractive presentation. Never accepts data or connectors."""
    if not isinstance(gate, Mapping) or gate.get("visible") is not True or gate.get("operational") is not False:
        # A stale navigation state must not bypass the gate.
        st.error("Biblioteca indisponível para esta sessão.")
        return False
    st.subheader("📚 Biblioteca AION")
    st.info("Prévia administrativa em sandbox. A Biblioteca ainda não foi ativada.")
    st.caption("Poderoso por dentro. Simples por fora.")
    left, right = st.columns(2)
    with left:
        st.metric("Acesso a documentos", "BLOQUEADO")
    with right:
        st.metric("Ingestão e indexação", "DESATIVADAS")
    st.markdown("**Etapas necessárias para liberar a Biblioteca**")
    for item in _REMAINING:
        st.markdown("- " + item)
    st.warning("Nenhum PDF pode ser enviado, consultado ou aprovado por esta prévia.")
    return True


__all__ = ["SCHEMA", "WORKSPACE_LABEL", "library_shell_gate",
           "library_workspace_choices", "render_library_shell"]
