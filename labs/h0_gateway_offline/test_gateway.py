"""16 synthetic adversarial checks from RFC H0-GW-01. OFFLINE ONLY."""
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from dataclasses import replace

try:
    from .gateway import (Gateway, Intent, SimulatedPolicy, SimulatedHighWater,
                          FakeAdapter, FakeReceiptAuthority, Denied, Uncertain, InjectedCrash)
except ImportError:
    from gateway import (Gateway, Intent, SimulatedPolicy, SimulatedHighWater,
                         FakeAdapter, FakeReceiptAuthority, Denied, Uncertain, InjectedCrash)


def good_policy(**kwargs):
    values = dict(independent_admin_assumed=True, exclusive_fake_adapter_assumed=True,
                  trusted_test_key_assumed=True, strong_read_assumed=True,
                  source_gate_assumed=True, human_owner_gate_assumed=True,
                  simulated_monthly_budget=0)
    values.update(kwargs)
    return SimulatedPolicy(**values)


def sample(intent_id="logical-intent-0001", tenant="tenant-A"):
    return Intent(logical_intent_id=intent_id, idempotency_key="opaque-dedupe-key-1",
                  owner="TEST-HUMAN-OWNER", tenant=tenant, workspace="ws-A",
                  aggregate="agg-1", action="fake-notification", channel="fake-sms",
                  account="SIMULATED-account", issuer="SIMULATED-gateway",
                  payload_digest="a" * 64, destination_digest="b" * 64)


def race_worker(db_path, intent, queue):
    gateway = Gateway(db_path, good_policy())
    adapter = FakeAdapter()
    try:
        gateway.dispatch_once(intent, adapter)
        queue.put(("GRANTED", len(adapter.sink)))
    except Denied:
        queue.put(("DENIED", len(adapter.sink)))
    except Exception as exc:
        queue.put(("ERROR:" + repr(exc), len(adapter.sink)))


def fence_worker(db_path, intent, queue, mode):
    gateway = Gateway(db_path, good_policy())
    try:
        if mode == "fence":
            gateway.fence_pre_handoff(intent)
        else:
            gateway.dispatch_once(intent, FakeAdapter())
        queue.put(mode)
    except Denied:
        queue.put("denied")


class H0GatewayOfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="H0GW_OFFLINE_")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.sqlite"
        self.intent = sample()
        self.authority = FakeReceiptAuthority()
        self.gateway = Gateway(self.path, good_policy(), verifier=self.authority)
        self.gateway.prepare(self.intent)

    def assert_unknown(self):
        state = self.gateway.inspect(self.intent)
        self.assertEqual(state["state"], "UNKNOWN")
        self.assertEqual(state["issue_count"], 1)

    def test_01_thirty_two_processes_one_issue_one_fake_call(self):
        ctx = mp.get_context("spawn" if os.name == "nt" else "fork")
        q = ctx.Queue()
        workers = [ctx.Process(target=race_worker, args=(str(self.path), self.intent, q)) for _ in range(32)]
        for proc in workers:
            proc.start()
        for proc in workers:
            proc.join(30)
            self.assertEqual(proc.exitcode, 0, "multiprocess contender crashed or hung")
        results = [q.get(timeout=3) for _ in range(32)]
        self.assertEqual([x[0] for x in results].count("GRANTED"), 1, results)
        self.assertEqual([x[0] for x in results].count("DENIED"), 31, results)
        self.assertEqual(sum(x[1] for x in results), 1)
        self.assert_unknown()

    def test_02_crash_after_marker_before_fake_call_no_restart_retry(self):
        sink = []
        with self.assertRaises(InjectedCrash):
            self.gateway.dispatch_once(self.intent, FakeAdapter(sink), crash_at="after_marker")
        self.assertEqual(sink, [])
        restarted = Gateway(self.path, good_policy())
        with self.assertRaises(Denied):
            restarted.dispatch_once(self.intent, FakeAdapter(sink))
        self.assertEqual(sink, [])
        self.assert_unknown()

    def test_03_after_handoff_lost_response_ttl_expired_never_retry(self):
        sink = []
        with self.assertRaises(InjectedCrash):
            self.gateway.dispatch_once(self.intent, FakeAdapter(sink), crash_at="after_handoff")
        self.assertEqual(len(sink), 1)
        # No TTL cleanup exists; 31-day elapsed time cannot rearm issue_count.
        for _ in range(3):
            with self.assertRaises(Denied):
                Gateway(self.path, good_policy()).dispatch_once(self.intent, FakeAdapter(sink))
        self.assertEqual(len(sink), 1)
        self.assert_unknown()

    def test_04_fence_versus_issue_mutually_exclusive(self):
        ctx = mp.get_context("spawn" if os.name == "nt" else "fork")
        q = ctx.Queue()
        workers = [ctx.Process(target=fence_worker, args=(str(self.path), self.intent, q, mode)) for mode in ("fence", "issue")]
        for p in workers:
            p.start()
        for p in workers:
            p.join(30)
            self.assertEqual(p.exitcode, 0)
        outcomes = [q.get(timeout=3) for _ in workers]
        self.assertEqual(outcomes.count("denied"), 1, outcomes)
        self.assertTrue("issue" in outcomes or "fence" in outcomes)
        state = self.gateway.inspect(self.intent)
        self.assertIn(state["state"], ("UNKNOWN", "FENCED_PRE_HANDOFF"))
        self.assertEqual(state["issue_count"], 1 if state["state"] == "UNKNOWN" else 0)

    def test_05_alternative_adapter_and_shared_credentials_fail_closed(self):
        class BadAdapter:
            def call(self, _):
                raise AssertionError("MUST NOT BE ACCESSED")
        with self.assertRaisesRegex(Denied, "UNTRUSTED_ADAPTER"):
            self.gateway.dispatch_once(self.intent, BadAdapter())
        weaker = Gateway(self.path, good_policy(exclusive_fake_adapter_assumed=False))
        with self.assertRaisesRegex(Denied, "GATES_NOT_MET"):
            weaker.dispatch_once(self.intent, FakeAdapter())
        self.assertEqual(self.gateway.inspect(self.intent)["state"], "PREPARED")

    def test_06_immutability_scope_payload_destination_channel_key(self):
        for key, value in (("tenant", "tenant-B"), ("payload_digest", "z" * 64),
                           ("destination_digest", "c" * 64), ("channel", "other"),
                           ("idempotency_key", "other-key"), ("owner", "other-owner"),
                           ("epoch", 2), ("account", "other-account")):
            modified = replace(self.intent, **{key: value})
            with self.subTest(key=key), self.assertRaisesRegex(Denied, "CONFLICT"):
                self.gateway.dispatch_once(modified, FakeAdapter())
        self.assertEqual(self.gateway.inspect(self.intent)["issue_count"], 0)

    def test_07_restore_older_ledger_highwater_detects_rollback(self):
        witness = SimulatedHighWater()
        wdb = Path(self.tmp.name) / "with_witness.sqlite"
        gw = Gateway(wdb, good_policy(), witness=witness)
        intent = sample("rollback-target")
        gw.prepare(intent)
        backup = Path(self.tmp.name) / "snapshot.sqlite"
        shutil.copyfile(wdb, backup)
        with self.assertRaises(InjectedCrash):
            gw.dispatch_once(intent, FakeAdapter(), crash_at="after_marker")
        self.assertEqual(witness.values[intent.logical_intent_id], 2)
        shutil.copyfile(backup, wdb)  # adversarial restore while toy witness survives
        with self.assertRaisesRegex(Denied, "ROLLBACK_DETECTED"):
            gw.dispatch_once(intent, FakeAdapter())
        with self.assertRaisesRegex(Denied, "ROLLBACK_DETECTED"):
            gw.inspect(intent)
        witness.available = False
        with self.assertRaisesRegex(Denied, "WITNESS_UNAVAILABLE"):
            gw.dispatch_once(intent, FakeAdapter())

    def test_08_signature_issuer_epoch_version_and_nonce_replay(self):
        self.gateway.dispatch_once(self.intent, FakeAdapter())
        receipt = self.authority.sign(self.intent, kind="API_CREATED", nonce="nonce01", sequence=1)
        for key, val in (("signature", "wrong"), ("issuer", "wrong"),
                         ("epoch", 4), ("key_id", "stolen")):
            tampered = {**receipt, key: val}
            with self.subTest(key=key), self.assertRaises(Denied):
                self.gateway.accept_receipt(self.intent, tampered)
        self.assertEqual(self.gateway.accept_receipt(self.intent, receipt), "PROVIDER_ACCEPTED")
        with self.assertRaisesRegex(Denied, "REPLAY"):
            self.gateway.accept_receipt(self.intent, receipt)
        reused = self.authority.sign(self.intent, kind="CARRIER_ACCEPTED", nonce="nonce01", sequence=2)
        with self.assertRaisesRegex(Denied, "REPLAY"):
            self.gateway.accept_receipt(self.intent, reused)

    def test_09_delivered_then_failed_out_of_order_never_no_effect(self):
        self.gateway.dispatch_once(self.intent, FakeAdapter())
        self.gateway.accept_receipt(self.intent, self.authority.sign(self.intent, kind="DELIVERED", nonce="n1", sequence=3))
        with self.assertRaisesRegex(Denied, "NO_EFFECT_FENCED"):
            self.gateway.accept_receipt(self.intent, self.authority.sign(self.intent, kind="FAILED", nonce="n2", sequence=4))
        with self.assertRaisesRegex(Denied, "NONMONOTONIC"):
            self.gateway.accept_receipt(self.intent, self.authority.sign(self.intent, kind="API_CREATED", nonce="n3", sequence=2))
        self.assertEqual(self.gateway.inspect(self.intent)["boundary"], "DELIVERED")

    def test_10_timeout_429_5xx_late_receipt_without_retry(self):
        for result in ("timeout", "429", "5xx"):
            intent = sample("transport-" + result)
            self.gateway.prepare(intent)
            adapter = FakeAdapter(result=result)
            with self.subTest(result=result), self.assertRaises(Uncertain):
                self.gateway.dispatch_once(intent, adapter)
            self.assertEqual(len(adapter.sink), 1)
            self.assertEqual(self.gateway.inspect(intent)["state"], "UNKNOWN")
            with self.assertRaises(Denied):
                self.gateway.dispatch_once(intent, adapter)
            self.gateway.accept_receipt(intent, self.authority.sign(intent, kind="API_CREATED", nonce="late-" + result, sequence=1))
            self.assertEqual(self.gateway.inspect(intent)["boundary"], "API_CREATED")
            self.assertEqual(len(adapter.sink), 1)

    def test_11_fake_cancel_can_be_followed_by_late_delivery_no_post_send_fence(self):
        self.gateway.dispatch_once(self.intent, FakeAdapter())
        with self.assertRaisesRegex(Denied, "NO_EFFECT_FENCED"):
            self.gateway.accept_receipt(self.intent, self.authority.sign(self.intent, kind="NO_EFFECT_FENCED", nonce="cancel", sequence=1))
        self.gateway.accept_receipt(self.intent, self.authority.sign(self.intent, kind="DELIVERED", nonce="late", sequence=2))
        self.assertEqual(self.gateway.inspect(self.intent)["boundary"], "DELIVERED")

    def test_12_signer_restart_missing_key_custody_fail_closed(self):
        self.gateway.dispatch_once(self.intent, FakeAdapter())
        self.authority.available = False
        with self.assertRaisesRegex(Denied, "UNAVAILABLE"):
            self.gateway.accept_receipt(self.intent, self.authority.sign(self.intent, kind="API_CREATED", nonce="x", sequence=1))
        self.assert_unknown()
        gw_new_signer = Gateway(self.path, good_policy(), verifier=FakeReceiptAuthority(key=b"wrong-key"))
        receipt = FakeReceiptAuthority().sign(self.intent, kind="API_CREATED", nonce="y", sequence=1)
        with self.assertRaisesRegex(Denied, "SIGNATURE_INVALID"):
            gw_new_signer.accept_receipt(self.intent, receipt)

    def test_13_weak_eventual_read_policy_explicitly_rejected(self):
        weak = Gateway(self.path, good_policy(strong_read_assumed=False))
        with self.assertRaisesRegex(Denied, "GATES_NOT_MET"):
            weak.dispatch_once(self.intent, FakeAdapter())
        self.assertEqual(self.gateway.inspect(self.intent)["issue_count"], 0)

    def test_14_no_lookup_after_lost_provider_id_keeps_unknown(self):
        with self.assertRaises(InjectedCrash):
            self.gateway.dispatch_once(self.intent, FakeAdapter(), crash_at="after_handoff")
        self.assertEqual(self.gateway.provider_lookup_without_id(self.intent), "UNKNOWN")
        with self.assertRaises(Denied):
            self.gateway.dispatch_once(self.intent, FakeAdapter())
        self.assert_unknown()

    def test_15_source_h0_owner_gates_independent_worker_always_off(self):
        for source, h0, owner in ((True, False, True), (False, True, True),
                                  (True, True, False), (True, True, True)):
            self.assertFalse(Gateway.production_worker_eligible(
                source_verified=source, h0_verified=h0, owner_verified=owner))
        no_source = Gateway(self.path, good_policy(source_gate_assumed=False))
        with self.assertRaises(Denied):
            no_source.dispatch_once(self.intent, FakeAdapter())

    def test_16_budget_circuit_breaker_no_shortcuts(self):
        costly = FakeAdapter()
        with self.assertRaisesRegex(Denied, "BUDGET_BLOCKED"):
            self.gateway.dispatch_once(self.intent, costly, quoted_cost=1)
        self.assertEqual(costly.sink, [])
        self.assertEqual(self.gateway.inspect(self.intent)["state"], "PREPARED")
        self.gateway.dispatch_once(self.intent, FakeAdapter(), quoted_cost=0)
        self.assert_unknown()
        with self.assertRaises(Denied):
            self.gateway.dispatch_once(self.intent, FakeAdapter())


if __name__ == "__main__":
    unittest.main(verbosity=2)
