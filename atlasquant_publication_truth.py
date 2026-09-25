"""Truthful publication/deployment posture for AtlasQuant.

This module never assumes that code merged to GitHub is already live. It only
compares identities that were explicitly observed or provided by the runtime.
No deploy, provider call, permission change or trading action is performed.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_PUBLICATION_TRUTH_V1"


def _clean(value: Any, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


def _sha(value: Any) -> str:
    raw = _clean(value, 64).lower()
    return raw if re.fullmatch(r"[0-9a-f]{40}", raw) else ""


def publication_truth(
    *,
    environment: Any = "",
    source_build: Any = "",
    runtime_commit: Any = "",
    expected_main_commit: Any = "",
    production_verified_commit: Any = "",
    interface_validation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    env = _clean(environment, 40).upper() or "UNKNOWN"
    build = _clean(source_build, 80)
    runtime_sha = _sha(runtime_commit)
    main_sha = _sha(expected_main_commit)
    verified_sha = _sha(production_verified_commit)
    validation = dict(interface_validation or {})

    runtime_identity = "CONFIRMED" if runtime_sha else "UNKNOWN"
    main_identity = "CONFIRMED" if main_sha else "UNKNOWN"

    if runtime_sha and main_sha:
        main_match = "MATCH" if runtime_sha == main_sha else "MISMATCH"
    else:
        main_match = "UNKNOWN"

    if runtime_sha and verified_sha:
        production_verification = (
            "VERIFIED" if runtime_sha == verified_sha else "MISMATCH"
        )
    else:
        production_verification = "UNKNOWN"

    interface_complete = bool(
        validation.get("all_confirmed_current_build", False)
    )

    if main_match == "MISMATCH":
        state = "RUNTIME_BEHIND_OR_DIVERGED"
    elif main_match == "MATCH" and production_verification == "VERIFIED":
        state = (
            "PRODUCTION_VERIFIED"
            if interface_complete
            else "PRODUCTION_VERIFIED_INTERFACE_PENDING"
        )
    elif main_match == "MATCH":
        state = "MAIN_MATCH_PRODUCTION_UNVERIFIED"
    elif runtime_identity == "CONFIRMED":
        state = "RUNTIME_IDENTIFIED_MAIN_UNKNOWN"
    elif build:
        state = "SOURCE_BUNDLE_IDENTIFIED"
    else:
        state = "UNKNOWN"

    if state == "RUNTIME_BEHIND_OR_DIVERGED":
        next_action = (
            "Revisar o commit em execução antes de qualquer afirmação de publicação. "
            "Não tratar o runtime como atualizado."
        )
    elif state == "PRODUCTION_VERIFIED":
        next_action = (
            "Produção e main têm a mesma identidade confirmada e as telas críticas "
            "deste build foram validadas."
        )
    elif state == "PRODUCTION_VERIFIED_INTERFACE_PENDING":
        next_action = (
            "A identidade de produção foi confirmada, mas ainda faltam telas críticas "
            "deste build para revalidar."
        )
    elif state == "MAIN_MATCH_PRODUCTION_UNVERIFIED":
        next_action = (
            "O commit em execução coincide com a main esperada, mas ainda falta uma "
            "prova explícita de validação da produção."
        )
    elif state == "RUNTIME_IDENTIFIED_MAIN_UNKNOWN":
        next_action = (
            "O commit em execução foi identificado, mas não há identidade confirmada "
            "da main para comparação."
        )
    elif state == "SOURCE_BUNDLE_IDENTIFIED":
        next_action = (
            "O bundle em execução foi identificado, mas o commit de runtime/main ainda "
            "não está confirmado."
        )
    else:
        next_action = (
            "Coletar identidade do runtime e da main antes de afirmar que a versão está publicada."
        )

    return {
        "schema": SCHEMA,
        "state": state,
        "truth_state": "CONFIRMED" if state != "UNKNOWN" else "UNKNOWN",
        "environment": env,
        "source_build": build,
        "runtime_commit": runtime_sha,
        "expected_main_commit": main_sha,
        "production_verified_commit": verified_sha,
        "runtime_identity": runtime_identity,
        "main_identity": main_identity,
        "main_match": main_match,
        "production_verification": production_verification,
        "interface_validation_complete": interface_complete,
        "can_claim_latest_main_live": bool(
            main_match == "MATCH"
            and production_verification == "VERIFIED"
        ),
        "can_claim_interface_validated": interface_complete,
        "next_action": next_action,
        "automatic_deploy": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


__all__ = ["SCHEMA", "publication_truth"]
