"""A76 NEGATIVE_CHARACTERIZATION. SIMULATED_ONLY / NO AUTHORITY.

No positive authorization mock, witness, Worker tick, persistence or live I/O.
Legacy tests are not modified. Local hashes below are never attestations.
"""
from contextlib import ExitStack
from copy import deepcopy
from datetime import timedelta
import importlib.util
import json
import os
import socket
import time
import unittest
from unittest.mock import Mock, patch

import atlasquant_aion_global_worker_activation as activation
import atlasquant_aion_global_worker_reactivation_gate as gates
import test_atlasquant_aion_global_worker_activation as legacy
import test_atlasquant_aion_global_worker_reactivation_gate as incident
import test_atlasquant_aion_activation_authority_a74 as fixtures

DENIAL = "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED"


class A76ActivationDenialCoverage(unittest.TestCase):
    def setUp(self):
        self.io = ExitStack()
        self.addCleanup(self.io.close)
        self.http = []
        for name in ("get", "post", "patch", "put", "delete", "request"):
            self.http.append(self.io.enter_context(patch(
                "requests." + name, side_effect=AssertionError("A76_NO_NETWORK"))))
        self.http.append(self.io.enter_context(patch(
            "requests.sessions.Session.request", side_effect=AssertionError("A76_NO_NETWORK"))))
        self.http.append(self.io.enter_context(patch.object(
            socket.socket, "connect", side_effect=AssertionError("A76_NO_SOCKET"))))
        self.http.append(self.io.enter_context(patch.object(
            socket.socket, "connect_ex", side_effect=AssertionError("A76_NO_SOCKET"))))
        if importlib.util.find_spec("httpx") is not None:
            for name in ("get", "post", "patch", "put", "delete", "request",
                         "Client.request", "AsyncClient.request"):
                self.http.append(self.io.enter_context(patch(
                    "httpx." + name, side_effect=AssertionError("A76_NO_NETWORK"))))
        self.f = fixtures.A74PlanTicketDenialTests()
        self.f.setUp()  # In-memory historical staging; not plan()/approval().
        self.now = self.f.now
        self.observation = {"class": "NEGATIVE_CHARACTERIZATION",
                            "fixture": "SIMULATED_ONLY_NO_AUTHORITY",
                            "reader_calls": 0, "writer_calls": 0,
                            "disabler_calls": 0}

    def tearDown(self):
        self.observation["http_socket_calls"] = sum(m.call_count for m in self.http)
        self.assertEqual(self.observation["http_socket_calls"], 0)

    def expect(self, result, reason, *, field="status"):
        self.observation.update(expected_reason=reason,
                                observed_reason=result.get("reason"),
                                observed_state=result.get(field))
        self.assertEqual(result[field], "BLOCKED")
        self.assertEqual(result["reason"], reason)
        self.assertNotIn("plan", result)
        self.assertNotIn("approval", result)
        for key in ("feature_flag_modified", "global_worker_executed"):
            if key in result:
                self.assertIs(result[key], False)

    def plan(self, readiness=None, flag=None, runtime=None, gate=None):
        r = self.f.fixture.runtime if runtime is None else runtime
        before = deepcopy(r)
        result = activation.prepare_global_worker_activation_plan(
            self.f.fixture.access, r,
            self.f.fixture.readiness if readiness is None else readiness,
            legacy._safe_flag("UNSET") if flag is None else flag,
            reactivation_gate=gate, now=self.now)
        self.assertEqual(r, before)
        return result

    def run_readiness(self, mode):
        r = deepcopy(self.f.fixture.readiness)
        if mode in ("false", "true"):
            for key in ("source_authenticity_verified", "independent_witness_verified",
                        "source_resource_owner_bound", "external_activation_allowed"):
                r[key] = mode == "true"
        if mode in ("past", "future"):
            r["checked_at"] = (self.now + timedelta(days=-365 if mode == "past" else 365)).isoformat()
        before = deepcopy(r)
        self.assertEqual(activation._readiness_local_diagnostic(r)["state"], "READY")
        self.expect(activation._readiness_contract(r), DENIAL, field="state")
        self.expect(self.plan(readiness=r), DENIAL)
        self.assertEqual(r, before)

    def run_flag(self, mode):
        flag = legacy._safe_flag("UNSET")
        if mode in ("ENABLED", "UNKNOWN"):
            flag = legacy._safe_flag(mode)
        elif mode == "unconfirmed":
            flag["status"] = "UNKNOWN"
        elif mode == "missing_safe":
            del flag["safe_for_arming_persistence"]
        elif mode == "false_safe":
            flag["safe_for_arming_persistence"] = False
        elif mode == "changed":
            flag = legacy._safe_flag("DISABLED")
        reason = "READINESS_FLAG_EVIDENCE_CHANGED" if mode == "changed" else "FEATURE_FLAG_NOT_PROVEN_DISABLED"
        self.expect(self.plan(flag=flag), reason)

    def run_approval(self, mode):
        plan = self.f.legacy_plan()
        self.assertEqual(activation.plan_integrity(plan)["state"], "MATCH")
        reason = DENIAL
        confirmation, phrase = True, activation.CONFIRMATION_PHRASE
        if mode == "confirmation":
            confirmation, reason = False, "EXPLICIT_CONFIRMATION_REQUIRED"
        elif mode == "phrase":
            phrase, reason = "WRONG", "CONFIRMATION_PHRASE_MISMATCH"
        elif mode == "expired":
            plan["expires_at"] = self.now.isoformat()
            reason = "ACTIVATION_PLAN_EXPIRED"
        elif mode in ("actor", "scope"):
            plan["actor_id" if mode == "actor" else "scope"] = "OTHER" if mode == "actor" else ["TENANT_B"]
            reason = "ACTIVATION_PLAN_CONTEXT_MISMATCH"
        elif mode == "tamper":
            plan["runtime_sha"] = "changed_without_rehash"
            reason = "ACTIVATION_PLAN_INTEGRITY_MISMATCH"
        if mode != "tamper":
            plan["plan_digest"] = activation._payload_digest(plan, "plan_digest")
        before = deepcopy(plan)
        result = activation.approve_global_worker_activation_plan(
            self.f.fixture.access, plan, confirmation=confirmation,
            confirmation_phrase=phrase, now=self.now)
        self.expect(result, reason)
        self.assertEqual(plan, before)

    def run_ticket(self, mode):
        ticket = self.f.legacy_ticket()
        runtime = deepcopy(self.f.fixture.runtime)
        access = deepcopy(self.f.fixture.access)
        reason = DENIAL
        if mode in ("actor", "scope", "fingerprint", "session", "tenant"):
            reason = "ACTIVATION_APPROVAL_CONTEXT_MISMATCH"
            if mode in ("actor", "scope"):
                ticket["actor_id" if mode == "actor" else "scope"] = "OTHER" if mode == "actor" else ["TENANT_B"]
            elif mode == "session":
                access["session"]["username"] = "other-workspace"
            else:
                access["session"]["credential_fingerprint"] = "TENANT_B_ROTATED_FINGERPRINT_123456789"
        elif mode == "sha":
            runtime["sha"], reason = "changed", "ACTIVATION_APPROVAL_RUNTIME_SHA_CHANGED"
        elif mode == "checkpoint":
            runtime["checkpoint"]["simulated_extra"] = "changed"
            reason = "ACTIVATION_APPROVAL_RUNTIME_DIGEST_CHANGED"
        elif mode in ("arm_digest", "arming_plan_digest", "arming_approval_digest"):
            ticket[mode] = "changed"
            reason = "ACTIVATION_APPROVAL_ARMING_STATE_CHANGED"
        elif mode == "expired":
            ticket["expires_at"] = self.now.isoformat()
            reason = "ACTIVATION_APPROVAL_EXPIRED"
        elif mode == "tamper":
            ticket["runtime_sha"] = "changed_without_rehash"
            reason = "ACTIVATION_APPROVAL_INTEGRITY_MISMATCH"
        elif mode == "phrase":
            ticket["confirmation_phrase_digest"] = "changed"
            reason = "ACTIVATION_APPROVAL_CONFIRMATION_PROOF_MISMATCH"
        if mode != "tamper":
            ticket["approval_digest"] = activation._payload_digest(ticket, "approval_digest")
            self.assertEqual(activation.approval_integrity(ticket)["state"], "MATCH")
        before = deepcopy((ticket, runtime, access))
        for _ in range(3 if mode == "replay" else 1):
            self.expect(activation.validate_global_worker_activation_approval(
                access, runtime, ticket, now=self.now), reason, field="state")
        self.assertEqual((ticket, runtime, access), before)

    def run_wrapper(self, mode):
        ticket = self.f.legacy_ticket()
        fresh = deepcopy(self.f.fixture.runtime)
        reason = DENIAL
        if mode == "sha":
            fresh["sha"], reason = "changed", "ACTIVATION_APPROVAL_RUNTIME_SHA_CHANGED"
        elif mode == "checkpoint":
            fresh["checkpoint"]["simulated_extra"] = "changed"
            reason = "ACTIVATION_APPROVAL_RUNTIME_DIGEST_CHANGED"
        elif mode == "no_confirmation":
            reason = "FINAL_EXPLICIT_CONFIRMATION_REQUIRED"
        reader = Mock(return_value=fresh)
        flag_reader = Mock(side_effect=AssertionError("FLAG_READ_UNREACHABLE"))
        writer = Mock(side_effect=AssertionError("WRITER_FORBIDDEN"))
        disabler = Mock(side_effect=AssertionError("DISABLER_UNEXPECTED"))
        result = activation.activate_global_worker_feature_flag(
            self.f.fixture.access, self.f.fixture.runtime, ticket, legacy._config(),
            confirmation=mode != "no_confirmation", now=self.now,
            runtime_reader=reader, flag_reader=flag_reader,
            flag_writer=writer, flag_disabler=disabler)
        self.expect(result, reason)
        self.assertEqual(reader.call_count, 0 if mode == "no_confirmation" else 1)
        flag_reader.assert_not_called()
        writer.assert_not_called()
        disabler.assert_not_called()
        self.observation.update(reader_calls=reader.call_count, writer_calls=writer.call_count,
                                disabler_calls=disabler.call_count, flag_reader_calls=flag_reader.call_count)

    def run_writer(self, state):
        self.expect(activation.write_repository_feature_flag_enabled(legacy._config(), state), DENIAL)

    def run_gate(self, mode):
        runtime, original_incident = incident._post_incident_runtime()
        readiness, flag = incident._readiness(), incident._safe_flag()
        snapshot = incident._safe_reconciled_snapshot(runtime)
        gate = gates.assess_post_incident_reactivation_gate(
            runtime, snapshot, readiness, flag, now=incident.NOW)
        self.assertEqual(gates.gate_integrity(gate)["state"], "MATCH")
        self.assertIs(gate["reactivation_authorized"], False)
        approval = {"post_incident_gate_required": True,
                    "post_incident_closure_ledger_digest": gate["closure_ledger_digest"],
                    "post_incident_latest_closure_record_id": gate["latest_closure_record_id"]}
        # This is a gate-binding DTO, not an operational approval ticket.
        self.observation["isolated_gate_only"] = True
        if mode == "green":
            p = gates.validate_reactivation_gate_for_plan(runtime, readiness, flag, gate, now=incident.NOW)
            e = gates.validate_reactivation_gate_for_execution(runtime, flag, approval, gate, now=incident.NOW)
            self.assertEqual(p["state"], "READY")
            self.assertEqual(e["state"], "READY")
            self.assertIs(e["reactivation_authorized"], False)
            result = activation.prepare_global_worker_activation_plan(
                incident._access(), runtime, readiness, flag, reactivation_gate=gate, now=incident.NOW)
            self.expect(result, DENIAL)
            return
        if mode == "reopened":
            reopened = deepcopy(original_incident)
            reopened["generated_at"] = (incident.NOW + timedelta(seconds=10)).isoformat()
            snapshot = incident.reconcile_global_worker_incident_center(
                {}, reopened, runtime, now=incident.NOW + timedelta(seconds=10))
            bad = gates.assess_post_incident_reactivation_gate(
                runtime, snapshot, readiness, flag, now=incident.NOW + timedelta(seconds=10))
            self.assertEqual(bad["status"], gates.BLOCKED_STATUS)
            self.expect(gates.validate_reactivation_gate_for_execution(
                runtime, flag, approval, bad, now=incident.NOW + timedelta(seconds=10)),
                "FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH", field="state")
            return
        expected = ""
        if mode == "missing":
            gate, expected = None, "POST_INCIDENT_REACTIVATION_GATE_INTEGRITY_MISMATCH"
        elif mode == "expired":
            gate["expires_at"] = incident.NOW.isoformat()
            expected = "POST_INCIDENT_REACTIVATION_GATE_EXPIRED"
        elif mode in ("runtime_sha", "runtime_checkpoint_digest", "closure_ledger_digest", "latest_closure_record_id"):
            gate[mode] = "swapped"
            expected = {"runtime_sha": "POST_INCIDENT_GATE_RUNTIME_SHA_CHANGED",
                        "runtime_checkpoint_digest": "POST_INCIDENT_GATE_RUNTIME_DIGEST_CHANGED",
                        "closure_ledger_digest": "POST_INCIDENT_GATE_LEDGER_CHANGED",
                        "latest_closure_record_id": "POST_INCIDENT_GATE_LATEST_CLOSURE_CHANGED"}[mode]
        elif mode == "flag":
            flag = incident._safe_flag("UNSET")
            expected = "POST_INCIDENT_GATE_FLAG_STATE_CHANGED"
        elif mode == "readiness_time":
            readiness["checked_at"] = (incident.NOW + timedelta(seconds=1)).isoformat()
            expected = "POST_INCIDENT_GATE_READINESS_CHANGED"
        if gate is not None:
            gate["gate_digest"] = gates._payload_digest(gate, "gate_digest")
        self.expect(gates.validate_reactivation_gate_for_plan(
            runtime, readiness, flag, gate, now=incident.NOW), expected, field="state")
        execution_reasons = {
            "missing": "FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH",
            "expired": "FRESH_POST_INCIDENT_GATE_EXPIRED",
            "runtime_sha": "FRESH_POST_INCIDENT_GATE_RUNTIME_SHA_CHANGED",
            "runtime_checkpoint_digest": "FRESH_POST_INCIDENT_GATE_RUNTIME_DIGEST_CHANGED",
            "closure_ledger_digest": "FRESH_POST_INCIDENT_GATE_LEDGER_CHANGED",
            "latest_closure_record_id": "FRESH_POST_INCIDENT_GATE_LATEST_CLOSURE_CHANGED",
            "flag": "FRESH_POST_INCIDENT_GATE_FLAG_STATE_CHANGED",
        }
        if mode in execution_reasons:
            self.expect(gates.validate_reactivation_gate_for_execution(
                runtime, flag, approval, gate, now=incident.NOW),
                execution_reasons[mode], field="state")
        if mode == "missing":
            self.expect(activation.prepare_global_worker_activation_plan(
                incident._access(), runtime, readiness, flag, now=incident.NOW), expected)


# Distinct unittest identities, not subtests inflated into method counts.
MATRIX = {
    "readiness": ("missing", "false", "true", "past", "future"),
    "flag": ("ENABLED", "UNKNOWN", "unconfirmed", "missing_safe", "false_safe", "changed"),
    "approval": ("coherent", "confirmation", "phrase", "expired", "actor", "scope", "tamper"),
    "ticket": ("coherent", "replay", "actor", "scope", "fingerprint", "session", "tenant",
               "sha", "checkpoint", "arm_digest", "arming_plan_digest", "arming_approval_digest",
               "expired", "tamper", "phrase"),
    "wrapper": ("no_confirmation", "coherent", "sha", "checkpoint"),
    "writer": ("UNSET", "DISABLED"),
    "gate": ("green", "missing", "expired", "reopened", "runtime_sha",
             "runtime_checkpoint_digest", "closure_ledger_digest", "latest_closure_record_id",
             "flag", "readiness_time"),
}


def _case(group, mode):
    def check(self):
        self.observation.update(group=group, case=mode)
        getattr(self, "run_" + group)(mode)
    check.__doc__ = "SIMULATED_ONLY " + group + "/" + mode
    return check


for _group, _modes in MATRIX.items():
    for _mode in _modes:
        setattr(A76ActivationDenialCoverage, "test_" + _group + "_" + _mode, _case(_group, _mode))


class EvidenceResult(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()

    def _record(self, test, status, error=None):
        row = {"test": test.id(), "status": status,
               "seconds": time.monotonic() - self.started,
               "observation": getattr(test, "observation", {})}
        if error:
            row["traceback"] = self._exc_info_to_string(error, test)
        self.records.append(row)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "PASS")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "FAIL", err)

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "ERROR", err)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._record(subtest, "SUBTEST_FAIL_OR_ERROR", err)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    modules = ["test_atlasquant_aion_activation_denial_coverage_a76",
               "test_atlasquant_aion_f1_t1_untrusted_witness_intake_a75",
               "test_atlasquant_aion_activation_authority_a74",
               "test_atlasquant_aion_readiness_source_witness_a73",
               "test_atlasquant_aion_inflight_attempt_a72",
               "test_atlasquant_aion_inflight_receipt_safety_a71",
               "test_atlasquant_aion_inflight_untrusted_receipts_a58"]
    if "--legacy" in sys.argv:
        modules = ["test_atlasquant_aion_global_worker_activation",
                   "test_atlasquant_aion_global_worker_reactivation_gate"]
    if "--canonical" in sys.argv:
        # Read the exact versioned A74 selection, without rewriting old tests.
        import shlex
        source = Path(".github/workflows/aion-a74-full-quality-security-lab.yml").read_text(encoding="utf-8")
        commands = source.split("python -m unittest -q \\\n")[1:]
        index = 1 if "--security" in sys.argv else 0
        raw = commands[index].split("\n  full-security-original-selection:")[0]
        modules = shlex.split(raw.replace("\\\n", " ").strip())
        modules = [x[:-3].replace("/", ".") if x.endswith(".py") else x for x in modules]
    EvidenceResult.records = []
    with ExitStack() as guard:
        for name in ("get", "post", "patch", "put", "delete", "request"):
            guard.enter_context(patch("requests." + name, side_effect=AssertionError("A76_NO_NETWORK")))
        guard.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("A76_NO_NETWORK")))
        guard.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("A76_NO_SOCKET")))
        guard.enter_context(patch.object(socket.socket, "connect_ex", side_effect=AssertionError("A76_NO_SOCKET")))
        if importlib.util.find_spec("httpx") is not None:
            for name in ("get", "post", "patch", "put", "delete", "request", "Client.request", "AsyncClient.request"):
                guard.enter_context(patch("httpx." + name, side_effect=AssertionError("A76_NO_NETWORK")))
        result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(
            unittest.defaultTestLoader.loadTestsFromNames(modules))
    if os.environ.get("A76_REPORT"):
        Path(os.environ["A76_REPORT"]).write_text(json.dumps({
            "os": sys.platform, "python": sys.version, "head": os.environ.get("A76_HEAD"),
            "tests": result.testsRun, "failures": len(result.failures),
            "errors": len(result.errors), "skips": len(result.skipped),
            "records": result.records}, indent=2), encoding="utf-8")
    sys.exit(not result.wasSuccessful())
