import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_certification_package import (
    BUSINESS_REQUIRED_GATES,
    assess_business_certification_package,
)
from atlasquant_aion_business_external_attestation import (
    REPOSITORY_FULL_NAME,
    REQUIRED_WORKFLOWS,
    build_business_ci_attestation_candidate,
    github_actions_business_ci_verifier,
    verify_github_actions_source,
)


SHA = "85cf6b1dc63623b4c054940d96e2b25f0175bc6e"
REFS = [
    "docs/aion/AION_BUSINESS_CERTIFICATION_PACKAGE_V1.md",
    "docs/adr/ADR-0012-business-primary-scope-certification.md",
    "docs/aion/ARCHITECTURE.md",
]


def _product_evidence():
    data = {name: True for name in BUSINESS_REQUIRED_GATES}
    data["evidence_refs"] = list(REFS)
    return data


def _runs(**updates):
    rows = []
    for index, (path, name) in enumerate(REQUIRED_WORKFLOWS.items(), start=1):
        run = {
            "id": 1000 + index,
            "run_attempt": 1,
            "name": name,
            "path": path,
            "event": "pull_request",
            "status": "completed",
            "conclusion": "success",
            "head_sha": SHA,
            "repository_full_name": REPOSITORY_FULL_NAME,
            "html_url": f"https://github.com/example/actions/runs/{1000 + index}",
        }
        if path in updates:
            run.update(updates[path])
        rows.append(run)
    return rows


def _source(**updates):
    data = {
        "repository_full_name": REPOSITORY_FULL_NAME,
        "sha": SHA,
        "quality_test_count": 3872,
        "runs": _runs(),
    }
    data.update(updates)
    return data


class BusinessExternalAttestationTests(unittest.TestCase):
    def test_candidate_is_bound_to_sha_refs_and_fingerprint(self):
        candidate = build_business_ci_attestation_candidate(
            sha=SHA,
            refs=REFS,
            test_count=3872,
        )
        self.assertEqual(candidate["sha"], SHA)
        self.assertEqual(candidate["test_count"], 3872)
        self.assertEqual(candidate["refs"], sorted(REFS))
        self.assertEqual(len(candidate["fingerprint"]), 64)
        self.assertTrue(candidate["tests_passed"])
        self.assertTrue(candidate["evidence_verified"])
        self.assertTrue(candidate["provenance_verified"])

    def test_external_github_source_verifies_all_required_workflows(self):
        candidate = build_business_ci_attestation_candidate(
            sha=SHA,
            refs=REFS,
            test_count=3872,
        )
        checked = verify_github_actions_source(candidate, _source())
        self.assertEqual(checked["state"], "VERIFIED")
        self.assertTrue(checked["valid"])
        self.assertEqual(checked["quality_test_count"], 3872)
        self.assertEqual(set(checked["workflow_states"]), set(REQUIRED_WORKFLOWS))
        self.assertTrue(all(item["verified"] for item in checked["workflow_states"].values()))
        self.assertFalse(checked["provider_called"])
        self.assertFalse(checked["external_write"])
        self.assertFalse(checked["runtime_activated"])

    def test_external_source_fails_closed_for_missing_failed_or_wrong_sha(self):
        candidate = build_business_ci_attestation_candidate(
            sha=SHA,
            refs=REFS,
            test_count=3872,
        )
        missing = _source(runs=_runs()[:-1])
        self.assertEqual(verify_github_actions_source(candidate, missing)["state"], "REJECTED")

        failed_runs = _runs()
        failed_runs[0]["conclusion"] = "failure"
        self.assertEqual(
            verify_github_actions_source(candidate, _source(runs=failed_runs))["state"],
            "REJECTED",
        )

        wrong_sha_runs = _runs()
        wrong_sha_runs[1]["head_sha"] = "0" * 40
        self.assertEqual(
            verify_github_actions_source(candidate, _source(runs=wrong_sha_runs))["state"],
            "REJECTED",
        )

        self.assertEqual(
            verify_github_actions_source(
                candidate,
                _source(repository_full_name="attacker/fork"),
            )["state"],
            "REJECTED",
        )
        self.assertEqual(
            verify_github_actions_source(candidate, _source(quality_test_count=0))["state"],
            "REJECTED",
        )

    def test_latest_attempt_controls_result_for_same_workflow_path(self):
        candidate = build_business_ci_attestation_candidate(
            sha=SHA,
            refs=REFS,
            test_count=3872,
        )
        rows = _runs()
        old_failure = dict(rows[0])
        old_failure["id"] = rows[0]["id"] - 100
        old_failure["run_attempt"] = 0
        old_failure["conclusion"] = "failure"
        checked = verify_github_actions_source(candidate, _source(runs=[old_failure, *rows]))
        self.assertEqual(checked["state"], "VERIFIED")

        newer_failure = dict(rows[0])
        newer_failure["id"] = rows[0]["id"] + 10000
        newer_failure["run_attempt"] = 2
        newer_failure["conclusion"] = "failure"
        checked = verify_github_actions_source(candidate, _source(runs=[*rows, newer_failure]))
        self.assertEqual(checked["state"], "REJECTED")

    def test_reader_backed_verifier_can_move_business_to_tested_only(self):
        candidate = build_business_ci_attestation_candidate(
            sha=SHA,
            refs=REFS,
            test_count=3872,
        )
        calls = []

        def reader(request):
            calls.append(dict(request))
            return _source()

        result = assess_business_certification_package(
            product_evidence=_product_evidence(),
            ci_attestation=candidate,
            human_review_approved=False,
            trusted_ci_verifier=github_actions_business_ci_verifier(reader),
        )
        self.assertEqual(result["state"], "TESTED")
        self.assertEqual(result["technical_state"], "TESTED")
        self.assertEqual(result["certification_state"], "NOT_CERTIFIED")
        self.assertFalse(result["human_review_verified"])
        self.assertFalse(result["runtime_activated"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["repository_full_name"], REPOSITORY_FULL_NAME)
        self.assertEqual(calls[0]["sha"], SHA)

    def test_reader_error_or_malformed_payload_never_verifies(self):
        candidate = build_business_ci_attestation_candidate(
            sha=SHA,
            refs=REFS,
            test_count=3872,
        )

        def explode(_request):
            raise RuntimeError("read failed")

        for reader in (explode, lambda _request: "not-a-mapping", lambda _request: {}):
            with self.subTest(reader=reader):
                verifier = github_actions_business_ci_verifier(reader)
                checked = verifier({
                    "schema": candidate["schema"],
                    "specialist": "BUSINESS",
                    "version": candidate["version"],
                    "suite": candidate["suite"],
                    "provenance": candidate["provenance"],
                    "evidence_id": candidate["evidence_id"],
                    "sha": candidate["sha"],
                    "refs": candidate["refs"],
                    "fingerprint": candidate["fingerprint"],
                })
                self.assertEqual(checked["state"], "REJECTED")
                self.assertFalse(checked["evidence_verified"])
                self.assertFalse(checked["provenance_verified"])
                self.assertFalse(checked["runtime_activated"])

    def test_module_has_no_network_process_or_external_sdk_imports(self):
        source = Path("atlasquant_aion_business_external_attestation.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
