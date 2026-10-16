"""Convergence regressions for Checkpoint Mestre V18 and Astra durable hardening."""
from copy import deepcopy
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from atlasquant_aion_continuity import (
    MissionTransitionError,
    new_mission,
    transition_mission,
)
from atlasquant_aion_core import guardian_decision
from atlasquant_aion_durable_tasks import (
    DurableTaskError,
    new_durable_task,
    prepare_resume,
    record_resume,
    update_step,
)
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
    ensure_operating_checkpoint,
    update_continuity_checkpoint,
    update_durable_tasks_checkpoint,
)
from atlasquant_aion_memory_layers import remember
from atlasquant_aion_observability import events_digest, new_event, normalize_event
from atlasquant_aion_specialist_session import (
    build_specialist_session_snapshot,
    loaded_session_from_checkpoint,
    read_loaded_specialist_snapshot,
)
from atlasquant_aion_status_board import build_master_status_board

ADMIN = {"role": "ADMIN"}
NOW = "2026-09-27T08:00:00+00:00"
CANONICAL_MAIN = "571f9a49e83d8696e3ff13a56b62745da34cc69b"
ROOT = Path(__file__).resolve().parent


def _git(args):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _commit_exists(revision):
    if not revision:
        return False
    return _git(["rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"]).returncode == 0


def _repository_is_shallow():
    result = _git(["rev-parse", "--is-shallow-repository"])
    return result.returncode == 0 and result.stdout.strip() == "true"


A54_PINNED_LAB_BASES = {
    "lab/aion-v16-a49-worker-pure-transition-simulation-20261013":
        "c1c7f5940eef913d60ff2f77e3bc1de3181db2f2",
    "lab/aion-v16-a52-a50-a51-integrated-containment-20261013":
        "60c61d959c81d50f6a9d6b5d1f1f932abf14844d",
    "lab/aion-v16-a54-stacked-ci-main-boundary-windows-20261013":
        "b36830e1733ce5c7e91fe67f730b4e061574b3eb",
    # A59 PR base is an immutable A58 LAB head. Unknown bases still DENY.
    "lab/aion-v16-a58-inflight-local-receipt-trust-red-20261014":
        "2eda461d4a9076807d3c0a1fea2b904f5c7d9e62",
    # A60 parent A59 is explicitly SHA-pinned, not an arbitrary PR base.
    "lab/aion-v16-a59-live-self-reported-status-red-20261014":
        "3c1e05ac3e497f37aa1473d7b7f3ab5d9633c22f",
    # A61 requires precisely the reviewed A60 parent, no unknown fallback.
    "lab/aion-v16-a60-saga-pre-enqueue-local-integrity-20261014":
        "a9c8e5bb491174aeaf6305732eb56ec5d6e26166",
    # A62 source PR must use exact A61 parent, not a floating LAB ref.
    "lab/aion-v16-a61-saga-outbox-local-atomicity-20261014":
        "07e95f6b1abd2acdf6e6c2331329b5e392ac3b65",
    # A63 parent A62 must match its reviewed immutable SHA.
    "lab/aion-v16-a62-saga-outcome-untrusted-local-20261014":
        "2449548771545dee00b715a22309c33635909831",
    # A64 parent A63 verified exact SHA; other branches remain denied.
    "lab/aion-v16-a63-saga-outcome-locked-snapshot-20261014":
        "d14c9ec14502d9b84852934a9ef0cd485fbcf95a",
    # A65 parent A64 approved for LAB testing only at exact immutable SHA.
    "lab/aion-v16-a64-saga-forward-outbox-binding-20261014":
        "e577d59c65f2541e41155b525337800fe71cbb46",
    # A66 parent A65 must be immutable; never infer from a moving LAB ref.
    "lab/aion-v16-a65-saga-unverified-terminal-state-20261014":
        "a59be4fe0c689fb9a7c1f0cd18811d5031f57919",
    # A67 must target exactly A66's audited immutable parent, not a moving ref.
    "lab/aion-v16-a66-empty-inflight-no-witness-20261014":
        "1dc406122e172e309d036b87d56d29adc2be28e7",
    # A68 requires exactly the reviewed A67 HEAD, with no floating parent.
    "lab/aion-v16-a67-autopilot-data-branch-pin-20261014":
        "7ffb2d15c89e1f3be2bb9e44ca744672353324b5",
    # A69 requires the reviewed A68 parent at the exact immutable SHA.
    "lab/aion-v16-a68-render-deploy-hard-stop-20261014":
        "093f35cab46cde1c3de8639e54569942f5270335",
    # A70 requires the reviewed A69 parent at the exact immutable SHA.
    "lab/aion-v16-a69-checkpoint-bootstrap-migration-hard-stop-20261014":
        "90d290e801bbcb80885000349b9353ac7794d03b",
    # A71 requires reviewed A70 at exact immutable SHA, not a mutable LAB ref.
    "lab/aion-v16-a70-main-ruleset-contract-20261014":
        "4152d9f1d5b8afad6703f4678ca89ba1b254fcfe",
    # A72 reviewed A71 parent pinned exactly, never a floating LAB base.
    "lab/aion-v16-a71-inflight-receipt-missing-unsafe-20261014":
        "6501bff88f818202e6b5a5538093a6698d259dd9",
    # A73 reviewed A72 parent, only for LAB not release.
    "lab/aion-v16-a72-inflight-attempt-malformed-hard-stop-20261014":
        "76623d1b2d719d350ab1135a2a888c6fdfa61192",
    # A74 is attached to the exact audited A73 immutable commit.
    "lab/aion-v16-a73-readiness-requires-external-source-witness-20261014":
        "1b9466509e13a24f60a611453e41c905896da585",
    # A75 targets the reviewed A74 commit, not a moving LAB ref.
    "lab/aion-v16-a74-activation-plan-ticket-authority-hard-stop-20261014":
        "d2c3f6deaa0af4170be3abf4bdccb6c4fca7ab64",
    # A76 and A77 are siblings pinned to A75 exactly; no authority is enabled.
    "lab/aion-v16-a75-f1-t1-untrusted-witness-intake-20261014":
        "373618865d8b7b7d2497e319db0c7c7926daa4fe",
    # A78 QA-only integration targets the immutable reviewed A76 HEAD.
    "lab/aion-v16-a76-activation-coverage-recovery-20261014":
        "092eb60bd9b4f6f66035d1f71ee6ee8add9441cd",
    # A82 integrated LAB review may target only the pinned A81 parent.
    "lab/aion-v16-a81-windows-a62-sqlite-cleanup-20261014":
        "881c0c1e45e0695591894bec234efbac6d563f27",
    # A83 may target ONLY reviewed A82 head, not a mutable branch.
    "lab/aion-v16-a82-core-stack-integration-rehearsal-20261014":
        "70c1c59236e00ff6b11b7f7dec6e32913997720a",
    # A84 security rehearsal must originate on the pinned A83 snapshot.
    "lab/aion-v16-a83-inflight-local-failed-proof-truthfulness-20261014":
        "6cde550b3e1f6988b336bd474c23c2926100f00f",
    # A88 stays stacked on the immutable audited A84 snapshot.
    "lab/aion-v16-a84-inflight-staging-independent-proof-20261014":
        "861512d394a662dc4554bd31feec916a19d07ad2",
    # A89 accepts only the reviewed A88 immutable parent HEAD for LAB.
    "lab/aion-v16-a88-outbox-redacted-payload-identity-20261015":
        "70d7c0f57cd9b25cc011181453594c83df8fbbbc",
    # A90 CI-only rehearsal is pinned to the reviewed A89 immutable parent.
    "lab/aion-v16-a89-json-action-payload-canonical-gate-20261015":
        "0a5422504822cadbe6ee1ed5ac70bcc5158a8254",
    # A95 can only rehearse on the exact audited A90 historical baseline.
    "lab/aion-v16-a90-historical-quality-security-rebaseline-20261015":
        "be75d3f71045f4adcefd0141dc84642bc2a3d66a",
    # A96 is stacked only on the audited immutable A95 final HEAD.
    "lab/aion-v16-a95-credential-key-stage-denial-20261015":
        "8a29fb4099f2893f2bd84126085a94d3bf277c71",
    # A100 audits only immutable A96 without modifying production behavior.
    "lab/aion-v16-a96-extended-auth-header-denial-20261015":
        "f503f23a5a1dbb7adb59db899b6639f8d304ae21",
    # A103 bounded payload gate starts only from the immutable A100 audit HEAD.
    "lab/aion-v16-a100-qa-security-rebaseline-a96-20261015":
        "a27cbf5f6498629cafc20b196a28582df887bbfc",
    # A104 rechecks the historical suite on the exact completed A103 laboratory HEAD.
    "lab/aion-v16-a103-bounded-json-action-stage-20261015":
        "7bc29d1b023043b14681a09174538511e9b8e097",
    # A112 checks only the exact A111 historical rebaseline snapshot; no floating lab branch.
    "lab/aion-v16-a111-historical-rebaseline-a110-20261016":
        "a0cc38d62aa9fce9e3eef14c3eb74c84145e3b27",
    # A113 trusts ONLY the immutable A112 HEAD as LAB base, still checking A49.
    "lab/aion-v16-a112-canonical-qa-and-base-pin-20261016":
        "1350a45a31c9b53185d5a8771b437a49c580772d",
    # A114 derives only from the immutable verified A113 LAB snapshot.
    "lab/aion-v16-a113-expired-claim-causal-quarantine-20261016":
        "bb891246506b3eb1dbc677405e2015c011854a2d",
    # A115 validation only on exact immutable A114 LAB parent, no floating refs.
    "lab/aion-v16-a114-saga-projection-integrity-20261016":
        "fd3183b291561b033be6a2f65450e873d7af65f9",
    # A116 audits only the exact reviewed A115 head for non-authoritative receipt fixtures.
    "lab/aion-v16-a115-windows-saga-sqlite-cleanup-20261016":
        "e7e196faa492fb1611956e32ff5c97904949cefc",
    # A117 only permits the exact reviewed A116 HEAD; never a floating branch.
    "lab/aion-v16-a116-inflight-corrupt-receipt-fixture-20261016":
        "9c13fa9bce1290a56716714c9991979edb02e3dd",
}
A54_A49_PARENT = "c1c7f5940eef913d60ff2f77e3bc1de3181db2f2"
A54_ORIGIN_URLS = {
    "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4",
    "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4.git",
}


def _production_base():
    """A54: validate stacked target, but ALWAYS snapshot true origin/main.

    Git source selection is not independent owner/producer/witness enrollment.
    Never use a cached lab ref or local main as a production-main substitute.
    """
    base_ref = os.environ.get("GITHUB_BASE_REF", "").strip()
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request" and not base_ref:
        raise AssertionError("A54_PR_BASE_REQUIRED")
    target = base_ref or "main"
    if target != "main" and target not in A54_PINNED_LAB_BASES:
        raise AssertionError("A54_UNKNOWN_PR_BASE")
    origin = _git(["remote", "get-url", "origin"])
    if origin.returncode != 0 or origin.stdout.strip() not in A54_ORIGIN_URLS:
        raise AssertionError("A54_ORIGIN_NOT_APPROVED")
    fetched = _git([
        "fetch", "--no-tags", "--depth", "1", "origin",
        "+refs/heads/main:refs/remotes/origin/main",
    ])
    if fetched.returncode != 0:
        raise AssertionError("A54_TRUE_MAIN_UNAVAILABLE")
    resolved = _git(["rev-parse", "--verify", "origin/main^{commit}"])
    main_sha = resolved.stdout.strip()
    if (resolved.returncode != 0 or len(main_sha) != 40
            or any(c not in "0123456789abcdef" for c in main_sha)):
        raise AssertionError("A54_MAIN_COMMIT_INVALID")
    if target != "main":
        # A54 -> A52 -> A49 needs depth three for the pinned ancestor.
        # Earlier pinned bases need at most depth two. Never omit ancestry.
        pinned_depth = (
            # A66's fixed A65 base is 65 commits ahead of A49. Fetch a
            # deeper, bounded history so the required ancestry check runs,
            # never relax A54_A49_PARENT_NOT_VERIFIED on shallow clones.
            # A67 A66 parent is 77 commits ahead of A49; this preserves
            # an actual merge-base ancestry proof even on a shallow checkout.
            # A68 pinned A67 parent is 84 commits beyond the A49 trust base.
            # A69 A68 parent is 92 commits ahead of the A49 ancestor.
            # A70 reviewed A69 base is 99 commits beyond required A49.
            # A71 preserves A49 ancestry across the reviewed A70 stack.
            # A72 needs A71 and the unchanged A49 ancestor.
            # A73 includes A72 and the trusted A49 historical ancestor.
            # A74 includes A73 and deep true-origin-main/A49 ancestry.
            # A74/A75/A76 retain the same A49 provenance ancestry with
            # a bounded depth; no shallow-clone bypass or local-main fallback.
            "864" if target == "lab/aion-v16-a116-inflight-corrupt-receipt-fixture-20261016"
            else "832" if target == "lab/aion-v16-a115-windows-saga-sqlite-cleanup-20261016"
            else "800" if target == "lab/aion-v16-a114-saga-projection-integrity-20261016"
            else "768" if target == "lab/aion-v16-a113-expired-claim-causal-quarantine-20261016"
            else "736" if target == "lab/aion-v16-a112-canonical-qa-and-base-pin-20261016"
            else "704" if target == "lab/aion-v16-a111-historical-rebaseline-a110-20261016"
            else "608" if target == "lab/aion-v16-a103-bounded-json-action-stage-20261015"
            else "576" if target == "lab/aion-v16-a100-qa-security-rebaseline-a96-20261015"
            else "544" if target == "lab/aion-v16-a96-extended-auth-header-denial-20261015"
            else "512" if target == "lab/aion-v16-a95-credential-key-stage-denial-20261015"
            else "480" if target == "lab/aion-v16-a90-historical-quality-security-rebaseline-20261015"
            else "448" if target == "lab/aion-v16-a89-json-action-payload-canonical-gate-20261015"
            else "416" if target == "lab/aion-v16-a88-outbox-redacted-payload-identity-20261015"
            else "384" if target == "lab/aion-v16-a84-inflight-staging-independent-proof-20261014"
            else "352" if target == "lab/aion-v16-a83-inflight-local-failed-proof-truthfulness-20261014"
            else "320" if target == "lab/aion-v16-a82-core-stack-integration-rehearsal-20261014"
            else "288" if target == "lab/aion-v16-a81-windows-a62-sqlite-cleanup-20261014"
            else "256" if target in {
                "lab/aion-v16-a74-activation-plan-ticket-authority-hard-stop-20261014",
                "lab/aion-v16-a75-f1-t1-untrusted-witness-intake-20261014",
                "lab/aion-v16-a76-activation-coverage-recovery-20261014",
            }
            else "208" if target == "lab/aion-v16-a73-readiness-requires-external-source-witness-20261014"
            else "192" if target == "lab/aion-v16-a72-inflight-attempt-malformed-hard-stop-20261014"
            else "176" if target == "lab/aion-v16-a71-inflight-receipt-missing-unsafe-20261014"
            else "160" if target == "lab/aion-v16-a70-main-ruleset-contract-20261014"
            else "136" if target == "lab/aion-v16-a69-checkpoint-bootstrap-migration-hard-stop-20261014"
            else "128" if target == "lab/aion-v16-a68-render-deploy-hard-stop-20261014"
            else "120" if target == "lab/aion-v16-a67-autopilot-data-branch-pin-20261014"
            else "112" if target == "lab/aion-v16-a66-empty-inflight-no-witness-20261014"
            else "96" if target == "lab/aion-v16-a65-saga-unverified-terminal-state-20261014"
            else "64" if target in {
                "lab/aion-v16-a58-inflight-local-receipt-trust-red-20261014",
                "lab/aion-v16-a59-live-self-reported-status-red-20261014",
                "lab/aion-v16-a60-saga-pre-enqueue-local-integrity-20261014",
                "lab/aion-v16-a61-saga-outbox-local-atomicity-20261014",
                "lab/aion-v16-a62-saga-outcome-untrusted-local-20261014",
                "lab/aion-v16-a63-saga-outcome-locked-snapshot-20261014",
                "lab/aion-v16-a64-saga-forward-outbox-binding-20261014",
                "lab/aion-v16-a65-saga-unverified-terminal-state-20261014",
            }
            else "3" if target == "lab/aion-v16-a54-stacked-ci-main-boundary-windows-20261013"
            else "2"
        )
        fetched = _git([
            "fetch", "--no-tags", "--depth", pinned_depth, "origin",
            f"+refs/heads/{target}:refs/remotes/origin/{target}",
        ])
        if fetched.returncode != 0:
            raise AssertionError("A54_PINNED_BASE_UNAVAILABLE")
        actual = _git(["rev-parse", "--verify", f"origin/{target}^{{commit}}"])
        if actual.returncode != 0 or actual.stdout.strip() != A54_PINNED_LAB_BASES[target]:
            raise AssertionError("A54_LAB_BASE_SHA_MISMATCH")
        ancestry = _git(["merge-base", "--is-ancestor", A54_A49_PARENT, actual.stdout.strip()])
        if ancestry.returncode != 0:
            raise AssertionError("A54_A49_PARENT_NOT_VERIFIED")
    # Return immutable main SHA: later ref changes cannot redirect the diff.
    return main_sha


def _assert_production_surfaces(base):
    # NUL avoids quoted/newline path ambiguities; no-renames retains old paths.
    diff = _git(["diff", "--no-renames", "--name-only", "-z", base])
    if diff.returncode != 0:
        raise AssertionError("A54_MAIN_SURFACE_DIFF_UNAVAILABLE")
    forbidden = _forbidden_production_paths(diff.stdout.split("\x00"))
    if forbidden:
        raise AssertionError("A54_FORBIDDEN_PRODUCTION_SURFACE:" + repr(forbidden))


def _forbidden_production_paths(paths):
    forbidden = []
    for line in paths:
        path = line.strip()
        if not path:
            continue
        if path.lower() == "render.yaml" or path.lower().startswith("deploy/") or "secret" in path.lower():
            forbidden.append(path)
    return forbidden


def _render_manual_deploy_hardening_only(base):
    previous=_git(["show",f"{base}:render.yaml"])
    if previous.returncode != 0:
        return False
    current=(ROOT/"render.yaml").read_text(encoding="utf-8")
    before=previous.stdout
    marker="autoDeployTrigger: commit"
    if before.count(marker) != 1:
        return False
    expected=before.replace(marker,"autoDeployTrigger: off")
    return current == expected


def _task(**step_fields):
    return new_durable_task(
        "Local work",
        steps=[{"title": "Inspect", "step_id": "s", **step_fields}],
        checkpoint_digest="cp-a",
        created_at=NOW,
    )


class AionConvergenceTests(unittest.TestCase):
    def test_checkpoint_v18_and_durable_tasks_coexist(self):
        task = record_resume(_task(), expected_revision=1, checkpoint_digest="cp-a")
        checkpoint = update_durable_tasks_checkpoint(default_checkpoint(), records=[task])
        self.assertEqual(checkpoint["checkpoint_version"], 18)
        self.assertIn("memory_layers", checkpoint)
        self.assertEqual(checkpoint["memory_layers"]["schema"], "ATLASQUANT_AION_MEMORY_LAYERS_V1")
        self.assertEqual(checkpoint["durable_tasks"]["records"][0]["state"], task["state"])
        self.assertFalse(checkpoint["durable_tasks"]["records"][0]["automatic_resume_executes"])
        self.assertFalse(checkpoint["aion"]["real_trading"])
        restored = ensure_operating_checkpoint(json.loads(json.dumps(checkpoint)))
        self.assertEqual(restored["checkpoint_version"], 18)
        self.assertEqual(restored["durable_tasks"]["records"][0], task)
        self.assertEqual(checkpoint_integrity_report(restored)["state"], "CONFIRMED")

    def test_legacy_checkpoint_migrates_without_dropping_durable_tasks(self):
        task = record_resume(_task(), expected_revision=1, checkpoint_digest="cp-a")
        mission = new_mission("Keep continuity", created_at=NOW)
        current = update_durable_tasks_checkpoint(default_checkpoint(), records=[task])
        current = update_continuity_checkpoint(current, missions=[mission])
        legacy = json.loads(json.dumps(current))
        legacy["checkpoint_version"] = 17
        legacy.pop("memory_layers")
        upgraded = ensure_operating_checkpoint(legacy)
        self.assertEqual(legacy["checkpoint_version"], 17)
        self.assertNotIn("memory_layers", legacy)
        self.assertEqual(upgraded["checkpoint_version"], 18)
        self.assertEqual(upgraded["memory_layers"]["schema"], "ATLASQUANT_AION_MEMORY_LAYERS_V1")
        self.assertEqual(upgraded["durable_tasks"]["records"][0]["durable_task_id"], task["durable_task_id"])
        self.assertEqual(upgraded["durable_tasks"]["records"][0]["state"], task["state"])
        self.assertEqual(upgraded["durable_tasks"]["records"][0]["steps"], task["steps"])
        self.assertEqual(upgraded["continuity"]["missions"][0]["mission_id"], mission["mission_id"])
        report = checkpoint_integrity_report(legacy)
        self.assertIn(report["state"], {"MIGRATION_REQUIRED", "CONFIRMED"})
        self.assertNotEqual(report["state"], "MISMATCH")

    def test_memory_fabric_does_not_erase_durable_state_machine(self):
        waiting = update_step(_task(), "s", "WAITING_APPROVAL")
        checkpoint = update_durable_tasks_checkpoint(default_checkpoint(), records=[waiting])
        before = deepcopy(checkpoint["durable_tasks"])
        checkpoint["memory_layers"] = remember(
            checkpoint["memory_layers"],
            layer="project",
            content="A maquina de estados duravel permanece intacta.",
            origin="convergence",
            category="continuity",
            truth_state="CONFIRMED",
        )
        merged = ensure_operating_checkpoint(checkpoint)
        self.assertEqual(merged["checkpoint_version"], 18)
        self.assertGreaterEqual(len(merged["memory_layers"]["entries"]), 1)
        self.assertEqual(merged["durable_tasks"]["records"], before["records"])
        self.assertEqual(merged["durable_tasks"]["records"][0]["state"], "WAITING_APPROVAL")
        self.assertEqual(merged["durable_tasks"]["digest"], before["digest"])

    def test_specialist_snapshot_does_not_erase_checkpoint_continuity(self):
        waiting = update_step(_task(), "s", "WAITING_APPROVAL")
        mission = new_mission("Snapshot must not write", created_at=NOW)
        checkpoint = update_durable_tasks_checkpoint(default_checkpoint(), records=[waiting])
        checkpoint["continuity"]["missions"] = [mission]
        before = deepcopy(checkpoint)
        snapshot = loaded_session_from_checkpoint(checkpoint)
        reading = read_loaded_specialist_snapshot("market", snapshot)
        self.assertEqual(checkpoint, before)
        self.assertEqual(checkpoint["continuity"]["missions"][0]["mission_id"], mission["mission_id"])
        self.assertEqual(checkpoint["durable_tasks"]["records"][0]["state"], "WAITING_APPROVAL")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertFalse(reading["answers_user_question"])
        self.assertNotIn("top_10", reading.get("observations") or {})

    def test_sanitization_still_removes_secrets_and_keeps_old_event_digests(self):
        historical = {
            "schema": "ATLASQUANT_AION_OBSERVABILITY_V1",
            "event_id": "EV-LEGACY00000001",
            "event_type": "note",
            "message": "hello",
            "severity": "INFO",
            "source": "AION",
            "truth_state": "CONFIRMED",
            "evidence": {"note": "plain"},
            "created_at": NOW,
        }
        self.assertEqual(normalize_event(historical), historical)
        self.assertEqual(events_digest([historical]), events_digest([normalize_event(historical)]))
        event = new_event(
            "check",
            "token=abcd",
            evidence={"metadata": {"items": [{"api_key": "xy"}], "note": "password=abcd"}},
            created_at=NOW,
            request_id="Bearer zzzzzzzzzzzzz",
        )
        blob = json.dumps(event)
        self.assertNotIn("abcd", blob)
        self.assertNotIn("xy", blob)
        self.assertNotIn("zzzzzzzzzzzzz", blob)
        self.assertIn("[REDACTED]", blob)
        self.assertEqual(event["request_id"], "[REDACTED]")
        self.assertNotIn("task_id", event)

    def test_resume_does_not_execute_and_waiting_approval_is_not_bypassed(self):
        waiting = update_step(_task(), "s", "WAITING_APPROVAL", blocker="Needs review")
        resumed = record_resume(
            waiting,
            expected_revision=waiting["revision"],
            checkpoint_digest="cp-a",
        )
        self.assertEqual(resumed["state"], "WAITING_APPROVAL")
        self.assertEqual(resumed["steps"][0]["state"], "WAITING_APPROVAL")
        self.assertEqual(resumed["steps"][0]["attempts"], waiting["steps"][0]["attempts"])
        self.assertFalse(resumed["automatic_resume_executes"])
        view = prepare_resume(resumed, checkpoint_digest="cp-a")
        self.assertFalse(view["executes_action"])
        self.assertTrue(view["restores_state_only"])
        with self.assertRaises(DurableTaskError) as ctx:
            update_step(resumed, "s", "RUNNING", access=ADMIN)
        self.assertEqual(ctx.exception.result["error_code"], "APPROVAL_REQUIRED")
        self.assertFalse(ctx.exception.result["executes_action"])

    def test_terminal_mission_rejects_inconsistent_active_task_and_reopen(self):
        mission = new_mission("Finish", created_at=NOW)
        running = update_step(_task(), "s", "RUNNING", access=ADMIN)
        done = transition_mission([mission], mission["mission_id"], "IN_PROGRESS")
        done = transition_mission(done, mission["mission_id"], "DONE")
        self.assertEqual(done[0]["status"], "DONE")
        with self.assertRaises(MissionTransitionError) as mission_error:
            transition_mission(done, mission["mission_id"], "IN_PROGRESS")
        self.assertEqual(mission_error.exception.result["error_code"], "INVALID_MISSION_TRANSITION")
        self.assertFalse(mission_error.exception.result["executes_action"])
        checkpoint = update_durable_tasks_checkpoint(default_checkpoint(), records=[running])
        checkpoint["continuity"]["missions"] = done
        running["mission_id"] = mission["mission_id"]
        running["revision"] += 1
        with self.assertRaises(DurableTaskError) as task_error:
            update_durable_tasks_checkpoint(checkpoint, records=[running])
        self.assertEqual(task_error.exception.result["error_code"], "MISSION_TASK_INCONSISTENT")
        self.assertFalse(task_error.exception.result["executes_action"])

    def test_guardian_denies_real_trade_and_snapshot_stays_local(self):
        for flags in ({}, {"real_broker_execution": True}):
            decision = guardian_decision("real_trade", ADMIN, approved=True, feature_flags=flags)
            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["risk"], "REAL_TRADING")
        denied = _task(guardian_action="real_trade")
        with self.assertRaises(DurableTaskError) as ctx:
            update_step(denied, "s", "RUNNING", access=ADMIN, approved=True)
        self.assertEqual(ctx.exception.result["error_code"], "GUARDIAN_DENIED")

        def explode(*_args, **_kwargs):
            raise AssertionError("network call")

        with mock.patch("socket.create_connection", explode), mock.patch("urllib.request.urlopen", explode):
            snapshot = build_specialist_session_snapshot({"origin": "CHECKPOINT", "observed_at": NOW})
            absent = read_loaded_specialist_snapshot("market", None)
            core = read_loaded_specialist_snapshot("core", snapshot)
        self.assertFalse(snapshot["network_called"])
        self.assertFalse(snapshot["provider_called"])
        self.assertFalse(snapshot["secrets_included"])
        self.assertEqual(absent["answer_truth"], "UNKNOWN")
        self.assertEqual(absent["truth_state"], "UNKNOWN")
        self.assertFalse(absent["answers_user_question"])
        self.assertFalse(absent["network_called"])
        self.assertFalse(core["observations"]["real_trade_allowed"])
        self.assertFalse(core["answers_user_question"])

    def test_status_board_and_admin_keep_both_stacks(self):
        board = build_master_status_board(
            checkpoint={
                "operating": {"tasks": []},
                "entitlements": {"records": []},
                "continuity": {"missions": [], "handoffs": []},
                "durable_tasks": {"records": []},
                "memory_layers": default_checkpoint()["memory_layers"],
            },
            runtime_result={
                "status": "CONFIRMED",
                "integrity": {"state": "CONFIRMED", "matched": 7, "total": 7},
            },
            provider={"state": "ZERO_COST_LOCAL"},
            feature_flags={},
            system_context={"truth_state": "CONFIRMED", "source_build": "abc123"},
            market_context={"fresh_confirmed": False, "summary": ""},
            account_entitlement_audit={
                "schema": "ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1",
                "accounts_total": 0,
                "active_user_accounts": 0,
                "effective_user_accounts": 0,
                "user_accounts_without_effective_entitlement": 0,
                "duplicate_effective_user_accounts": 0,
                "orphan_effective_entitlements": 0,
            },
            working_dirty=False,
        )
        item = next(row for row in board["items"] if row["id"] == "durable_task_continuity")
        self.assertEqual(item["state"], "CONFIRMED")
        self.assertFalse(item["executes_action"])
        market = next(row for row in board["items"] if row["id"] == "market_freshness")
        self.assertEqual(market["state"], "UNKNOWN")
        admin = (ROOT / "atlasquant_aion_admin.py").read_text(encoding="utf-8")
        for marker in (
            "specialist_snapshot",
            "loaded_session_from_checkpoint",
            "memory_layer_summary",
            "answers_user_question",
            "expected_revision=resume.get(\"revision\")",
            "Prepare a retomada da tarefa selecionada primeiro.",
            "Ordens reais",
        ):
            self.assertIn(marker, admin)
        self.assertIn("durable_task_continuity", (ROOT / "atlasquant_aion_status_board.py").read_text(encoding="utf-8"))

    def test_main_and_production_surfaces_stay_untouched(self):
        base = _production_base()
        # Ancestry of the pinned base is enforced only when this clone can
        # actually walk that history. Shallow CI does not have the object.
        if _commit_exists(CANONICAL_MAIN) and not _repository_is_shallow():
            ancestor = _git(["merge-base", "--is-ancestor", CANONICAL_MAIN, base])
            self.assertEqual(
                ancestor.returncode,
                0,
                "A base main não contém mais o commit canônico da convergência.\n"
                + ancestor.stderr,
            )
        _assert_production_surfaces(base)
        checkpoint = default_checkpoint()
        self.assertFalse(checkpoint["aion"]["real_trading"])
        self.assertFalse(guardian_decision("deploy_production", ADMIN, approved=True)["allowed"])
        self.assertFalse(guardian_decision("merge_main", ADMIN, approved=True)["allowed"])
        self.assertFalse(guardian_decision("real_trade", ADMIN, approved=True)["allowed"])
        # Optimistic revision still refuses a stale checkpoint digest.
        current = update_durable_tasks_checkpoint(checkpoint, records=[_task()])
        with self.assertRaises(DurableTaskError) as ctx:
            update_durable_tasks_checkpoint(
                current,
                records=[_task()],
                expected_checkpoint_digest="stale",
            )
        self.assertEqual(ctx.exception.result["error_code"], "REVISION_CHECKPOINT_CONFLICT")
        self.assertNotEqual(checkpoint_source_digest(current), "stale")



class A55PinnedA54BaseTests(unittest.TestCase):
    """Adversarial stacked-base gate: no claim of external witness authority."""

    A54_TARGET = "lab/aion-v16-a54-stacked-ci-main-boundary-windows-20261013"
    MAIN_SHA = "a" * 40

    def _resolve(self, target, *, moved=False, main_down=False, ancestry_down=False, bad_origin=False):
        calls = []

        def fake_git(args):
            calls.append(list(args))
            if args[:2] == ["remote", "get-url"]:
                value = ("https://github.com/untrusted/not-our-repo"
                         if bad_origin else next(iter(A54_ORIGIN_URLS)))
                return subprocess.CompletedProcess(args, 0, value, "")
            if args[:1] == ["fetch"]:
                is_main = args[-1] == "+refs/heads/main:refs/remotes/origin/main"
                failed = main_down if is_main else False
                return subprocess.CompletedProcess(args, int(failed), "", "offline" if failed else "")
            if args[:2] == ["rev-parse", "--verify"]:
                if args[-1] == "origin/main^{commit}":
                    return subprocess.CompletedProcess(args, 0, self.MAIN_SHA, "")
                if args[-1] == f"origin/{self.A54_TARGET}^{{commit}}":
                    sha = "b" * 40 if moved else A54_PINNED_LAB_BASES[self.A54_TARGET]
                    return subprocess.CompletedProcess(args, 0, sha, "")
            if args[:2] == ["merge-base", "--is-ancestor"]:
                return subprocess.CompletedProcess(args, int(ancestry_down), "", "")
            raise AssertionError("A55_UNEXPECTED_GIT_CALL " + repr(args))

        self.calls = calls
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "pull_request",
                                         "GITHUB_BASE_REF": target}), mock.patch(
            __name__ + "._git", side_effect=fake_git
        ):
            return _production_base()

    def test_a55_exact_a54_pin_fetches_depth_three_and_returns_real_main(self):
        self.assertEqual(self._resolve(self.A54_TARGET), self.MAIN_SHA)
        self.assertIn(["fetch", "--no-tags", "--depth", "3", "origin",
                       "+refs/heads/" + self.A54_TARGET + ":refs/remotes/origin/" + self.A54_TARGET],
                      self.calls)
        self.assertIn(["merge-base", "--is-ancestor", A54_A49_PARENT,
                       A54_PINNED_LAB_BASES[self.A54_TARGET]], self.calls)
        self.assertEqual(self.calls[1][-1], "+refs/heads/main:refs/remotes/origin/main")

    def test_a55_moved_a54_pin_denied(self):
        with self.assertRaisesRegex(AssertionError, "A54_LAB_BASE_SHA_MISMATCH"):
            self._resolve(self.A54_TARGET, moved=True)

    def test_a55_unknown_base_denied_before_any_git(self):
        with self.assertRaisesRegex(AssertionError, "A54_UNKNOWN_PR_BASE"):
            self._resolve("lab/unknown-not-allowlisted")
        self.assertEqual(self.calls, [])

    def test_a55_no_true_main_never_falls_back_to_lab(self):
        with self.assertRaisesRegex(AssertionError, "A54_TRUE_MAIN_UNAVAILABLE"):
            self._resolve(self.A54_TARGET, main_down=True)
        self.assertFalse(any("refs/heads/" + self.A54_TARGET in " ".join(c) for c in self.calls))

    def test_a55_missing_a49_ancestry_denied(self):
        with self.assertRaisesRegex(AssertionError, "A54_A49_PARENT_NOT_VERIFIED"):
            self._resolve(self.A54_TARGET, ancestry_down=True)

    def test_a55_wrong_origin_denied(self):
        with self.assertRaisesRegex(AssertionError, "A54_ORIGIN_NOT_APPROVED"):
            self._resolve(self.A54_TARGET, bad_origin=True)

if __name__ == "__main__":
    unittest.main()
