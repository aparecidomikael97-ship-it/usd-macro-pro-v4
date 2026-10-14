"""A59 RED: self-reported checkpoint stats and relabelled receipts cannot prove LIVE.

Only test real read-only AION verifier with local fixtures. No production calls.
The test module documents the untrusted evidence; a green run without independent
source enrollment must NEVER be described as proof that a Worker is LIVE.
"""
from copy import deepcopy
from datetime import timedelta
import unittest
import test_atlasquant_aion_global_worker_live_verification as live_fixture
import test_atlasquant_aion_inflight_untrusted_receipts_a58 as receipt_fixture
from atlasquant_aion_global_worker import (
    _mutated, _empty_lease, attach_global_worker_state, load_global_worker_state,
)
from atlasquant_aion_global_worker_live_verification import (
    verify_global_worker_live_activation,
)


class A59LiveEvidenceSourceTrustTests(unittest.TestCase):
    def setUp(self):
        self.v = live_fixture.GlobalWorkerLiveVerificationTests()
        self.v.setUp()

    def test_01_self_asserted_heartbeat_and_tick_are_not_verified_live(self):
        checkpoint = self.v.with_stats(
            self.v.armed_checkpoint(),
            heartbeat_at=live_fixture.TICK.isoformat(),
            tick_at=live_fixture.TICK.isoformat(),
            runtime_id="gha-self-asserted",
            ticks=1,
        )
        report = verify_global_worker_live_activation(
            self.v.access, self.v.runtime(checkpoint),
            live_fixture._flag(),
            activation_result=live_fixture._activation_result(),
            now=live_fixture.TICK + timedelta(seconds=10),
        )
        self.assertFalse(
            report.get("live_confirmed"),
            "Locally re-digestable heartbeat/tick cannot prove live Worker",
        )
        self.assertNotIn(report["status"], {"LIVE_CONFIRMED_IDLE", "LIVE_CONFIRMED_WITH_WORK"})

    def test_02_self_asserted_local_terminal_cannot_prove_live_work(self):
        f = receipt_fixture.A58LocalTerminalAuthorityDenialTests()
        f.setUp()
        checkpoint = f.locally_relabel_terminal(f.local_receipt_checkpoint())
        state, _ = load_global_worker_state(checkpoint)
        stats = deepcopy(state["stats"])
        stats.update({
            "last_heartbeat_at": receipt_fixture.rf.TICK.isoformat(),
            "last_tick_at": receipt_fixture.rf.TICK.isoformat(),
            "last_runtime_id": "gha-self-asserted-receipt",
            "ticks": 1,
        })
        checkpoint = attach_global_worker_state(
            checkpoint,
            _mutated(state, stats=stats, lease=_empty_lease(), inflight_tick={}),
        )
        boundary = receipt_fixture.rf.BASE
        report = verify_global_worker_live_activation(
            f.f.access, f.runtime(checkpoint),
            live_fixture._flag(updated_at=boundary),
            activation_result=live_fixture._activation_result(activated_at=boundary),
            now=receipt_fixture.rf.TICK + timedelta(minutes=20),
        )
        self.assertFalse(
            report.get("live_confirmed"),
            "Locally re-signed GLOBAL_WORKER row cannot prove live work",
        )
        self.assertFalse(report.get("work_receipt_confirmed"))
        self.assertNotIn(report["status"], {"LIVE_CONFIRMED_IDLE", "LIVE_CONFIRMED_WITH_WORK"})

    def test_03_heartbeat_only_cannot_assert_verified_heartbeat(self):
        checkpoint = self.v.with_stats(
            self.v.armed_checkpoint(),
            heartbeat_at=live_fixture.TICK.isoformat(),
            tick_at="",
            runtime_id="gha-self-asserted-heartbeat",
            ticks=0,
        )
        report = verify_global_worker_live_activation(
            self.v.access, self.v.runtime(checkpoint),
            live_fixture._flag(),
            activation_result=live_fixture._activation_result(),
            now=live_fixture.TICK + timedelta(seconds=10),
        )
        self.assertEqual(report["status"], "BLOCKED_UNVERIFIED_LIVE_EVIDENCE")
        self.assertFalse(report["heartbeat_confirmed"])
        self.assertFalse(report["live_confirmed"])
        self.assertFalse(report["feature_flag_modified"])

    def test_04_claims_in_loaded_metadata_cannot_enroll_live_authority(self):
        checkpoint = self.v.with_stats(
            self.v.armed_checkpoint(),
            heartbeat_at=live_fixture.TICK.isoformat(),
            tick_at=live_fixture.TICK.isoformat(),
            runtime_id="gha-fake-attestor",
            ticks=1,
        )
        runtime = self.v.runtime(checkpoint)
        runtime.update({
            "independent_witness_verified": True,
            "owner_authorized": True,
            "source_attested": True,
            "producer_receipt_verified": True,
        })
        report = verify_global_worker_live_activation(
            self.v.access, runtime,
            live_fixture._flag(),
            activation_result=live_fixture._activation_result(),
            now=live_fixture.TICK + timedelta(seconds=10),
        )
        self.assertEqual(report["status"], "BLOCKED_UNVERIFIED_LIVE_EVIDENCE")
        for key in ("live_confirmed", "heartbeat_confirmed", "tick_confirmed",
                    "work_receipt_confirmed"):
            self.assertFalse(report[key])
        self.assertEqual(report["reason"], "INDEPENDENT_LIVE_ATTESTATION_NOT_ENROLLED")

    def test_06_stale_lease_must_not_claim_confirmed_local_tick(self):
        lease = {
            "owner": "gha-local-lease",
            "token": "untrusted-local-token",
            "fencing_token": 1,
            "acquired_at": live_fixture.ACTIVATED.isoformat(),
            "heartbeat_at": live_fixture.TICK.isoformat(),
            "expires_at": (live_fixture.TICK - timedelta(minutes=1)).isoformat(),
        }
        checkpoint = self.v.with_stats(
            self.v.armed_checkpoint(),
            heartbeat_at=live_fixture.TICK.isoformat(),
            tick_at=live_fixture.TICK.isoformat(),
            runtime_id="gha-local-lease",
            ticks=1,
            lease=lease,
        )
        report = verify_global_worker_live_activation(
            self.v.access, self.v.runtime(checkpoint),
            live_fixture._flag(),
            activation_result=live_fixture._activation_result(),
            now=live_fixture.TICK + timedelta(seconds=10),
        )
        self.assertEqual(report["status"], "BLOCKED_STALE_LEASE")
        self.assertFalse(report["live_confirmed"])
        self.assertFalse(report["heartbeat_confirmed"])
        self.assertFalse(report["tick_confirmed"])

    def test_07_inflight_block_must_not_claim_confirmed_local_tick(self):
        f = receipt_fixture.A58LocalTerminalAuthorityDenialTests()
        f.setUp()
        checkpoint = self.v.with_stats(
            f.claimed,
            heartbeat_at=receipt_fixture.rf.TICK.isoformat(),
            tick_at=receipt_fixture.rf.TICK.isoformat(),
            runtime_id="gha-local-inflight",
            ticks=1,
        )
        report = verify_global_worker_live_activation(
            f.f.access, f.runtime(checkpoint),
            live_fixture._flag(updated_at=receipt_fixture.rf.BASE),
            activation_result=live_fixture._activation_result(
                activated_at=receipt_fixture.rf.BASE
            ),
            now=receipt_fixture.rf.TICK + timedelta(minutes=20),
        )
        self.assertEqual(report["status"], "BLOCKED_INFLIGHT_RECONCILIATION")
        self.assertFalse(report["live_confirmed"])
        self.assertFalse(report["heartbeat_confirmed"])
        self.assertFalse(report["tick_confirmed"])

    def test_08_unsafe_local_receipt_must_not_claim_confirmed_work(self):
        f = receipt_fixture.A58LocalTerminalAuthorityDenialTests()
        f.setUp()
        checkpoint = f.locally_relabel_terminal(
            f.local_receipt_checkpoint(), unsafe=True,
        )
        state, _ = load_global_worker_state(checkpoint)
        stats = deepcopy(state["stats"])
        stats.update({
            "last_heartbeat_at": receipt_fixture.rf.TICK.isoformat(),
            "last_tick_at": receipt_fixture.rf.TICK.isoformat(),
            "last_runtime_id": "gha-untrusted-unsafe",
            "ticks": 1,
        })
        checkpoint = attach_global_worker_state(
            checkpoint,
            _mutated(state, stats=stats, lease=_empty_lease(), inflight_tick={}),
        )
        report = verify_global_worker_live_activation(
            f.f.access, f.runtime(checkpoint),
            live_fixture._flag(updated_at=receipt_fixture.rf.BASE),
            activation_result=live_fixture._activation_result(
                activated_at=receipt_fixture.rf.BASE
            ),
            now=receipt_fixture.rf.TICK + timedelta(minutes=20),
        )
        self.assertEqual(report["status"], "BLOCKED_UNSAFE_RECEIPT")
        self.assertEqual(report["unsafe_receipts_after_activation"], 1)
        self.assertFalse(report["live_confirmed"])
        self.assertFalse(report["work_receipt_confirmed"])
        self.assertFalse(report["heartbeat_confirmed"])
        self.assertFalse(report["tick_confirmed"])

    def test_05_feature_off_is_not_live_even_with_self_asserted_stats(self):
        checkpoint = self.v.with_stats(
            self.v.armed_checkpoint(),
            heartbeat_at=live_fixture.TICK.isoformat(),
            tick_at=live_fixture.TICK.isoformat(),
            runtime_id="gha-fake-live",
            ticks=1,
        )
        report = verify_global_worker_live_activation(
            self.v.access, self.v.runtime(checkpoint),
            live_fixture._flag(state="DISABLED"),
            activation_result=live_fixture._activation_result(),
            now=live_fixture.TICK,
        )
        self.assertEqual(report["status"], "NOT_ENABLED")
        self.assertFalse(report.get("live_confirmed", False))
        self.assertFalse(report["feature_flag_modified"])


if __name__ == "__main__":
    unittest.main()
