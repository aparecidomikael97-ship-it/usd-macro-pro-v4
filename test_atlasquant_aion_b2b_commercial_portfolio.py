from atlasquant_aion_b2b_commercial_golden_path import SCHEMA as JOURNEY_SCHEMA
from atlasquant_aion_b2b_commercial_portfolio import SCHEMA, build_commercial_portfolio

SCOPE = {"owner_id": "owner-1", "workspace_id": "admin-business"}


def journey(state, stage, action, gaps=()):
    return {
        "schema": JOURNEY_SCHEMA,
        "state": state,
        "current_stage": stage,
        "current_stage_label": stage or "Lead",
        "next_human_action": action,
        "lineage_gaps": list(gaps),
        "evidence_digest": "sha256:" + (stage or "empty"),
        "read_only": True,
        "grants_authority": False,
        "executes_action": False,
        "automatic_outreach": False,
        "automatic_billing": False,
    }


def admin(
    *,
    package="PROFISSIONAL",
    subscription_state="ACTIVE",
    payment_state="PAID",
    value_state="VALUE_CONFIRMED",
    observed_roi_pct=120.0,
    health_state="HEALTHY",
    health_score=90.0,
    capacity_utilization_pct=60.0,
    seed="a",
):
    return {
        "package": package,
        "subscription_state": subscription_state,
        "payment_state": payment_state,
        "value_state": value_state,
        "observed_roi_pct": observed_roi_pct,
        "health_state": health_state,
        "health_score": health_score,
        "capacity_utilization_pct": capacity_utilization_pct,
        "source_evidence_digest": "sha256:" + seed * 64,
    }


def test_portfolio_prioritizes_blocked_and_gap_cases_without_tenant_data():
    result = build_commercial_portfolio(
        portfolio_scope=SCOPE,
        companies=[
            {"company_ref": "C-003", "journey": journey("READY", "recurring_customer", "MONITORAR")},
            {"company_ref": "C-001", "journey": journey("BLOCKED", "proposal", "REVISAR")},
            {"company_ref": "C-002", "journey": journey("READY_WITH_GAPS", "pilot_value", "REVISAR_VALOR", ("diagnostic",))},
        ],
    )
    assert result["schema"] == SCHEMA
    assert result["state"] == "READY"
    assert result["company_count"] == 3
    assert [x["company_ref"] for x in result["attention_queue"]] == ["C-001", "C-002", "C-003"]
    assert result["state_counts"]["BLOCKED"] == 1
    assert result["stage_counts"]["proposal"] == 1
    assert result["package_counts"]["UNASSIGNED"] == 3
    assert result["admin_summary_coverage_count"] == 0
    assert result["tenant_identity_exposed"] is False
    assert result["contact_data_exposed"] is False
    assert result["raw_payment_data_exposed"] is False
    assert result["crm_write"] is False
    assert result["executes_action"] is False


def test_admin_summary_adds_package_roi_health_capacity_and_payment_signals_only():
    result = build_commercial_portfolio(
        portfolio_scope=SCOPE,
        companies=[
            {
                "company_ref": "C-001",
                "journey": journey("READY", "recurring_customer", "MONITORAR"),
                "admin_summary": admin(seed="a"),
            },
            {
                "company_ref": "C-002",
                "journey": journey("READY", "recurring_customer", "REVISAR"),
                "admin_summary": admin(
                    package="COMPLETO",
                    payment_state="OVERDUE",
                    value_state="VALUE_AT_RISK",
                    observed_roi_pct=12.5,
                    health_state="REMEDIATION",
                    health_score=58,
                    capacity_utilization_pct=95,
                    seed="b",
                ),
            },
        ],
    )
    assert result["state"] == "READY"
    assert result["admin_summary_coverage_count"] == 2
    assert result["package_counts"]["PROFISSIONAL"] == 1
    assert result["package_counts"]["COMPLETO"] == 1
    assert result["payment_counts"]["OVERDUE"] == 1
    assert result["value_state_counts"]["VALUE_AT_RISK"] == 1
    assert result["health_state_counts"]["REMEDIATION"] == 1
    assert result["capacity_state_counts"]["PRESSURE"] == 1
    assert result["delinquency_counts"]["OVERDUE"] == 1

    queue = result["attention_queue"]
    assert [row["company_ref"] for row in queue] == ["C-002", "C-001"]
    risky = queue[0]
    assert risky["package"] == "COMPLETO"
    assert risky["subscription_state"] == "ACTIVE"
    assert risky["payment_state"] == "OVERDUE"
    assert risky["delinquency_signal"] == "OVERDUE"
    assert risky["observed_roi_pct"] == 12.5
    assert risky["health_score"] == 58.0
    assert risky["capacity_utilization_pct"] == 95.0
    assert risky["capacity_state"] == "PRESSURE"
    assert risky["admin_attention_score"] > 0
    assert set(risky["admin_attention_reasons"]) == {
        "PAYMENT_OVERDUE",
        "CAPACITY_PRESSURE",
        "VALUE_AT_RISK",
        "REMEDIATION",
    }


def test_capacity_summary_uses_bounded_read_only_thresholds():
    result = build_commercial_portfolio(
        portfolio_scope=SCOPE,
        companies=[
            {
                "company_ref": "C-001",
                "journey": journey("READY", "managed_service", "MONITORAR"),
                "admin_summary": admin(capacity_utilization_pct=69.99, seed="a"),
            },
            {
                "company_ref": "C-002",
                "journey": journey("READY", "managed_service", "MONITORAR"),
                "admin_summary": admin(capacity_utilization_pct=70, seed="b"),
            },
            {
                "company_ref": "C-003",
                "journey": journey("READY", "managed_service", "MONITORAR"),
                "admin_summary": admin(capacity_utilization_pct=90, seed="c"),
            },
        ],
    )
    by_ref = {row["company_ref"]: row for row in result["attention_queue"]}
    assert by_ref["C-001"]["capacity_state"] == "NORMAL"
    assert by_ref["C-002"]["capacity_state"] == "WATCH"
    assert by_ref["C-003"]["capacity_state"] == "PRESSURE"
    assert result["capacity_state_counts"] == {
        "NORMAL": 1,
        "WATCH": 1,
        "PRESSURE": 1,
        "UNKNOWN": 0,
    }
    assert result["automatic_quota_change"] is False


def test_admin_summary_rejects_extra_fields_to_prevent_pii_or_raw_payment_leak():
    unsafe = admin(seed="d")
    unsafe["email"] = "customer@example.com"
    unsafe["amount_due_brl"] = 5000
    result = build_commercial_portfolio(
        portfolio_scope=SCOPE,
        companies=[
            {
                "company_ref": "C-001",
                "journey": journey("READY", "recurring_customer", "MONITORAR"),
                "admin_summary": unsafe,
            }
        ],
    )
    assert result["state"] == "BLOCKED"
    assert result["company_count"] == 0
    blocker = " ".join(result["blockers"])
    assert "ADMIN_SUMMARY_FIELD_UNSAFE" in blocker
    assert "email" in blocker
    assert "amount_due_brl" in blocker
    assert result["raw_customer_data_exposed"] is False
    assert result["raw_payment_data_exposed"] is False
    assert result["payment_amount_exposed"] is False
    assert result["banking_data_exposed"] is False


def test_invalid_admin_states_or_unproven_summary_fail_closed():
    bad = admin(seed="e")
    bad["package"] = "ENTERPRISE"
    bad["payment_state"] = "CHARGEBACK"
    bad["health_score"] = 101
    bad["capacity_utilization_pct"] = -1
    bad["source_evidence_digest"] = "not-a-digest"
    result = build_commercial_portfolio(
        portfolio_scope=SCOPE,
        companies=[
            {
                "company_ref": "C-001",
                "journey": journey("READY", "managed_service", "REVISAR"),
                "admin_summary": bad,
            }
        ],
    )
    assert result["state"] == "BLOCKED"
    assert result["company_count"] == 0
    joined = " ".join(result["blockers"])
    assert "ADMIN_PACKAGE_INVALID" in joined
    assert "ADMIN_PAYMENT_STATE_INVALID" in joined
    assert "ADMIN_HEALTH_SCORE_INVALID" in joined
    assert "ADMIN_CAPACITY_UTILIZATION_INVALID" in joined
    assert "ADMIN_EVIDENCE_DIGEST_REQUIRED" in joined


def test_payment_signal_never_exposes_amount_and_preserves_no_billing_authority():
    result = build_commercial_portfolio(
        portfolio_scope=SCOPE,
        companies=[
            {
                "company_ref": "C-001",
                "journey": journey("READY", "customer_portal", "ACOMPANHAR"),
                "admin_summary": admin(
                    subscription_state="PAUSED",
                    payment_state="DUE",
                    seed="f",
                ),
            }
        ],
    )
    row = result["attention_queue"][0]
    assert row["subscription_state"] == "PAUSED"
    assert row["payment_state"] == "DUE"
    assert row["delinquency_signal"] == "DUE"
    assert "amount_due_brl" not in row
    assert result["automatic_billing"] is False
    assert result["production_mutation"] is False
    assert result["grants_authority"] is False
    assert result["executes_action"] is False


def test_duplicate_company_ref_blocks_portfolio():
    result = build_commercial_portfolio(
        portfolio_scope=SCOPE,
        companies=[
            {"company_ref": "C-001", "journey": journey("READY", "proposal", "REVISAR")},
            {"company_ref": "C-001", "journey": journey("READY", "pilot_value", "REVISAR")},
        ],
    )
    assert result["state"] == "BLOCKED"
    assert any(x.startswith("COMPANY_REF_DUPLICATE") for x in result["blockers"])


def test_unsafe_journey_is_rejected_instead_of_entering_queue():
    bad = journey("READY", "proposal", "REVISAR")
    bad["automatic_billing"] = True
    result = build_commercial_portfolio(
        portfolio_scope=SCOPE,
        companies=[{"company_ref": "C-001", "journey": bad}],
    )
    assert result["state"] == "BLOCKED"
    assert result["company_count"] == 0
    assert any("JOURNEY_AUTOMATION_UNSAFE:automatic_billing" in x for x in result["blockers"])


def test_invalid_admin_scope_is_fail_closed():
    result = build_commercial_portfolio(
        portfolio_scope={"owner_id": "", "workspace_id": "admin-business"},
        companies=[],
    )
    assert result["state"] == "BLOCKED"
    assert "PORTFOLIO_SCOPE_INVALID" in result["blockers"]
    assert result["executes_action"] is False
