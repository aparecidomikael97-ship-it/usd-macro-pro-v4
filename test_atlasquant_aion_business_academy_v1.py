from atlasquant_aion_business_academy_v1 import (
    academy_action_policy,
    lesson_progress,
)


def test_professor_mode_blocks_live_outreach():
    result = academy_action_policy(mode="PROFESSOR", action="OUTREACH_SEND")
    assert result["state"] == "BLOCKED"
    assert "LIVE_ACTION_BLOCKED_IN_LEARNING_MODE" in result["blockers"]
    assert result["executes_action"] is False


def test_guided_practice_blocks_crm_write():
    result = academy_action_policy(mode="GUIDED_PRACTICE", action="CRM_WRITE")
    assert result["state"] == "BLOCKED"


def test_understanding_plus_practice_completes_lesson():
    result = lesson_progress(
        prior_state="PRACTICE_READY",
        demonstrated_understanding=True,
        practice_passed=True,
    )
    assert result["state"] == "UNDERSTOOD"


def test_clicks_alone_do_not_complete():
    result = lesson_progress(
        prior_state="IN_PROGRESS",
        demonstrated_understanding=False,
        practice_passed=False,
    )
    assert result["state"] == "REVIEW_RECOMMENDED"
    assert result["clicks_only_do_not_complete"] is True
