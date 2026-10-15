"""A79 SIMULATED_ONLY. No producer, signature, witness or external action.

Local SQLite fixture tampering/restoration is an adversarial input, not an
independent receipt. Passing characterization never establishes H0 custody.
"""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import multiprocessing
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
import atlasquant_aion_producer_receipt_untrusted_precheck as shape
import test_atlasquant_aion_producer_receipt_untrusted_precheck as prior

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
SCOPE = Scope("SIMULATED-owner", "SIMULATED-tenant-a", "SIMULATED-workspace-a")
DENIAL = "INDEPENDENT_PRODUCER_NOT_ENROLLED"


def no_network(stack):
    spies = []
    if importlib.util.find_spec("requests"):
        for name in ("get", "post", "patch", "put", "delete", "request", "sessions.Session.request"):
            spies.append(stack.enter_context(patch("requests." + name,
                side_effect=AssertionError("A79_NO_EXTERNAL_IO"))))
    if importlib.util.find_spec("httpx"):
        for name in ("get", "post", "patch", "put", "delete", "request", "Client.request", "AsyncClient.request"):
            spies.append(stack.enter_context(patch("httpx." + name,
                side_effect=AssertionError("A79_NO_EXTERNAL_IO"))))
    for name in ("connect", "connect_ex"):
        spies.append(stack.enter_context(patch.object(socket.socket, name,
            side_effect=AssertionError("A79_NO_SOCKET"))))
    return spies


def local_policy(decision):
    # Necessary local policy fields only, NOT independent authority or H0.
    return {"allowed": True, "actor_id": SCOPE.owner_id,
            "tenant_id": SCOPE.tenant_id, "workspace_id": SCOPE.workspace_id,
            "policy_version": "SIMULATED-policy", "authorization_ref": "SIMULATED-approval"}


def enqueue(outbox, *, ref="SIMULATED-intent", aggregate="SIMULATED-aggregate", **extra):
    return outbox.enqueue(intent_ref=ref, action="SIMULATED_ACTION",
        payload={"SIMULATED_ONLY": True}, aggregate_key=aggregate,
        policy_version="SIMULATED-policy", authorization_ref="SIMULATED-approval",
        created_at=NOW, valid_until=NOW + timedelta(minutes=5), **extra)


class TrapAdapter:
    def __init__(self, result=None):
        self.getters = []
        self.calls = []
        self.result = result

    @property
    def send(self):
        self.getters.append("send")
        def callback(*args, **kwargs):
            self.calls.append("send")
            return self.result
        return callback

    @property
    def reconcile(self):
        self.getters.append("reconcile")
        def callback(*args, **kwargs):
            self.calls.append("reconcile")
            return self.result
        return callback

    @property
    def compensate(self):
        self.getters.append("compensate")
        raise AssertionError("COMPENSATION_FORBIDDEN")


def child_attempt(path, worker, start, conn):
    """Spawned offline process; opens ONLY the parent's disposable fixture DB."""
    store = None
    try:
        with ExitStack() as guard:
            no_network(guard)
            start.wait(20)
            store = SQLiteChatStore(path)
            outbox = ExecutionOutbox(store, SCOPE)
            row = outbox.claim_next(worker, now=NOW, lease_seconds=60)
            adapter = TrapAdapter({"confirmed": True, "signature_verified": True})
            reason = "NO_CLAIM"
            if row is not None:
                try:
                    outbox.dispatch_claimed(row["idempotency_key"], worker_id=worker,
                        authorize=local_policy, adapter=adapter, now=NOW)
                except PermissionError as exc:
                    reason = str(exc)
            conn.send({"claimed": row is not None, "reason": reason,
                       "getters": adapter.getters, "calls": adapter.calls,
                       "effects": outbox.effect_count()})
    except BaseException as exc:
        conn.send({"ERROR": type(exc).__name__})
    finally:
        if store is not None:
            store.close()
        conn.close()


class A79CausalDenialTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.network = no_network(self.stack)
        root = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="a79_"))
        self.path = Path(root) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(lambda: self.store.close())
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.observation = {"class": "NEGATIVE_CHARACTERIZATION",
                            "fixture": "SIMULATED_ONLY_NO_AUTHORITY",
                            "adapter_getters": [], "send": 0, "reconcile": 0,
                            "compensate": 0}

    def tearDown(self):
        self.observation["http_socket_calls"] = sum(m.call_count for m in self.network)
        self.assertEqual(self.observation["http_socket_calls"], 0)

    def inspect(self, claim, binding, expected):
        result = shape.inspect_untrusted_receipt_shape(claim, binding)
        self.assertEqual(result["reason"], expected)
        prior.assert_denied(self, result)
        self.observation.update(status=result["status"], reason=result["reason"],
                                shape_matched=result["shape_matched"])
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.outbox.list(), [])

    def run_binding(self, field):
        claim, binding = prior.synthetic_claim(), deepcopy(prior.BOUND)
        claim[field] = claim[field] + 1 if type(claim[field]) is int else (
            "f" * 64 if field in {"intent_digest", "witness_head"} else "SIMULATED-other")
        self.inspect(claim, binding, "LOCAL_BINDING_MISMATCH_" + field.upper())

    def run_shape(self, mode):
        claim, binding = prior.synthetic_claim(), deepcopy(prior.BOUND)
        expected = "INDEPENDENT_PRODUCER_AND_WITNESS_NOT_ENROLLED"
        if mode == "negative":
            claim = prior.synthetic_claim(shape.NEGATIVE)
        elif mode == "false_signature_flag":
            claim["signature_verified"] = False
            expected = "CLAIM_FIELDS_MISMATCH"
        elif mode == "true_signature_flag":
            claim["signature_verified"] = True
            expected = "CLAIM_FIELDS_MISMATCH"
        elif mode in ("bool_counter", "negative_counter"):
            claim["attempt"] = True if mode == "bool_counter" else -1
            expected = "INVALID_CLAIM_ATTEMPT"
        elif mode == "huge_counter":
            claim["epoch"] = binding["epoch"] = 2 ** 1024
        elif mode == "unicode":
            claim["owner_id"] = "SIMULATED-owne\u0301r"
            expected = "INVALID_BINDING_TOKEN_OWNER_ID"
        elif mode in ("future", "past"):
            claim["issued_at"] = "2099-01-01T00:00:00Z" if mode == "future" else "2020-01-01T00:00:00Z"
        elif mode == "naive":
            claim["issued_at"] = "2026-10-14T12:00:00"
            expected = "INVALID_UTC_TIMESTAMP"
        elif mode == "bad_signature":
            claim["claimed_signature"] = "not-a-signature"
            expected = "INVALID_CLAIMED_SIGNATURE_SHAPE"
        elif mode == "extra":
            claim["retry_authorized"] = True
            expected = "CLAIM_FIELDS_MISMATCH"
        elif mode == "dict_subclass":
            class Evil(dict):
                def get(self, *args):
                    raise AssertionError("getter executed")
            claim = Evil(claim)
            expected = "CLAIM_MUST_BE_PLAIN_DICT"
        elif mode == "evil_value":
            class Evil:
                def __eq__(self, other):
                    raise AssertionError("comparison executed")
                def __str__(self):
                    raise AssertionError("conversion executed")
            claim["owner_id"] = Evil()
            expected = "INVALID_BINDING_TYPE_OWNER_ID"
        elif mode == "evil_key":
            class EvilKey:
                def __hash__(self):
                    return hash("kind")
                def __eq__(self, other):
                    raise AssertionError("key equality executed")
            claim = {EvilKey(): "POSITIVE_COMMITTED"}
            expected = "CLAIM_KEY_NOT_STRING"
        self.inspect(claim, binding, expected)

    def claim(self):
        item = enqueue(self.outbox)
        row = self.outbox.claim_next("SIMULATED-worker", now=NOW, lease_seconds=5)
        self.assertEqual(item["idempotency_key"], row["idempotency_key"])
        return row

    def dispatch(self, row, *, adapter=None, policy=local_policy, when=NOW, worker="SIMULATED-worker"):
        adapter = TrapAdapter() if adapter is None else adapter
        with self.assertRaisesRegex(PermissionError, "^" + DENIAL + "$"):
            self.outbox.dispatch_claimed(row["idempotency_key"], worker_id=worker,
                authorize=policy, adapter=adapter, now=when)
        self.assertEqual(adapter.getters, [])
        self.assertEqual(adapter.calls, [])
        current = self.outbox.get(row["idempotency_key"])
        self.assertEqual(current["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.observation.update(status=current["state"], reason=current["last_error"],
                                attempts=current["attempts"], effects=0)

    def run_outcome(self, mode):
        row = self.claim()
        fake = {"status": mode, "confirmed": True, "accepted": True,
                "signature_verified": True, "authoritative_absence": True,
                "effect_ref": "SIMULATED-FAKE", "retry_authorized": True}
        if mode in ("SENT", "CONFIRMED", "RETRYABLE"):
            self.dispatch(row, adapter=TrapAdapter(fake))
            return
        state = "SENT" if mode == "SENT_RECONCILE" else "UNCERTAIN"
        with self.outbox.db:
            self.outbox.db.execute("UPDATE action_outbox SET state=? WHERE idempotency_key=?",
                                   (state, row["idempotency_key"]))
        before = tuple(self.outbox.db.iterdump())
        fake.update(found=mode == "COMMITTED", claimed_receipt=prior.synthetic_claim(
            shape.NEGATIVE if mode in ("NO_EFFECT", "404", "EMPTY") else shape.POSITIVE))
        adapter = TrapAdapter(fake)
        authorize = Mock(side_effect=AssertionError("AUTH_NOT_NEEDED_FOR_DENIED_RECONCILE"))
        with self.assertRaisesRegex(PermissionError, "^" + DENIAL + "$"):
            self.outbox.reconcile(row["idempotency_key"], adapter=adapter,
                                  authorize=authorize, now=NOW)
        self.assertEqual(adapter.getters, [])
        self.assertEqual(adapter.calls, [])
        authorize.assert_not_called()
        self.assertEqual(tuple(self.outbox.db.iterdump()), before)
        self.observation.update(status=state, reason=DENIAL, database_changed=False)

    def run_recovery(self, mode):
        row = self.claim()
        key = row["idempotency_key"]
        if mode == "expired_lease":
            next_row = self.outbox.claim_next("SIMULATED-worker2", now=NOW+timedelta(seconds=6))
            self.assertEqual(next_row["attempts"], 2)
            self.dispatch(next_row, when=NOW+timedelta(seconds=6), worker="SIMULATED-worker2")
            return
        if mode in ("UNKNOWN", "restart_UNKNOWN"):
            with self.outbox.db:
                self.outbox.db.execute("UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?", (key,))
            if mode == "restart_UNKNOWN":
                self.store.close()
                self.store = SQLiteChatStore(self.path)
                self.outbox = ExecutionOutbox(self.store, SCOPE)
            self.assertIsNone(self.outbox.claim_next("SIMULATED-second", now=NOW+timedelta(seconds=60)))
            adapter = TrapAdapter({"found": False, "authoritative_absence": True})
            with self.assertRaisesRegex(PermissionError, DENIAL):
                self.outbox.reconcile(key, adapter=adapter, authorize=local_policy, now=NOW)
            self.assertEqual(adapter.getters, [])
            self.assertEqual(self.outbox.get(key)["state"], "UNCERTAIN")
        elif mode == "blocked_restart":
            self.dispatch(row)
            self.store.close()
            self.store = SQLiteChatStore(self.path)
            self.outbox = ExecutionOutbox(self.store, SCOPE)
            self.assertIsNone(self.outbox.claim_next("SIMULATED-second", now=NOW+timedelta(seconds=60)))
        elif mode == "snapshot_restore":
            backup_path = self.path.parent / "pre-denial.sqlite3"
            backup = sqlite3.connect(backup_path)
            self.store.db.backup(backup)
            backup.close()
            self.dispatch(row)
            # Joint local rollback is not detectable as independent history.
            restore = sqlite3.connect(backup_path)
            restore.backup(self.store.db)
            restore.close()
            self.assertEqual(self.outbox.get(key)["state"], "CLAIMED")
            self.dispatch(self.outbox.get(key))
            self.observation["rollback_detected"] = False
        elif mode == "missing_first_row":
            with self.outbox.db:
                self.outbox.db.execute("DELETE FROM action_outbox WHERE idempotency_key=?", (key,))
            with self.assertRaises(LookupError):
                self.outbox.dispatch_claimed(key, worker_id="SIMULATED-worker", adapter=TrapAdapter(),
                                            authorize=local_policy, now=NOW)
        elif mode == "confirm_direct":
            before = tuple(self.outbox.db.iterdump())
            with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"):
                self.outbox._confirm(key, expected=row, effect_ref="SIMULATED-FAKE",
                                     confirmed_at=NOW, result={"signature_verified": True})
            self.assertEqual(tuple(self.outbox.db.iterdump()), before)
        elif mode == "idempotent":
            duplicate = enqueue(self.outbox)
            self.assertEqual(duplicate["idempotency_key"], key)
            self.assertEqual(duplicate["enqueue_state"], "IDEMPOTENT")
            self.dispatch(row)
        elif mode in ("second_process_claim", "second_process_unknown"):
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            children, pipes = [], []
            # Raw local fixture: neither PENDING nor UNKNOWN authorizes send.
            with self.outbox.db:
                self.outbox.db.execute("UPDATE action_outbox SET state=?,lease_owner='',lease_until='' WHERE idempotency_key=?",
                                      ("UNCERTAIN" if mode == "second_process_unknown" else "PENDING", key))
            try:
                for i in range(4):
                    recv, send = ctx.Pipe(duplex=False)
                    process = ctx.Process(target=child_attempt, args=(str(self.path), "SIMULATED-p"+str(i), ready, send))
                    process.start()
                    send.close()
                    children.append(process)
                    pipes.append(recv)
                ready.set()
                results = []
                for pipe in pipes:
                    self.assertTrue(pipe.poll(40), "child timeout")
                    results.append(pipe.recv())
                for process in children:
                    process.join(10)
                    self.assertEqual(process.exitcode, 0)
                self.assertEqual(sum(r.get("claimed", False) for r in results), 0 if mode == "second_process_unknown" else 1)
                self.assertTrue(all("ERROR" not in r for r in results))
                self.assertTrue(all(r["getters"] == [] and r["calls"] == [] and r["effects"] == 0 for r in results))
                self.assertEqual(self.outbox.get(key)["state"], "UNCERTAIN" if mode == "second_process_unknown" else "BLOCKED_PRODUCER")
                self.observation["process_results"] = results
            finally:
                for process in children:
                    if process.is_alive():
                        process.terminate()
                    process.join(10)
                for pipe in pipes:
                    pipe.close()
        self.assertEqual(self.outbox.effect_count(), 0)
        self.observation.update(status=self.outbox.get(key)["state"] if mode != "missing_first_row" else "ROW_ABSENT",
                                reason="NO_EXTERNAL_PROOF_NO_SEND", effects=0)

    def run_scope(self, field):
        row = self.claim()
        def wrong(decision):
            value = local_policy(decision)
            value[field] = "SIMULATED-other"
            return value
        result = self.outbox.dispatch_claimed(row["idempotency_key"], worker_id="SIMULATED-worker",
            authorize=wrong, adapter=TrapAdapter(), now=NOW)
        expected = {"actor_id": "ACTOR_MISMATCH", "tenant_id": "TENANT_ID_MISMATCH",
                    "workspace_id": "WORKSPACE_ID_MISMATCH", "policy_version": "POLICY_VERSION_CHANGED",
                    "authorization_ref": "AUTHORIZATION_CHANGED"}[field]
        self.assertEqual(result["last_error"], expected)
        self.assertIn(result["state"], {"REVOKED", "BLOCKED_REAPPROVAL"})
        self.assertEqual(self.outbox.effect_count(), 0)
        self.observation.update(status=result["state"], reason=expected)

    def run_saga(self, mode):
        from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
        from atlasquant_aion_execution_saga import ExecutionSagaCoordinator
        budget = CumulativeAuthorityBudget(self.store, SCOPE,
            authority_budget_ref="SIMULATED-budget", policy_version="SIMULATED-policy")
        saga = ExecutionSagaCoordinator(self.store, SCOPE, outbox=self.outbox, authority_budget=budget)
        saga.create(saga_id="SIMULATED-saga", steps=[{
            "step_key": "one", "action": "SIMULATED_ACTION", "payload": {"SIMULATED_ONLY": True},
            "capability_class": "LOW_RISK", "risk_points": 1, "reversible": True,
            "compensation_action": "SIMULATED_UNDO", "compensation_payload": {},
            "compensation_risk_points": 1}], created_at=NOW)
        item = saga.enqueue_next("SIMULATED-saga", authorization_ref="SIMULATED-approval",
                                 valid_until=NOW+timedelta(minutes=5), created_at=NOW)
        key = saga.get("SIMULATED-saga")["steps"][0]["outbox_key"]
        state = mode.replace("comp_", "")
        with self.outbox.db:
            self.outbox.db.execute("UPDATE action_outbox SET state=? WHERE idempotency_key=?", (state, key))
            if mode.startswith("comp_"):
                self.outbox.db.execute("UPDATE aion_execution_saga_steps SET compensation_outbox_key=? WHERE saga_id=?",
                                      (key, "SIMULATED-saga"))
        before = tuple(self.store.db.iterdump())
        expected = ("INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED" if state == "CONFIRMED"
                    else "INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED")
        if mode.startswith("comp_") and state not in {"CONFIRMED", "FAILED"}:
            expected = "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED"
        call = saga.sync_compensation_outcome if mode.startswith("comp_") else saga.sync_forward_outcome
        with self.assertRaisesRegex(PermissionError, "^"+expected+"$"):
            call("SIMULATED-saga", "one", now=NOW)
        self.assertEqual(tuple(self.store.db.iterdump()), before)
        self.assertEqual(self.outbox.effect_count(), 0)
        self.observation.update(status="DENIED", reason=expected, database_changed=False,
                                raw_sql_fixture=True, root_closed=False)

    def test_first_intent_rollback_does_not_license_send(self):
        self.store.db.executescript("CREATE TRIGGER simulated_abort BEFORE INSERT ON action_outbox BEGIN SELECT RAISE(ABORT,'SIMULATED_ABORT'); END;")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "SIMULATED_ABORT"):
            enqueue(self.outbox)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM action_decisions").fetchone()[0], 0)
        self.assertEqual(self.outbox.list(), [])
        self.store.db.execute("DROP TRIGGER simulated_abort")
        # Local H0/H1 window remains indistinguishable; no send is admitted.
        row = self.claim()
        self.dispatch(row)
        self.observation["first_local_intent_retry_possible"] = True

    def test_reconcile_and_dispatch_on_unknown_race_stay_non_effectful(self):
        from concurrent.futures import ThreadPoolExecutor
        row = self.claim()
        key = row["idempotency_key"]
        with self.store.db:
            self.store.db.execute("UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?", (key,))
        def attempt(which):
            store = SQLiteChatStore(self.path)
            try:
                box, adapter = ExecutionOutbox(store, SCOPE), TrapAdapter()
                try:
                    if which == "reconcile":
                        box.reconcile(key, adapter=adapter, authorize=local_policy, now=NOW)
                    else:
                        box.dispatch_claimed(key, worker_id="SIMULATED-worker",
                                             adapter=adapter, authorize=local_policy, now=NOW)
                except (ValueError, PermissionError) as exc:
                    return type(exc).__name__, str(exc), adapter.getters, adapter.calls
                raise AssertionError("unexpected admission")
            finally:
                store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["reconcile", "dispatch"]))
        self.assertEqual(results[0], ("PermissionError", DENIAL, [], []))
        self.assertEqual(results[1], ("ValueError", "intent must be CLAIMED before dispatch", [], []))
        self.assertEqual(self.outbox.get(key)["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.observation.update(status="UNCERTAIN", reason="NO_REENTRY", concurrent_results=results)

    def test_contradictory_claims_same_attempt_neither_unlocks(self):
        row = self.claim()
        key = row["idempotency_key"]
        claims = [prior.synthetic_claim(shape.POSITIVE), prior.synthetic_claim(shape.NEGATIVE)]
        for claim in claims:
            result = shape.inspect_untrusted_receipt_shape(claim, deepcopy(prior.BOUND))
            prior.assert_denied(self, result)
            self.assertIs(result["shape_matched"], True)
        with self.store.db:
            self.store.db.execute("UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?", (key,))
        adapter = TrapAdapter({"claims": claims, "confirmed": True, "authoritative_absence": True})
        with self.assertRaisesRegex(PermissionError, DENIAL):
            self.outbox.reconcile(key, adapter=adapter, authorize=local_policy, now=NOW)
        self.assertEqual(adapter.getters, [])
        self.assertEqual(self.outbox.get(key)["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.observation.update(status="UNCERTAIN", reason=DENIAL, contradictory_claims_untrusted=True)


MATRIX = {
    "binding": tuple(prior.BOUND),
    "shape": ("positive", "negative", "false_signature_flag", "true_signature_flag",
              "bool_counter", "negative_counter", "huge_counter", "unicode", "future", "past",
              "naive", "bad_signature", "extra", "dict_subclass", "evil_value", "evil_key"),
    "outcome": ("SENT", "CONFIRMED", "RETRYABLE", "COMMITTED", "NO_EFFECT", "404", "EMPTY", "UNKNOWN", "SENT_RECONCILE"),
    "recovery": ("expired_lease", "UNKNOWN", "restart_UNKNOWN", "blocked_restart", "snapshot_restore",
                 "missing_first_row", "confirm_direct", "idempotent", "second_process_claim", "second_process_unknown"),
    "scope": ("actor_id", "tenant_id", "workspace_id", "policy_version", "authorization_ref"),
    "saga": ("CONFIRMED", "FAILED", "REVOKED", "BLOCKED_REAPPROVAL",
             "comp_CONFIRMED", "comp_FAILED", "comp_UNCERTAIN"),
}


def case(group, mode):
    def run(self):
        self.observation.update(group=group, case=mode)
        getattr(self, "run_"+group)(mode)
    return run


for group, modes in MATRIX.items():
    for mode in modes:
        setattr(A79CausalDenialTests, "test_"+group+"_"+mode, case(group, mode))


if __name__ == "__main__":
    import os
    import sys
    from test_atlasquant_aion_activation_denial_coverage_a76 import EvidenceResult
    modules = ["test_atlasquant_aion_h0_causal_denial_a79",
               "test_atlasquant_aion_producer_receipt_untrusted_precheck",
               "test_atlasquant_aion_outbox_fifo_local_terminal_denial",
               "test_atlasquant_aion_outbox_missing_predecessor_denial",
               "test_atlasquant_aion_inflight_untrusted_receipts_a58",
               "test_atlasquant_aion_inflight_receipt_safety_a71"]
    if "--historical" in sys.argv:
        modules = ["test_atlasquant_aion_execution_outbox", "test_atlasquant_aion_execution_saga",
                   "test_atlasquant_aion_saga_outcome_local_trust_a62",
                   "test_atlasquant_aion_saga_compensation_admission",
                   "test_atlasquant_aion_action_receipt",
                   "test_atlasquant_aion_action_receipt_bridge",
                   "test_atlasquant_aion_b2b_external_effect_outcome_receipt_contract_v1",
                   "test_atlasquant_aion_b2b_real_receipt_authenticator_contract_v1"]
    EvidenceResult.records = []
    with ExitStack() as guard:
        no_network(guard)
        result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(
            unittest.defaultTestLoader.loadTestsFromNames(modules))
    report = {"head": os.environ.get("A79_HEAD"), "os": sys.platform, "python": sys.version,
              "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skips": len(result.skipped), "records": EvidenceResult.records}
    print("A79_RESULT_JSON_BEGIN")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    print("A79_RESULT_JSON_END")
    sys.exit(not result.wasSuccessful())
