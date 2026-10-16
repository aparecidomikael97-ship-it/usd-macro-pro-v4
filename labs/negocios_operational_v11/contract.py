"""AtlasQuant Negocios V1.1 - OFFLINE, PURE, SYNTHETIC specification oracle.

NOT an application integration, authorizer, financial verifier, CRM backend, or LGPD proof.
No network, IO, persistence, data import, message sending, or payment execution.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

DISCLAIMER = (
    "Nosso compromisso é organizar processos, registros e acompanhamento de "
    "oportunidades, com entregas e indicadores definidos no escopo. Isso pode "
    "contribuir para um atendimento melhor, mas não garantimos aumento de "
    "vendas, faturamento ou lucro."
)

STAGES = ("CONSULTA", "LEAD_NAO_QUALIFICADO", "LEAD_QUALIFICADO", "OPORTUNIDADE")
STOCK_STATES = ("NAO_VERIFICADO", "DISPONIVEL", "RESERVADO", "INDISPONIVEL", "NAO_APLICAVEL")
PAYMENT_STATES = ("NAO_VERIFICADO", "PENDENTE", "PARCIAL", "CONFIRMADO", "CONTESTADO", "NAO_APLICAVEL")
OPEN_STATUSES = ("ABERTO", "PAUSADO")
ALL_STATUSES = (*OPEN_STATUSES, "GANHO", "PERDIDO", "CONCLUIDO")
CHECK_ITEMS = (
    "finalidade_e_base", "minimizacao", "acesso_autorizado",
    "preferencias_e_direitos", "retencao_e_correcao", "incidentes_escalados",
)
BLOCKED_CAPABILITIES = frozenset({"SEND", "PAY", "CHARGE", "RESERVE_STOCK", "IMPORT_PII", "DEPLOY", "ENABLE_WORKER"})


class ContractError(ValueError):
    """Typed, non-sensitive local validation error."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _aware(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ContractError("TIMESTAMP_REQUIRED")
    try:
        x = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ContractError("TIMESTAMP_INVALID") from None
    if x.tzinfo is None or x.utcoffset() is None:
        raise ContractError("TIMESTAMP_TIMEZONE_REQUIRED")
    return x


def _fields(obj: Mapping[str, Any], *required: str) -> None:
    if not isinstance(obj, Mapping) or any(not obj.get(k) for k in required):
        raise ContractError("FIELDS_REQUIRED")


def _provenance(obj: Mapping[str, Any], category: str, *, now: datetime) -> None:
    _fields(obj, "checked_by", "checked_at", "source_ref")
    stamp = _aware(obj["checked_at"])
    if stamp > now:
        raise ContractError(f"{category}_FUTURE_PROOF")
    if not isinstance(obj["source_ref"], str) or not obj["source_ref"].startswith("SIM-"):
        # Deliberate test-only source prefix; real evidence evaluation NOT here.
        raise ContractError(f"{category}_SYNTHETIC_SOURCE_REQUIRED")


def review_record(record: Mapping[str, Any], *, now: str, review_cutoff: str) -> dict[str, Any]:
    """Return local warnings only; no state mutations, no real authorization.

    'now' and 'review_cutoff' are explicit; caller determines timezone/business day.
    Flagging overdue is NOT permission to contact a person.
    """
    _fields(record, "tenant_id", "case_id", "stage", "state", "updated_at")
    if record["stage"] not in STAGES:
        raise ContractError("STAGE_INVALID")
    if record["state"] not in ALL_STATUSES:
        raise ContractError("STATE_INVALID")
    current, cutoff, updated = _aware(now), _aware(review_cutoff), _aware(record["updated_at"])
    if updated > current:
        raise ContractError("UPDATED_IN_FUTURE")
    if cutoff > current:
        raise ContractError("CUTOFF_IN_FUTURE")
    issues: set[str] = set()
    active = record["state"] in OPEN_STATUSES
    if active:
        if not record.get("owner_id"):
            issues.add("OWNER_MISSING")
        if not record.get("next_action") and not record.get("pause_reason"):
            issues.add("NEXT_ACTION_OR_PAUSE_MISSING")
        if record.get("next_action") and not record.get("next_due_at"):
            issues.add("NEXT_DUE_MISSING")
        if record.get("next_due_at") and _aware(record["next_due_at"]) < current:
            issues.add("FOLLOW_UP_OVERDUE")
        if updated < cutoff:
            issues.add("DAILY_REVIEW_REQUIRED")
    if record["stage"] in ("LEAD_QUALIFICADO", "OPORTUNIDADE"):
        qualification = record.get("qualification") or {}
        if any(qualification.get(k) is not True for k in ("need_identified", "can_serve", "interest_to_proceed")):
            issues.add("QUALIFICATION_UNVERIFIED")
        if record["stage"] == "OPORTUNIDADE" and not qualification.get("decision_path_documented"):
            issues.add("OPPORTUNITY_DECISION_UNVERIFIED")
    stock = record.get("stock") or {"state": "NAO_VERIFICADO"}
    payment = record.get("payment") or {"state": "NAO_VERIFICADO"}
    if stock.get("state") not in STOCK_STATES:
        raise ContractError("STOCK_STATE_INVALID")
    if payment.get("state") not in PAYMENT_STATES:
        raise ContractError("PAYMENT_STATE_INVALID")
    if stock["state"] == "NAO_APLICAVEL" and record.get("requires_stock") is True:
        issues.add("STOCK_APPLICABILITY_CONFLICT")
    if stock["state"] in ("DISPONIVEL", "RESERVADO", "INDISPONIVEL"):
        try:
            _provenance(stock, "STOCK", now=current)
        except ContractError:
            issues.add("STOCK_EVIDENCE_MISSING")
    if stock["state"] in ("DISPONIVEL", "RESERVADO"):
        requested, observed = record.get("requested_qty"), stock.get("observed_qty")
        if not isinstance(requested, int) or isinstance(requested, bool) or requested <= 0:
            issues.add("STOCK_REQUESTED_QUANTITY_MISSING")
        if not isinstance(observed, int) or isinstance(observed, bool) or observed < 0:
            issues.add("STOCK_OBSERVED_QUANTITY_MISSING")
        if (type(requested) is int and type(observed) is int
                and requested > 0 and 0 <= observed < requested):
            issues.add("STOCK_INSUFFICIENT_FOR_REQUEST")
        if stock["state"] == "RESERVADO" and not stock.get("reservation_ref"):
            issues.add("STOCK_RESERVATION_NOT_DOCUMENTED")
    if payment["state"] in ("PARCIAL", "CONFIRMADO", "CONTESTADO"):
        try:
            _provenance(payment, "PAYMENT", now=current)
        except ContractError:
            issues.add("PAYMENT_EVIDENCE_MISSING")
        if payment["state"] in ("PARCIAL", "CONFIRMADO"):
            amount_due, amount_received = payment.get("amount_due_cents"), payment.get("amount_received_cents")
            if (type(amount_due) is not int or amount_due <= 0
                    or type(amount_received) is not int or amount_received < 0):
                issues.add("PAYMENT_AMOUNT_UNVERIFIED")
            elif payment["state"] == "CONFIRMADO" and amount_received < amount_due:
                issues.add("PAYMENT_CONFIRMED_BUT_AMOUNT_SHORT")
            elif payment["state"] == "PARCIAL" and amount_received >= amount_due:
                issues.add("PAYMENT_PARTIAL_BUT_AMOUNT_FULL")
        # Even a synthetically complete proof is not independent bank confirmation.
        issues.add("FINANCIAL_RECONCILIATION_NOT_VERIFIED_EXTERNALLY")
    if stock["state"] == "NAO_VERIFICADO":
        issues.add("STOCK_NOT_VERIFIED")
    if payment["state"] == "NAO_VERIFICADO":
        issues.add("PAYMENT_NOT_VERIFIED")
    if record.get("contact_preference") in ("RECUSOU", "DESCONHECIDA", None):
        issues.add("OUTBOUND_CONTACT_NOT_AUTHORIZED")
    for k in ("purpose_ref", "legal_basis_ref", "retention_policy_ref"):
        if not record.get(k):
            issues.add("PRIVACY_" + k.upper() + "_MISSING")
    checklist = record.get("privacy_checklist") or {}
    if any(checklist.get(k) is not True for k in CHECK_ITEMS):
        issues.add("PRIVACY_CHECKLIST_PENDING")
    return {
        "schema": "AQ_NEGOCIOS_V11_SYNTHETIC_ONLY",
        "case_id": record["case_id"],
        "tenant_id": record["tenant_id"],
        "issues": sorted(issues),
        "external_effects_enabled": False,
        "lgpd_compliance_certified": False,
        "stock_availability_proven": False,
        "bank_receipt_proven": False,
        "send_approved": False,
    }


def advance_stage(current: Mapping[str, Any], *, target: str, actor_tenant: str) -> str:
    _fields(current, "tenant_id", "stage")
    if current["tenant_id"] != actor_tenant:
        raise ContractError("TENANT_ACCESS_DENIED")
    if target not in STAGES:
        raise ContractError("STAGE_INVALID")
    if STAGES.index(target) > STAGES.index(current["stage"]) + 1:
        raise ContractError("STAGE_SKIP_REVIEW_REQUIRED")
    if STAGES.index(target) < STAGES.index(current["stage"]):
        raise ContractError("STAGE_REGRESSION_REVIEW_REQUIRED")
    if target in ("LEAD_QUALIFICADO", "OPORTUNIDADE"):
        q = current.get("qualification") or {}
        if not all(q.get(k) is True for k in ("need_identified", "can_serve", "interest_to_proceed")):
            raise ContractError("QUALIFICATION_UNVERIFIED")
    if target == "OPORTUNIDADE":
        q = current.get("qualification") or {}
        if not q.get("decision_path_documented") or not current.get("owner_id") or not current.get("next_action"):
            raise ContractError("OPPORTUNITY_REQUIRED_DATA_MISSING")
    return target


def render_proposal(*, scope: str, price_label: str) -> str:
    """Draft only. Does not imply ability to issue contracts or send proposals."""
    if not scope.strip() or not price_label.strip():
        raise ContractError("PROPOSAL_SCOPE_OR_PRICE_REQUIRED")
    return ("RASCUNHO DIDATICO — NAO HOMOLOGADO / NAO ENVIADO\nREVISAO HUMANA OBRIGATORIA: textos livres podem conter promessas enganosas.\n\n"
            + scope.strip() + "\nValor (estimativa): " + price_label.strip()
            + "\n\n" + DISCLAIMER + "\n")


def privacy_summary(checklist: Mapping[str, Any]) -> str:
    if not isinstance(checklist, Mapping):
        raise ContractError("PRIVACY_CHECKLIST_INVALID")
    return "REVISAO_HUMANA_NECESSARIA"  # Never issue legal compliance certificates.


def request_external_action(action: str) -> None:
    """No external effects, even in apparent positive simulated states."""
    if not isinstance(action, str) or action.upper() in BLOCKED_CAPABILITIES:
        raise ContractError("HARD_NO_GO_EXTERNAL_ACTION")
    raise ContractError("OFFLINE_SPEC_ONLY")
