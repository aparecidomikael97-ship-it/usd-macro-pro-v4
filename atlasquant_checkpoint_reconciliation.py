"""Checkpoint Mestre reconciliation gate.

Reads the versioned manifest and ADR registry. It does not open the network,
write runtime state, call a provider, or change a decision.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

GATE_ID = "CHECKPOINT_MESTRE_RECONCILIATION_2026_09_15_TO_2026_09_29"
PERIOD_START = "2026-09-15"
PERIOD_END = "2026-09-29"
MANIFEST_PATH = "docs/continuidade/checkpoint_mestre_reconciliation_2026-09-29.json"
NARRATIVE_PATH = "docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md"
PRESERVED_CHECKPOINT = "docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md"
ADR_README = "docs/adr/README.md"

OFFICIAL_STATES = (
    "APROVADO / PENDENTE",
    "IMPLEMENTADO / EM VALIDAÇÃO",
    "VALIDADO",
    "DEPENDÊNCIA EXTERNA",
    "SUBSTITUÍDO",
    "DESCARTADO",
    "UNVERIFIED",
    "NEEDS HUMAN RECONCILIATION",
)
PENDING_STATES = (
    "APROVADO / PENDENTE",
    "UNVERIFIED",
    "NEEDS HUMAN RECONCILIATION",
)
ADR_STATUSES = ("PROPOSED", "ACCEPTED", "SUPERSEDED", "DEPRECATED", "REJECTED")
ADR_HEADINGS = (
    "Título",
    "Data",
    "Status",
    "Contexto",
    "Problema",
    "Alternativas consideradas",
    "Decisão",
    "Consequências",
    "Componentes afetados",
    "Segurança",
    "Compatibilidade",
    "Rollback/migração",
    "PR/commit relacionado",
    "Supersedes",
    "Superseded by",
)
REQUIRED_DECISION_IDS = (
    "D-AION-SINGLE-NUCLEUS",
    "D-ADMIN-DOORS-FOUR",
    "D-SPECIALISTS-NOT-INDEPENDENT-AIS",
    "D-FOUR-CLOSURES",
    "D-SPECIALIST-CERTIFICATION-REQUIRED",
    "D-BUSINESS-FIVE-FRONTS",
    "D-BUSINESS-OPERATIONAL-GUIDELINE",
    "D-HUMAN-APPROVAL-HIGH-IMPACT",
    "D-COMMERCIAL-AION-REQUIREMENTS",
    "D-COMMERCIAL-FLOW",
    "D-REVENUE-IS-NOT-PROFIT",
    "D-OPPORTUNITY-SCOUT",
    "D-OPPORTUNITY-FLOW",
    "D-NO-VIRAL-OR-TOP20-PROOF",
    "D-ADR-ARCHITECTURE-RECORDS",
    "D-ADR-AVERAGE-DAILY-RANGE",
    "D-ADR-DEPOSITARY-RECEIPTS",
    "D-ATR-SEPARATE-FROM-ADR",
    "D-ECOSYSTEM-ROBUSTNESS",
    "D-PRIORITY-ORDER-2026-09-29",
    "D-CHECKPOINT-MASTER-NO-PARALLEL-STORE",
    "D-TRUTH-INCOMPLETE-NOT-CONFIRMED",
    "D-ADMIN-USER-SEPARATION",
    "D-SPECIALISTS-SHARE-CORE",
    "D-DOD-HUMAN-RELEASE-REVIEW",
    "D-REAL-TRADING-FAIL-CLOSED",
    "D-RELEASE-DEPLOY-MERGE-GATE",
    "D-2026-09-22-DOCUMENT-PRESERVED",
)
REQUIRED_SOURCES = (
    "docs/continuidade/REGISTRO_ORIGINAL_2026-09-15.md",
    "docs/continuidade/VISAO_MESTRE_BACKLOG_2026-09-18.md",
    "docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md",
    "docs/continuidade/AION_CHECKPOINT_NEXTGEN_APPROVED_2026-09-25.md",
    "docs/continuidade/AION_CHECKPOINT_ECOSSISTEMA_UX_2026-09-27.md",
    "docs/aion/ARCHITECTURE.md",
    "docs/aion/CORE_CHECKPOINT_MEMORY.md",
    "docs/product/PRODUCT_DECISIONS_2026-09-19.md",
)
REQUIRED_ADR_IDS = tuple(f"ADR-{index:04d}" for index in range(1, 11))


def _root(root: Path | None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parent


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    path = _root(root) / MANIFEST_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def _error(errors: list[str], message: str) -> None:
    errors.append(message)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def validate_decision(item: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    decision_id = str(item.get("id") or "")
    state = str(item.get("state") or "")
    evidence = [str(ref) for ref in _as_list(item.get("evidence")) if str(ref).strip()]
    if state not in OFFICIAL_STATES:
        _error(errors, f"{decision_id or '<sem id>'}: estado inválido {state!r}")
        return errors
    if "PENDENTE" in state and "VALIDADO" in state:
        _error(errors, f"{decision_id}: PENDENTE não pode ser apresentado como VALIDADO")
    if state in PENDING_STATES:
        if item.get("validated") is True:
            _error(errors, f"{decision_id}: estado pendente marcado como validado")
        if item.get("implemented") is True:
            _error(errors, f"{decision_id}: estado pendente marcado como implementado")
    if state == "IMPLEMENTADO / EM VALIDAÇÃO":
        if item.get("validated") is True:
            _error(errors, f"{decision_id}: IMPLEMENTADO não pode ser apresentado como VALIDADO")
        if item.get("implemented") is not True:
            _error(errors, f"{decision_id}: implementação sem marca consistente")
        if not evidence:
            _error(errors, f"{decision_id}: implementação sem evidência")
    if state == "VALIDADO":
        if item.get("validated") is not True or not evidence:
            _error(errors, f"{decision_id}: VALIDADO exige validated=true e evidência")
    if state == "SUBSTITUÍDO" and not str(item.get("superseded_by") or "").strip():
        _error(errors, f"{decision_id}: SUBSTITUÍDO sem substituto")
    if state == "DEPENDÊNCIA EXTERNA" and item.get("validated") is True:
        _error(errors, f"{decision_id}: dependência externa marcada como validada")
    return errors


def validate_adr_text(adr_id: str, text: str, status: str) -> list[str]:
    errors: list[str] = []
    if f"Status: {status}" not in text:
        _error(errors, f"{adr_id}: status {status} ausente no registro")
    for heading in ADR_HEADINGS:
        if heading not in text:
            _error(errors, f"{adr_id}: seção ausente {heading}")
    if status == "SUPERSEDED":
        marker = "Superseded by"
        after = text.split(marker, 1)[1] if marker in text else ""
        successor = after.strip().splitlines()[0].strip(" :#-") if after.strip() else ""
        if successor.lower() in {"", "nenhum", "nenhuma", "none", "-", "n/a"}:
            _error(errors, f"{adr_id}: SUPERSEDED sem substituto")
    if status not in ADR_STATUSES:
        _error(errors, f"{adr_id}: status de ADR inválido {status!r}")
    return errors


def validate_manifest(
    manifest: Mapping[str, Any],
    *,
    narrative: str,
    adr_texts: Mapping[str, str],
    existing_paths: set[str],
) -> list[str]:
    errors: list[str] = []
    if manifest.get("gate_id") != GATE_ID:
        _error(errors, "gate_id ausente ou divergente")
    period = manifest.get("period") if isinstance(manifest.get("period"), Mapping) else {}
    if period.get("start") != PERIOD_START or period.get("end") != PERIOD_END:
        _error(errors, "período 2026-09-15 a 2026-09-29 ausente")
    if PERIOD_START not in narrative or PERIOD_END not in narrative or GATE_ID not in narrative:
        _error(errors, "narrativa não declara período ou gate")
    if PRESERVED_CHECKPOINT not in narrative:
        _error(errors, "narrativa não preserva o Checkpoint de 2026-09-22")
    sources = _as_list(manifest.get("sources"))
    source_paths = {str(item.get("path")) for item in sources if isinstance(item, Mapping)}
    if not source_paths:
        _error(errors, "fontes não inventariadas")
    for required in REQUIRED_SOURCES:
        if required not in source_paths:
            _error(errors, f"fonte obrigatória fora do inventário: {required}")
        if required not in existing_paths:
            _error(errors, f"fonte obrigatória ausente no disco: {required}")
    decisions = [item for item in _as_list(manifest.get("decisions")) if isinstance(item, Mapping)]
    by_id: dict[str, Mapping[str, Any]] = {}
    for item in decisions:
        decision_id = str(item.get("id") or "")
        if not decision_id or decision_id in by_id:
            _error(errors, f"id de decisão inválido ou duplicado: {decision_id!r}")
            continue
        by_id[decision_id] = item
        errors.extend(validate_decision(item))
        if decision_id not in narrative or str(item.get("state") or "") not in narrative:
            _error(errors, f"{decision_id}: ausente da narrativa ou sem estado")
        for ref in _as_list(item.get("evidence")):
            if str(ref) not in existing_paths:
                _error(errors, f"{decision_id}: evidência ausente {ref}")
        successor = item.get("superseded_by")
        if successor and str(successor) not in by_id and str(successor) not in {d.get("id") for d in decisions}:
            _error(errors, f"{decision_id}: superseded_by desconhecido")
    for required in REQUIRED_DECISION_IDS:
        if required not in by_id:
            _error(errors, f"decisão estrutural ausente: {required}")
    for item in decisions:
        successor = str(item.get("superseded_by") or "")
        if successor and successor not in by_id:
            _error(errors, f"{item.get('id')}: substituto inexistente {successor}")
    gaps = [item for item in _as_list(manifest.get("gaps")) if isinstance(item, Mapping)]
    if not gaps:
        _error(errors, "lacunas não registradas")
    for gap in gaps:
        gap_id = str(gap.get("id") or "")
        state = str(gap.get("state") or "")
        if state not in {"UNVERIFIED", "NEEDS HUMAN RECONCILIATION"}:
            _error(errors, f"{gap_id}: lacuna com estado inválido {state!r}")
        if gap.get("validated") is True or gap.get("implemented") is True:
            _error(errors, f"{gap_id}: lacuna promovida a fato implementado ou validado")
        if gap_id and gap_id not in narrative:
            _error(errors, f"{gap_id}: lacuna ausente da narrativa")
    adrs = [item for item in _as_list(manifest.get("adrs")) if isinstance(item, Mapping)]
    adr_ids = [str(item.get("id") or "") for item in adrs]
    if adr_ids != list(REQUIRED_ADR_IDS):
        _error(errors, "registry de ADR incompleto ou fora de ordem")
    for item in adrs:
        adr_id = str(item.get("id") or "")
        status = str(item.get("status") or "")
        path = str(item.get("file") or "")
        if path not in existing_paths:
            _error(errors, f"{adr_id}: arquivo ausente {path}")
        text = adr_texts.get(adr_id, "")
        errors.extend(validate_adr_text(adr_id, text, status))
        if adr_id not in narrative:
            _error(errors, f"{adr_id}: ausente da narrativa")
    if ADR_README not in existing_paths:
        _error(errors, "docs/adr/README.md ausente")
    return errors


def validate_repository(root: Path | None = None) -> dict[str, Any]:
    base = _root(root)
    manifest = load_manifest(base)
    narrative = (base / NARRATIVE_PATH).read_text(encoding="utf-8")
    readme = (base / ADR_README).read_text(encoding="utf-8")
    adr_texts: dict[str, str] = {}
    existing = {MANIFEST_PATH, NARRATIVE_PATH, ADR_README}
    for item in manifest.get("adrs") or []:
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("file") or "")
        adr_id = str(item.get("id") or "")
        file_path = base / path
        if file_path.is_file():
            existing.add(path)
            adr_texts[adr_id] = file_path.read_text(encoding="utf-8")
    for source in manifest.get("sources") or []:
        if isinstance(source, Mapping):
            path = str(source.get("path") or "")
            if path and (base / path).is_file():
                existing.add(path)
    for ref in (
        *REQUIRED_SOURCES,
        PRESERVED_CHECKPOINT,
        "docs/aion/ADDING_CAPABILITIES.md",
        "docs/aion/AION_SKILL_PLUGIN_CERTIFICATION_V1.md",
        "docs/aion/AION_SPECIALIST_CERTIFICATION_V1.md",
        "docs/continuidade/AION_ENTITLEMENTS_2026-09-24.md",
        "atlasquant_aion_specialist_session.py",
        "test_atlasquant_aion_specialist_session.py",
        "atlasquant_aion_developer_engine.py",
        "test_atlasquant_aion_developer_engine.py",
        "atlasquant_aion_capabilities.py",
        "test_atlasquant_aion_capabilities.py",
        "atlasquant_release_guard.py",
    ):
        if (base / ref).is_file():
            existing.add(ref)
    errors = validate_manifest(
        manifest,
        narrative=narrative + "\n" + readme,
        adr_texts=adr_texts,
        existing_paths=existing,
    )
    return {
        "gate_id": GATE_ID,
        "ok": not errors,
        "errors": errors,
        "decision_count": len(manifest.get("decisions") or []),
        "adr_count": len(manifest.get("adrs") or []),
        "gap_count": len(manifest.get("gaps") or []),
        "source_count": len(manifest.get("sources") or []),
    }
