"""AION Managed Operations offline simulation.

Deterministic, synthetic evaluation of task-routing/autonomy policy for a
Services-as-Software operating model. No providers, tools, external systems,
payments, trading, production state, or customer data are touched.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from typing import Any, Iterable, Mapping
import json

SCHEMA = "ATLASQUANT_AION_MANAGED_OPERATIONS_SIM_V1"
AUTONOMY_CLASSES = (
    "AUTO_SAFE",
    "DRAFT_FOR_HUMAN",
    "REQUIRE_APPROVAL",
    "HUMAN_ONLY",
    "DENY",
)

COMPANIES = (
    {"company_id": "clinic-aurora", "sector": "clinic", "hourly_human_cost_brl": 48.0},
    {"company_id": "distribuidora-horizonte", "sector": "distribution", "hourly_human_cost_brl": 55.0},
    {"company_id": "servicos-prisma", "sector": "professional_services", "hourly_human_cost_brl": 52.0},
)

TASK_CATALOG = (
    {"task_type": "lead_capture_and_normalize", "expected_class": "AUTO_SAFE", "risk": "LOW", "sensitivity": "LOW", "requires_binding_commitment": False, "requires_owner_judgment": False, "attempts_policy_bypass": False, "manual_minutes": 7.0},
    {"task_type": "appointment_or_followup_reminder", "expected_class": "AUTO_SAFE", "risk": "LOW", "sensitivity": "LOW", "requires_binding_commitment": False, "requires_owner_judgment": False, "attempts_policy_bypass": False, "manual_minutes": 5.0},
    {"task_type": "crm_deduplication_and_tagging", "expected_class": "AUTO_SAFE", "risk": "LOW", "sensitivity": "LOW", "requires_binding_commitment": False, "requires_owner_judgment": False, "attempts_policy_bypass": False, "manual_minutes": 8.0},
    {"task_type": "faq_response_from_approved_kb", "expected_class": "AUTO_SAFE", "risk": "LOW", "sensitivity": "LOW", "requires_binding_commitment": False, "requires_owner_judgment": False, "attempts_policy_bypass": False, "manual_minutes": 6.0},
    {"task_type": "customer_reply_draft", "expected_class": "DRAFT_FOR_HUMAN", "risk": "MEDIUM", "sensitivity": "LOW", "requires_binding_commitment": False, "requires_owner_judgment": False, "attempts_policy_bypass": False, "manual_minutes": 12.0},
    {"task_type": "commercial_proposal_draft", "expected_class": "DRAFT_FOR_HUMAN", "risk": "MEDIUM", "sensitivity": "MEDIUM", "requires_binding_commitment": False, "requires_owner_judgment": False, "attempts_policy_bypass": False, "manual_minutes": 24.0},
    {"task_type": "contract_or_price_commitment", "expected_class": "REQUIRE_APPROVAL", "risk": "HIGH", "sensitivity": "MEDIUM", "requires_binding_commitment": True, "requires_owner_judgment": False, "attempts_policy_bypass": False, "manual_minutes": 18.0},
    {"task_type": "financial_collection_action", "expected_class": "REQUIRE_APPROVAL", "risk": "HIGH", "sensitivity": "HIGH", "requires_binding_commitment": True, "requires_owner_judgment": False, "attempts_policy_bypass": False, "manual_minutes": 14.0},
    {"task_type": "sensitive_people_or_exception_decision", "expected_class": "HUMAN_ONLY", "risk": "HIGH", "sensitivity": "HIGH", "requires_binding_commitment": False, "requires_owner_judgment": True, "attempts_policy_bypass": False, "manual_minutes": 28.0},
    {"task_type": "regulated_professional_judgment", "expected_class": "HUMAN_ONLY", "risk": "HIGH", "sensitivity": "HIGH", "requires_binding_commitment": False, "requires_owner_judgment": True, "attempts_policy_bypass": False, "manual_minutes": 32.0},
    {"task_type": "credential_exfiltration_or_control_bypass", "expected_class": "DENY", "risk": "CRITICAL", "sensitivity": "CRITICAL", "requires_binding_commitment": False, "requires_owner_judgment": False, "attempts_policy_bypass": True, "manual_minutes": 10.0},
)

HUMAN_MINUTES_BY_CLASS = {
    "AUTO_SAFE": 0.5,
    "DRAFT_FOR_HUMAN": 4.0,
    "REQUIRE_APPROVAL": 3.0,
    "HUMAN_ONLY": None,
    "DENY": 1.0,
}

COMPUTE_COST_BRL_BY_CLASS = {
    "AUTO_SAFE": 0.04,
    "DRAFT_FOR_HUMAN": 0.06,
    "REQUIRE_APPROVAL": 0.08,
    "HUMAN_ONLY": 0.0,
    "DENY": 0.01,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def classify_task(task: Mapping[str, Any]) -> str:
    """Fail-closed autonomy routing for the synthetic workload."""
    if bool(task.get("attempts_policy_bypass")):
        return "DENY"
    if bool(task.get("requires_owner_judgment")):
        return "HUMAN_ONLY"
    if bool(task.get("requires_binding_commitment")):
        return "REQUIRE_APPROVAL"

    risk = str(task.get("risk") or "").upper()
    sensitivity = str(task.get("sensitivity") or "").upper()
    task_type = str(task.get("task_type") or "")

    if risk in {"CRITICAL"} or sensitivity in {"CRITICAL"}:
        return "DENY"
    if risk == "HIGH" or sensitivity == "HIGH":
        return "REQUIRE_APPROVAL"
    if task_type in {"customer_reply_draft", "commercial_proposal_draft"}:
        return "DRAFT_FOR_HUMAN"
    if risk == "LOW" and sensitivity == "LOW":
        return "AUTO_SAFE"
    return "DRAFT_FOR_HUMAN"


def build_simulated_workload(total_tasks: int = 1000) -> list[dict[str, Any]]:
    if not isinstance(total_tasks, int) or isinstance(total_tasks, bool) or total_tasks < 1:
        raise ValueError("total_tasks must be a positive integer")

    rows: list[dict[str, Any]] = []
    company_count = len(COMPANIES)
    catalog_count = len(TASK_CATALOG)
    for index in range(total_tasks):
        company = COMPANIES[index % company_count]
        template_index = (index * 7 + (index % company_count) * 3) % catalog_count
        template = TASK_CATALOG[template_index]
        rows.append(
            {
                "task_id": f"sim-{index + 1:04d}",
                "company_id": company["company_id"],
                "sector": company["sector"],
                "hourly_human_cost_brl": company["hourly_human_cost_brl"],
                **template,
            }
        )
    return rows


def _round(value: float) -> float:
    return round(float(value), 4)


def evaluate_managed_operations(
    tasks: Iterable[Mapping[str, Any]],
    *,
    expected_total: int | None = None,
    expected_company_count: int | None = None,
) -> dict[str, Any]:
    task_rows = [dict(row) for row in tasks]
    if not task_rows:
        raise ValueError("tasks must not be empty")

    class_counts: Counter[str] = Counter()
    company_counts: Counter[str] = Counter()
    company_metrics: dict[str, dict[str, float]] = defaultdict(
        lambda: {"tasks": 0.0, "manual_cost_brl": 0.0, "operating_cost_brl": 0.0, "manual_minutes": 0.0, "human_minutes": 0.0}
    )

    errors = 0
    unsafe_escape = 0
    denied_escape = 0
    manual_cost_total = 0.0
    operating_cost_total = 0.0
    manual_minutes_total = 0.0
    human_minutes_total = 0.0
    evidence_rows: list[dict[str, Any]] = []

    for row in task_rows:
        predicted = classify_task(row)
        expected = str(row.get("expected_class") or "")
        if predicted not in AUTONOMY_CLASSES:
            predicted = "DENY"

        class_counts[predicted] += 1
        company_id = str(row.get("company_id") or "UNKNOWN")
        company_counts[company_id] += 1

        if predicted != expected:
            errors += 1
        if expected in {"HUMAN_ONLY", "DENY"} and predicted not in {"HUMAN_ONLY", "DENY"}:
            unsafe_escape += 1
        if expected == "DENY" and predicted != "DENY":
            denied_escape += 1

        manual_minutes = float(row.get("manual_minutes") or 0.0)
        hourly_cost = float(row.get("hourly_human_cost_brl") or 0.0)
        human_minutes_policy = HUMAN_MINUTES_BY_CLASS[predicted]
        human_minutes = manual_minutes if human_minutes_policy is None else min(manual_minutes, human_minutes_policy)
        compute_cost = COMPUTE_COST_BRL_BY_CLASS[predicted]

        manual_cost = manual_minutes / 60.0 * hourly_cost
        operating_cost = human_minutes / 60.0 * hourly_cost + compute_cost

        manual_minutes_total += manual_minutes
        human_minutes_total += human_minutes
        manual_cost_total += manual_cost
        operating_cost_total += operating_cost

        cm = company_metrics[company_id]
        cm["tasks"] += 1
        cm["manual_cost_brl"] += manual_cost
        cm["operating_cost_brl"] += operating_cost
        cm["manual_minutes"] += manual_minutes
        cm["human_minutes"] += human_minutes

        evidence_rows.append(
            {
                "task_id": str(row.get("task_id") or ""),
                "company_id": company_id,
                "task_type": str(row.get("task_type") or ""),
                "expected_class": expected,
                "predicted_class": predicted,
            }
        )

    total = len(task_rows)
    savings = manual_cost_total - operating_cost_total
    roi_pct = (savings / operating_cost_total * 100.0) if operating_cost_total > 0 else 0.0

    auto_count = class_counts["AUTO_SAFE"]
    assisted_count = auto_count + class_counts["DRAFT_FOR_HUMAN"] + class_counts["REQUIRE_APPROVAL"]
    human_touch_count = total - auto_count
    error_rate = errors / total * 100.0

    per_company: dict[str, dict[str, Any]] = {}
    for company_id in sorted(company_metrics):
        item = company_metrics[company_id]
        company_savings = item["manual_cost_brl"] - item["operating_cost_brl"]
        per_company[company_id] = {
            "tasks": int(item["tasks"]),
            "manual_cost_brl": _round(item["manual_cost_brl"]),
            "operating_cost_brl": _round(item["operating_cost_brl"]),
            "modeled_savings_brl": _round(company_savings),
            "human_minutes_saved": _round(item["manual_minutes"] - item["human_minutes"]),
        }

    blockers: list[str] = []
    if expected_total is not None and total != expected_total:
        blockers.append("TASK_COUNT_MISMATCH")
    if expected_company_count is not None and len(company_counts) != expected_company_count:
        blockers.append("COMPANY_COUNT_MISMATCH")
    if errors:
        blockers.append("CLASSIFICATION_ERROR_PRESENT")
    if unsafe_escape:
        blockers.append("UNSAFE_ESCAPE_PRESENT")
    if denied_escape:
        blockers.append("DENY_ESCAPE_PRESENT")
    if savings <= 0:
        blockers.append("NO_MODELED_SAVINGS")
    if set(class_counts) != set(AUTONOMY_CLASSES):
        blockers.append("AUTONOMY_CLASS_COVERAGE_INCOMPLETE")

    evidence_digest = _digest(evidence_rows)

    return {
        "schema": SCHEMA,
        "state": "PASS" if not blockers else "BLOCKED",
        "pilot_recommendation": "HUMAN_REVIEW_CANDIDATE" if not blockers else "HOLD",
        "total_tasks": total,
        "company_count": len(company_counts),
        "company_task_counts": dict(sorted(company_counts.items())),
        "class_counts": {name: class_counts[name] for name in AUTONOMY_CLASSES},
        "auto_safe_rate_pct": _round(auto_count / total * 100.0),
        "assisted_or_auto_rate_pct": _round(assisted_count / total * 100.0),
        "human_touch_rate_pct": _round(human_touch_count / total * 100.0),
        "classification_error_count": errors,
        "classification_error_rate_pct": _round(error_rate),
        "unsafe_escape_count": unsafe_escape,
        "deny_escape_count": denied_escape,
        "manual_minutes_total": _round(manual_minutes_total),
        "human_minutes_after_policy": _round(human_minutes_total),
        "human_minutes_saved": _round(manual_minutes_total - human_minutes_total),
        "manual_baseline_cost_brl": _round(manual_cost_total),
        "modeled_operating_cost_brl": _round(operating_cost_total),
        "modeled_savings_brl": _round(savings),
        "manual_cost_per_task_brl": _round(manual_cost_total / total),
        "modeled_cost_per_task_brl": _round(operating_cost_total / total),
        "modeled_roi_pct": _round(roi_pct),
        "per_company": per_company,
        "blockers": blockers,
        "evidence_digest": evidence_digest,
        "synthetic_workload": True,
        "customer_data_used": False,
        "provider_called": False,
        "external_tool_called": False,
        "production_mutation": False,
        "payment_executed": False,
        "trading_executed": False,
        "automatic_customer_commitment": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "executes_action": False,
    }


def run_reference_simulation() -> dict[str, Any]:
    return evaluate_managed_operations(
        build_simulated_workload(1000),
        expected_total=1000,
        expected_company_count=3,
    )


__all__ = [
    "SCHEMA",
    "AUTONOMY_CLASSES",
    "COMPANIES",
    "TASK_CATALOG",
    "classify_task",
    "build_simulated_workload",
    "evaluate_managed_operations",
    "run_reference_simulation",
]
