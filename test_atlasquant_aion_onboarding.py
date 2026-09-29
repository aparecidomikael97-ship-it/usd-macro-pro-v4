"""Onboarding V1 is a pure contract. It must not execute or widen access."""
from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
)
from atlasquant_aion_onboarding import (
    BLOCKED,
    COMPLETED,
    STALE,
    assess_onboarding,
    complete_onboarding_step,
    onboarding_catalog_problems,
    onboarding_digest,
    resume_onboarding,
    validate_step_graph,
)
from atlasquant_aion_tenant import PERSONAL_SCOPE


NOW = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
UPDATED = "2026-09-29T00:00:00+00:00"
SECRET = "super-secret-value"


def _context(role="USER", mode="BEGINNER", **extra):
    payload = {
        "subject_ref": "subject.one",
        "role": role,
        "experience_mode": mode,
        "updated_at": UPDATED,
    }
    payload.update(extra)
    return payload


def _entitlement(subject="subject.one", **window):
    item = new_entitlement_request(
        subject,
        scope=PERSONAL_SCOPE,
        created_at="2026-09-01T00:00:00+00:00",
        **window,
    )
    item = approve_entitlement_request(item, {"role": "ADMIN"})
    return mark_entitlement_from_provider_evidence(item, {
        "confirmed": True,
        "provider": "registry",
        "external_id": "ext-1",
    })


def _step(report, step_id):
    return next(row for row in report["steps"] if row["step_id"] == step_id)


def _walk(payload, steps):
    progress = None
    report = None
    for step_id in steps:
        report = complete_onboarding_step(payload, progress, step_id, now=NOW)
        progress = report
    return report


class OnboardingContractTests(unittest.TestCase):
    def test_catalog_has_no_duplicate_missing_prerequisite_or_cycle(self):
        self.assertEqual(onboarding_catalog_problems(), ())
        self.assertIn("UNKNOWN_PREREQUISITE", validate_step_graph([
            {"step_id": "a", "prerequisites": ["missing"]},
        ]))
        self.assertIn("CIRCULAR_DEPENDENCY", validate_step_graph([
            {"step_id": "a", "prerequisites": ["b"]},
            {"step_id": "b", "prerequisites": ["a"]},
        ]))
        self.assertIn("DUPLICATE_STEP_ID", validate_step_graph([
            {"step_id": "a", "prerequisites": []},
            {"step_id": "a", "prerequisites": []},
        ]))

    def test_admin_beginner_and_advanced_do_not_gain_privilege(self):
        beginner = assess_onboarding(_context("ADMIN", "BEGINNER"), now=NOW)
        advanced = assess_onboarding(_context("ADMIN", "ADVANCED"), now=NOW)
        self.assertTrue(_step(beginner, "admin_beginner_orientation")["required"])
        self.assertFalse(_step(advanced, "admin_beginner_orientation")["required"])
        self.assertNotEqual(beginner["state"], COMPLETED)
        self.assertNotEqual(advanced["state"], COMPLETED)
        self.assertEqual(_step(advanced, "operational_integration_review")["evidence_status"], "UNKNOWN")
        for report in (beginner, advanced):
            self.assertTrue(report["admin"])
            self.assertFalse(report["real_trading_enabled"])
            self.assertTrue(all(item["widens_permission"] is False for item in report["recommendations"]))
            self.assertLessEqual(len(report["recommendations"]), 3)

    def test_user_without_entitlement_is_not_completed(self):
        report = assess_onboarding(_context("USER"), now=NOW)
        row = _step(report, "personal_entitlement_confirmed")
        self.assertNotEqual(row["state"], COMPLETED)
        self.assertEqual(row["evidence_status"], "UNKNOWN")
        self.assertEqual(row["blocked_reason"], "ENTITLEMENT_ABSENT")
        self.assertNotIn("personal_entitlement_confirmed", report["completed_step_ids"])
        self.assertEqual(_step(report, "payment_evidence_confirmed")["evidence_status"], "UNKNOWN")

    def test_confirmed_entitlement_does_not_prove_payment(self):
        report = assess_onboarding(
            _context("USER", entitlements=[_entitlement()]),
            now=NOW,
        )
        self.assertEqual(_step(report, "personal_entitlement_confirmed")["evidence_status"], "CONFIRMED")
        self.assertNotEqual(_step(report, "payment_evidence_confirmed")["evidence_status"], "CONFIRMED")
        self.assertFalse(report["payment_inferred_from_entitlement"])
        self.assertNotIn("payment_evidence_confirmed", report["completed_step_ids"])

    def test_expired_or_invalid_entitlement_is_not_effective(self):
        expired = assess_onboarding(
            _context("USER", entitlements=[_entitlement(expires_at="2026-09-02T00:00:00+00:00")]),
            now=NOW,
        )
        self.assertEqual(
            _step(expired, "personal_entitlement_confirmed")["blocked_reason"],
            "ENTITLEMENT_NOT_EFFECTIVE",
        )
        invalid = assess_onboarding(
            _context("USER", entitlements=[{"status": "ACTIVE_CONFIRMED"}]),
            now=NOW,
        )
        self.assertNotEqual(
            _step(invalid, "personal_entitlement_confirmed")["evidence_status"],
            "CONFIRMED",
        )

    def test_sales_trail_excludes_admin_steps(self):
        report = assess_onboarding(_context("SALES", "BEGINNER"), now=NOW)
        ids = {row["step_id"] for row in report["steps"]}
        self.assertIn("sales_orientation", ids)
        self.assertNotIn("admin_guardian_review", ids)
        self.assertFalse(report["admin"])
        self.assertFalse(report["real_trading_enabled"])

    def test_missing_and_invalid_role_fail_closed(self):
        missing = assess_onboarding({"experience_mode": "BEGINNER", "subject_ref": "subject.one"}, now=NOW)
        blank = assess_onboarding(_context(role=""), now=NOW)
        invalid = assess_onboarding(_context(role="OWNER"), now=NOW)
        self.assertEqual(missing["rejection"]["code"], "ROLE_ABSENT")
        self.assertEqual(blank["rejection"]["code"], "ROLE_ABSENT")
        self.assertEqual(invalid["rejection"]["code"], "ROLE_INVALID")
        for report in (missing, blank, invalid):
            self.assertEqual(report["state"], BLOCKED)
            self.assertEqual(report["completed_step_ids"], [])

    def test_feature_flag_on_is_not_operational_proof(self):
        report = assess_onboarding(
            _context(
                "ADMIN",
                "ADVANCED",
                feature_flags={"real_broker_execution": True, "entitlement_activation": True},
            ),
            now=NOW,
        )
        row = _step(report, "operational_integration_review")
        self.assertEqual(row["evidence_status"], "UNKNOWN")
        self.assertEqual(row["blocked_reason"], "FEATURE_FLAG_IS_NOT_OPERATIONAL_PROOF")
        self.assertNotEqual(row["state"], COMPLETED)
        self.assertFalse(report["guardian"]["allowed"])
        self.assertFalse(report["feature_flag_changed"])
        self.assertFalse(report["feature_flag_is_operational_proof"])

    def test_feature_flag_off_does_not_keep_old_completion(self):
        claimed = [
            "role_confirmed",
            "experience_confirmed",
            "read_access_confirmed",
            "admin_guardian_review",
            "operational_integration_review",
        ]
        progress = {
            "onboarding_version": 1,
            "role": "ADMIN",
            "experience_mode": "ADVANCED",
            "subject_ref": "subject.one",
            "updated_at": UPDATED,
            "state": COMPLETED,
            "completed_step_ids": claimed,
            "completed_step_versions": {step_id: 1 for step_id in claimed},
            "acknowledged_step_ids": ["admin_guardian_review"],
            "blocked_step_ids": [],
            "stale_step_ids": [],
            "last_seen_step_id": "operational_integration_review",
        }
        progress["digest"] = onboarding_digest(progress)
        report = resume_onboarding(
            _context("ADMIN", "ADVANCED", feature_flags={"real_broker_execution": False}),
            progress,
            now=NOW,
        )
        self.assertNotIn("operational_integration_review", report["completed_step_ids"])
        self.assertIn("operational_integration_review", report["stale_step_ids"])
        self.assertEqual(report["state"], STALE)

    def test_user_and_sales_cannot_complete_admin_steps(self):
        for role in ("USER", "SALES"):
            with self.subTest(role=role):
                report = complete_onboarding_step(
                    _context(role),
                    None,
                    "admin_guardian_review",
                    now=NOW,
                )
                self.assertEqual(report["rejection"]["code"], "PRIVILEGE_ESCALATION")
                self.assertNotIn("admin_guardian_review", report["completed_step_ids"])
                self.assertFalse(report["real_trading_enabled"])

    def test_skipping_a_prerequisite_does_not_complete_the_step(self):
        report = complete_onboarding_step(_context("SALES", "ADVANCED"), None, "experience_confirmed", now=NOW)
        self.assertEqual(report["rejection"]["code"], "SKIPPED_PREREQUISITE")
        self.assertEqual(report["completed_step_ids"], [])
        forged = {
            "onboarding_version": 1,
            "role": "SALES",
            "experience_mode": "ADVANCED",
            "subject_ref": "subject.one",
            "updated_at": UPDATED,
            "state": COMPLETED,
            "completed_step_ids": ["experience_confirmed"],
            "completed_step_versions": {"experience_confirmed": 1},
            "acknowledged_step_ids": [],
            "blocked_step_ids": [],
            "stale_step_ids": [],
            "last_seen_step_id": "",
        }
        forged["digest"] = onboarding_digest(forged)
        resumed = resume_onboarding(_context("SALES", "ADVANCED"), forged, now=NOW)
        self.assertNotIn("experience_confirmed", resumed["completed_step_ids"])
        self.assertEqual(resumed["state"], STALE)

    def test_normal_sales_advanced_progression_can_complete(self):
        report = _walk(_context("SALES", "ADVANCED"), [
            "role_confirmed",
            "experience_confirmed",
            "read_access_confirmed",
        ])
        self.assertEqual(report["state"], COMPLETED)
        self.assertEqual(report["completed_step_ids"], [
            "role_confirmed",
            "experience_confirmed",
            "read_access_confirmed",
        ])
        self.assertFalse(report["executes_action"])
        self.assertFalse(report["real_trading_enabled"])

    def test_resume_keeps_compatible_progress_and_same_digest(self):
        done = _walk(_context("SALES", "ADVANCED"), [
            "role_confirmed",
            "experience_confirmed",
            "read_access_confirmed",
        ])
        resumed = resume_onboarding(_context("SALES", "ADVANCED"), done, now=NOW)
        self.assertEqual(resumed["completed_step_ids"], done["completed_step_ids"])
        self.assertEqual(resumed["digest"], done["digest"])
        self.assertEqual(resumed["state"], COMPLETED)

    def test_changed_version_becomes_stale(self):
        done = complete_onboarding_step(_context("SALES", "ADVANCED"), None, "role_confirmed", now=NOW)
        resumed = resume_onboarding(
            _context("SALES", "ADVANCED"),
            done,
            now=NOW,
            step_versions={"role_confirmed": 2},
        )
        self.assertNotIn("role_confirmed", resumed["completed_step_ids"])
        self.assertIn("role_confirmed", resumed["stale_step_ids"])
        self.assertEqual(resumed["state"], STALE)
        self.assertTrue(resumed["review_required"])

    def test_digest_is_deterministic_and_tampering_is_rejected(self):
        payload = _context("SALES", "ADVANCED")
        first = assess_onboarding(payload, now=NOW)
        second = assess_onboarding(payload, now=NOW)
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(first["digest"], onboarding_digest(first))
        changed = assess_onboarding(_context("SALES", "BEGINNER"), now=NOW)
        self.assertNotEqual(first["digest"], changed["digest"])
        forged = dict(first)
        forged["digest"] = "ab" * 32
        rejected = resume_onboarding(payload, forged, now=NOW)
        self.assertEqual(rejected["rejection"]["code"], "DIGEST_MISMATCH")
        self.assertEqual(rejected["completed_step_ids"], [])
        self.assertEqual(rejected["state"], BLOCKED)

    def test_duplicate_unknown_and_malformed_progress_are_rejected(self):
        duplicate = resume_onboarding(_context("SALES", "ADVANCED"), {
            "completed_step_ids": ["role_confirmed", "role_confirmed"],
            "role": "SALES",
            "experience_mode": "ADVANCED",
            "updated_at": UPDATED,
        }, now=NOW)
        self.assertEqual(duplicate["rejection"]["code"], "DUPLICATE_STEP_ID")
        self.assertEqual(duplicate["completed_step_ids"], [])
        unknown = complete_onboarding_step(_context("SALES", "ADVANCED"), None, "not-a-step", now=NOW)
        self.assertEqual(unknown["rejection"]["code"], "UNKNOWN_STEP")
        malformed = resume_onboarding(_context("SALES", "ADVANCED"), {
            "completed_step_ids": "role_confirmed",
            "role": "SALES",
            "experience_mode": "ADVANCED",
            "updated_at": UPDATED,
        }, now=NOW)
        self.assertEqual(malformed["rejection"]["code"], "MALFORMED_PROGRESS")
        typed = resume_onboarding(_context("SALES", "ADVANCED"), {
            "completed_step_ids": [1, None],
            "role": "SALES",
            "experience_mode": "ADVANCED",
            "updated_at": UPDATED,
        }, now=NOW)
        self.assertEqual(typed["rejection"]["code"], "MALFORMED_PROGRESS")

    def test_secret_fields_are_rejected_without_echoing_the_value(self):
        for key in ("token", "password", "api_key", "secret", "credential"):
            with self.subTest(key=key):
                report = assess_onboarding(_context("ADMIN", "ADVANCED", **{key: SECRET}), now=NOW)
                self.assertEqual(report["rejection"]["code"], "SECRET_FIELD")
                self.assertNotIn(SECRET, json.dumps(report))
                self.assertEqual(report["steps"], [])

    def test_invalid_types_empty_values_and_large_payload_fail_closed(self):
        self.assertEqual(assess_onboarding(None, now=NOW)["rejection"]["code"], "PAYLOAD_INVALID")
        self.assertEqual(assess_onboarding(_context(role=1), now=NOW)["rejection"]["code"], "TYPE_INVALID")
        self.assertEqual(
            assess_onboarding(_context(entitlements={"scope": PERSONAL_SCOPE}), now=NOW)["rejection"]["code"],
            "TYPE_INVALID",
        )
        self.assertEqual(
            assess_onboarding(_context(subject_ref=""), now=NOW)["rejection"]["code"],
            "SUBJECT_REF_INVALID",
        )
        self.assertEqual(
            assess_onboarding(_context(subject_ref="x" * 5000), now=NOW)["rejection"]["code"],
            "PAYLOAD_TOO_LARGE",
        )
        self.assertEqual(
            assess_onboarding(_context(updated_at="yesterday"), now=NOW)["rejection"]["code"],
            "INVALID_TIMESTAMP",
        )
        future = (NOW + timedelta(days=1)).isoformat()
        self.assertEqual(
            assess_onboarding(_context(updated_at=future), now=NOW)["rejection"]["code"],
            "FUTURE_TIMESTAMP",
        )
        self.assertFalse(assess_onboarding(_context(role=[]), now=NOW)["real_trading_enabled"])

    def test_role_or_experience_swap_and_replay_do_not_keep_completed(self):
        admin = _walk(_context("ADMIN", "BEGINNER", operational_integration_confirmed=True), [
            "role_confirmed",
            "experience_confirmed",
            "read_access_confirmed",
            "admin_guardian_review",
        ])
        swapped = resume_onboarding(_context("USER", "BEGINNER"), admin, now=NOW)
        self.assertEqual(swapped["rejection"]["code"], "ROLE_CHANGED")
        self.assertEqual(swapped["state"], STALE)
        self.assertNotIn("admin_guardian_review", swapped["completed_step_ids"])
        self.assertFalse(swapped["admin"])

        sales = _walk(_context("SALES", "BEGINNER"), [
            "role_confirmed",
            "experience_confirmed",
            "read_access_confirmed",
            "sales_orientation",
        ])
        mode_swap = resume_onboarding(_context("SALES", "ADVANCED"), sales, now=NOW)
        self.assertEqual(mode_swap["rejection"]["code"], "EXPERIENCE_CHANGED")
        self.assertEqual(mode_swap["state"], STALE)
        self.assertEqual(mode_swap["completed_step_ids"], [])

        later = _context("SALES", "BEGINNER", updated_at="2026-09-29T02:00:00+00:00")
        replay = resume_onboarding(later, sales, now=NOW + timedelta(hours=3))
        self.assertEqual(replay["rejection"]["code"], "REPLAY_REJECTED")
        self.assertEqual(replay["completed_step_ids"], [])
        self.assertEqual(replay["state"], STALE)

    def test_no_side_effects_and_real_trading_stays_false(self):
        payload = _context("USER", entitlements=[_entitlement()])
        original = deepcopy(payload)
        report = assess_onboarding(payload, now=NOW)
        self.assertEqual(payload, original)
        source = Path("atlasquant_aion_onboarding.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)
        self.assertTrue(imported.isdisjoint({"requests", "socket", "subprocess", "urllib", "http"}))
        self.assertNotIn("open", calls)
        reports = [
            report,
            assess_onboarding(_context("ADMIN", "ADVANCED"), now=NOW),
            assess_onboarding(_context("SALES"), now=NOW),
            assess_onboarding(None, now=NOW),
        ]
        for item in reports:
            self.assertFalse(item["real_trading_enabled"])
            self.assertFalse(item["executes_action"])
            self.assertFalse(item["runtime_written"])
            self.assertFalse(item["guardian"]["allowed"])


if __name__ == "__main__":
    unittest.main()
