from atlasquant_aion_b2b_commercial_autonomy_contract_v1 import (
    evaluate_commercial_action,
)


def approved_envelope():
    return {
        "state": "APPROVED",
        "campaign_id": "CMP-001",
        "approved_by": "HUMAN_OWNER",
        "niche": "CLINICS",
        "allowed_channels": ["EMAIL", "WHATSAPP"],
        "business_hours": "08:00-18:00",
        "contact_rate_cap": 50,
        "followup_cap": 3,
        "approved_claims": ["DIAGNOSTIC", "AUTOMATION"],
        "approved_offers": ["DIAGNOSTIC", "CONTROLLED_PILOT"],
        "opt_out_enforced": True,
    }


def test_low_risk_outreach_can_be_eligible_inside_approved_envelope():
    result = evaluate_commercial_action(
        action="OUTREACH_SEND",
        envelope=approved_envelope(),
        contact_state="ELIGIBLE",
    )
    assert result["state"] == "ELIGIBLE"
    assert result["eligible"] is True
    assert result["external_action_executed"] is False


def test_owner_reserved_contract_commitment_is_blocked():
    result = evaluate_commercial_action(
        action="CONTRACT_COMMITMENT",
        envelope=approved_envelope(),
    )
    assert result["state"] == "BLOCKED"
    assert "HUMAN_OWNER_REQUIRED" in result["blockers"]
    assert result["requires_human_owner"] is True


def test_opt_out_blocks_outreach():
    result = evaluate_commercial_action(
        action="FOLLOWUP_SEND",
        envelope=approved_envelope(),
        contact_state="OPTED_OUT",
    )
    assert result["state"] == "BLOCKED"
    assert "CONTACT_NOT_ELIGIBLE" in result["blockers"]


def test_unapproved_envelope_fails_closed():
    env = approved_envelope()
    env["state"] = "DRAFT"
    result = evaluate_commercial_action(
        action="QUALIFICATION_DIALOGUE",
        envelope=env,
    )
    assert result["state"] == "BLOCKED"
    assert "CAMPAIGN_ENVELOPE_NOT_APPROVED" in result["blockers"]


def test_budget_boundary_blocks_action():
    result = evaluate_commercial_action(
        action="CAMPAIGN_ANALYTICS",
        envelope=approved_envelope(),
        within_budget=False,
    )
    assert result["state"] == "BLOCKED"
    assert "BUDGET_BOUNDARY_EXCEEDED" in result["blockers"]
