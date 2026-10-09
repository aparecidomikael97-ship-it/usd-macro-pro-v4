"""Only disposable hosted CI: ephemeral witness/role keys stay in RAM.

Independent witness state is deliberately OUTSIDE SQLite. No real anchor,
network/service/TPM/owner device. Public count artifacts only.
"""
from __future__ import annotations
import copy
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import test_atlasquant_aion_dual_ed25519_public_crypto_bridge_v1 as upstream
import atlasquant_aion_durable_dual_ed25519_challenge_registry_v1 as ledger
import atlasquant_aion_independent_monotonic_witness_reference_v2 as ref

ISSUED="2026-10-08T12:00:00Z"
NOW="2026-10-08T12:00:30Z"
EXPIRES="2026-10-08T12:05:00Z"
NONCE="ba"*32
TX="ab"*32


class WitnessPort:
    """CI-only signer. No private serialization/storage/export/enrollment."""
    def __init__(self,scope,snapshot,pair=None):
        self.pair=pair or upstream.DisposablePair()
        self.state=ref.ReferenceWitnessState(scope=scope,initial_ledger_sha256=ref.snapshot_digest(snapshot))
    def wrap(self,checkpoint):
        return {"checkpoint":copy.deepcopy(checkpoint),
                "signature_hex":self.pair._private.sign(ref.checkpoint_message(checkpoint)).hex()}
    def prepare(self,**kwargs):
        return self.wrap(self.state.prepare(**kwargs))
    def recover(self,**kwargs):
        return self.wrap(self.state.recover(**kwargs))
    def expected_head(self):
        return self.state.expected_head()


class IndependentWitnessTests(unittest.TestCase):
    def setUp(self):
        if (os.environ.get("GITHUB_ACTIONS")!="true"
                or os.environ.get("RUNNER_ENVIRONMENT")!="github-hosted"
                or os.environ.get("RUNNER_OS") not in ("Linux","Windows")):
            raise RuntimeError("Disposable hosted CI required; owner host forbidden")
        self.fixture=upstream.DualEd25519MathematicalBridgeTests(methodName="runTest")
        self.fixture.setUp()
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=str(Path(self.temp.name).resolve())
        self.path=str(Path(self.root)/"ledger.sqlite3")
        self.store=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root,create=True)
        self.request=self.payload()
        self.assertEqual(self.issue(self.request)["state"],"ISSUED")
        self.scope={"installation_id":"ci-install-0001","trust_chain_id":"ci-trust-chain-0001",
                    "witness_id":"ci-witness-0001",
                    "owner_public_key_sha256":self.fixture.owner.fingerprint,
                    "collector_public_key_sha256":self.fixture.collector.fingerprint,
                    "custody_sha256":ref.custody_digest(self.fixture.proposal)}
        self.witness=WitnessPort(self.scope,ref.ledger_snapshot(self.store))
        self.adapter=self.make_adapter()

    def payload(self,nonce=NONCE,generation=7,policy=None,proposal=None):
        proposal=copy.deepcopy(proposal or self.fixture.proposal)
        proposal["policy_generation"]=generation
        if policy is not None: proposal["policy_sha256"]=policy
        raw=self.fixture.payload(nonce=nonce,proposal=proposal)
        binding=ref.build_v2_binding(proposal,nonce)
        return {"v1_request":raw,
            "v2_owner_signature_hex":self.fixture.owner._private.sign(
                bytes.fromhex(binding["role_intents"]["owner"][7:])).hex(),
            "v2_collector_signature_hex":self.fixture.collector._private.sign(
                bytes.fromhex(binding["role_intents"]["collector"][7:])).hex()}

    def issue(self,request):
        raw=request["v1_request"]
        return self.store.issue(proposal=raw["proposal"],nonce=raw["nonce"],issued_at=ISSUED,expires_at=EXPIRES)

    def make_adapter(self,witness=None,scope=None,pin="default"):
        return ref.ReferenceWitnessAdapter(store=self.store,witness=witness or self.witness,
            scope=scope or self.scope,
            trusted_witness_public_key_hex=self.witness.pair.public_hex if pin=="default" else pin)

    def prepare(self,request=None,tx=TX):
        return self.adapter.prepare(request=request or self.request,transaction_id=tx,now_ts=NOW)

    def run_flow(self,request=None,tx=TX,adapter=None):
        return (adapter or self.adapter).consume_and_confirm(
            request=request or self.request,transaction_id=tx,now_ts=NOW)

    def gates(self,out):
        for key in ref.FALSE_GATES:
            self.assertIs(out[key],False,key)
        self.assertIs(out["snapshot_atomic_across_witness"],False)
        self.assertIs(out["exactly_once_execution_proven"],False)

    def blocked(self,out):
        self.assertEqual(out["state"],"BLOCKED",out)
        self.assertFalse(out["ledger_matches_witness"])
        self.gates(out)

    def signed(self):
        prepared=self.prepare()
        self.assertTrue(self.store.consume(request=self.request["v1_request"],now_ts=NOW)["nonce_transaction_consumed"])
        out=self.adapter.recover(prepared=prepared)
        self.assertTrue(out["ledger_matches_witness"],out)
        self.gates(out)
        return prepared,self.witness.wrap(out["checkpoint"])

    def test_healthy_four_observations_not_last_three_authorities(self):
        out=self.run_flow()
        for key in ("dual_signature_mathematically_valid","nonce_consumed_intact_ledger",
                    "external_witness_checkpoint_verified","ledger_matches_witness"):
            self.assertIs(out[key],True)
        self.gates(out)

    def test_preconsumption_db_restore_with_independent_witness_blocks(self):
        backup=Path(self.root)/"before.sqlite3"
        shutil.copyfile(self.path,backup)
        self.assertTrue(self.run_flow()["ledger_matches_witness"])
        shutil.copyfile(backup,self.path)
        self.blocked(self.run_flow(tx="ac"*32))
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_db_and_local_checkpoint_restore_independent_witness_preserved(self):
        backup=Path(self.root)/"before.sqlite3"
        shutil.copyfile(self.path,backup)
        prepared,_=self.signed()
        local_checkpoint=copy.deepcopy(prepared)
        shutil.copyfile(backup,self.path)
        self.blocked(self.adapter.recover(prepared=local_checkpoint))
        self.blocked(self.run_flow(tx="ad"*32))

    def test_restoring_both_db_and_witness_explicitly_loses_guarantee(self):
        backup=Path(self.root)/"before.sqlite3"
        shutil.copyfile(self.path,backup)
        initial_hash=self.witness.state.ledger_head
        self.assertTrue(self.run_flow()["ledger_matches_witness"])
        shutil.copyfile(backup,self.path)
        # Attacker reset of independent state is OUTSIDE the guarantee.
        self.witness.state=ref.ReferenceWitnessState(scope=self.scope,initial_ledger_sha256=initial_hash)
        out=self.run_flow()
        self.assertTrue(out["ledger_matches_witness"])
        self.gates(out)

    def test_same_receipt_is_not_a_signature_request(self):
        out=self.run_flow()
        self.blocked(self.run_flow(request=out))

    def test_consumed_nonce_cannot_be_reissued(self):
        self.assertTrue(self.run_flow()["ledger_matches_witness"])
        self.assertEqual(self.issue(self.request)["state"],"BLOCKED")

    def test_replay_original_request_never_confirms_second_time(self):
        self.assertTrue(self.run_flow()["ledger_matches_witness"])
        self.blocked(self.run_flow(tx="ac"*32))
        self.assertEqual(len(self.witness.state.used),1)

    def test_pending_confirmation_never_executable(self):
        prepared=self.prepare()
        self.assertEqual(prepared["phase"],"PREPARED")
        self.assertIsNone(self.witness.state.head)
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")
        out=self.adapter.recover(prepared=prepared)
        self.blocked(out)

    def test_restart_after_sqlite_commit_recovers_exact_pending_once(self):
        prepared=self.prepare()
        self.assertTrue(self.store.consume(request=self.request["v1_request"],now_ts=NOW)["nonce_transaction_consumed"])
        self.store=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        restarted=self.make_adapter()
        self.assertTrue(restarted.recover(prepared=prepared)["ledger_matches_witness"])
        before=ref.ledger_snapshot(self.store)
        self.assertTrue(restarted.recover(prepared=prepared)["ledger_matches_witness"])
        self.assertEqual(before,ref.ledger_snapshot(self.store))
        self.assertEqual(len(self.witness.state.used),1)

    def test_restart_before_commit_stays_blocked_no_consumption_or_auto_repair(self):
        prepared=self.prepare()
        self.store=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        before=ref.ledger_snapshot(self.store)
        self.blocked(self.make_adapter().recover(prepared=prepared))
        self.assertEqual(before,ref.ledger_snapshot(self.store))
        self.assertIsNotNone(self.witness.state.pending)

    def test_lost_confirmation_reply_recovers_without_second_authorization(self):
        prepared=self.prepare()
        self.store.consume(request=self.request["v1_request"],now_ts=NOW)
        original=self.witness.recover
        def lost(**kwargs):
            original(**kwargs)
            raise OSError("simulated lost reply")
        with patch.object(self.witness,"recover",side_effect=lost):
            self.blocked(self.adapter.recover(prepared=prepared))
        self.assertEqual(len(self.witness.state.used),1)
        self.assertTrue(self.adapter.recover(prepared=prepared)["ledger_matches_witness"])
        self.blocked(self.run_flow(tx="ac"*32))

    def test_before_sqlite_commit_failure_keeps_pending_not_confirmed(self):
        original=self.store._commit
        def fail(conn):
            raise sqlite3.OperationalError("injected before commit")
        with patch.object(self.store,"_commit",side_effect=fail):
            self.blocked(self.run_flow())
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")
        self.assertIsNone(self.witness.state.head)
        self.assertIsNotNone(self.witness.state.pending)

    def test_after_sqlite_commit_lost_ack_requires_explicit_recovery(self):
        prepared=self.prepare()
        original=self.store._commit
        def lost(conn):
            original(conn)
            raise sqlite3.OperationalError("lost commit acknowledgment")
        with patch.object(self.store,"_commit",side_effect=lost):
            out=self.store.consume(request=self.request["v1_request"],now_ts=NOW)
            self.assertFalse(out["nonce_transaction_consumed"])
        self.assertEqual(self.store.inspect()["states"][NONCE],"CONSUMED")
        self.assertIsNone(self.witness.state.head)
        self.assertTrue(self.adapter.recover(prepared=prepared)["ledger_matches_witness"])

    def test_before_witness_confirmation_unavailable_no_fallback(self):
        prepared=self.prepare()
        self.store.consume(request=self.request["v1_request"],now_ts=NOW)
        with patch.object(self.witness,"recover",side_effect=OSError("unavailable")):
            self.blocked(self.adapter.recover(prepared=prepared))
        self.assertIsNone(self.witness.state.head)
        self.assertTrue(self.adapter.recover(prepared=prepared)["ledger_matches_witness"])

    def test_prepare_unavailable_leaves_sqlite_untouched(self):
        before=ref.ledger_snapshot(self.store)
        with patch.object(self.witness,"prepare",side_effect=OSError("disconnected")):
            self.blocked(self.run_flow())
        self.assertEqual(before,ref.ledger_snapshot(self.store))

    def test_signature_tamper(self):
        prepared,envelope=self.signed()
        envelope["signature_hex"]="00"*64
        self.assertFalse(ref.verify_checkpoint(envelope,trusted_public_key_hex=self.witness.pair.public_hex,
            expected={**prepared,"phase":"CONFIRMED"})["external_witness_checkpoint_verified"])

    def test_mathematically_valid_unauthorized_witness_signature(self):
        prepared,envelope=self.signed()
        attacker=WitnessPort(self.scope,ref.ledger_snapshot(self.store))
        envelope=attacker.wrap(envelope["checkpoint"])
        self.assertFalse(ref.verify_checkpoint(envelope,trusted_public_key_hex=self.witness.pair.public_hex,
            expected={**prepared,"phase":"CONFIRMED"})["external_witness_checkpoint_verified"])

    def test_public_key_in_envelope_cannot_replace_separate_pin(self):
        prepared,envelope=self.signed()
        envelope["public_key_hex"]=self.witness.pair.public_hex
        self.assertFalse(ref.verify_checkpoint(envelope,trusted_public_key_hex=None,
            expected={**prepared,"phase":"CONFIRMED"})["external_witness_checkpoint_verified"])

    def test_swapped_witness_live_port_cannot_pass_pinned_prepare(self):
        attacker=WitnessPort(self.scope,ref.ledger_snapshot(self.store))
        self.blocked(self.run_flow(adapter=self.make_adapter(witness=attacker)))
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_owner_collector_swap(self):
        bad=copy.deepcopy(self.request)
        bad["v1_request"]["owner_public_key_hex"],bad["v1_request"]["collector_public_key_hex"]=(
            bad["v1_request"]["collector_public_key_hex"],bad["v1_request"]["owner_public_key_hex"])
        self.blocked(self.run_flow(request=bad))

    def test_v1_only_not_accepted_by_new_v2_boundary(self):
        self.blocked(self.run_flow(request=self.request["v1_request"]))

    def test_v1_missing_custodian_binding_reproduced_without_reinterpreting_v1(self):
        raw=copy.deepcopy(self.request["v1_request"])
        raw["proposal"]["owner"]["custodian_id"]="different-owner-002"
        self.assertEqual(self.fixture.check(raw)["state"],upstream.bridge.CANDIDATE)
        bad=copy.deepcopy(self.request);bad["v1_request"]=raw
        self.blocked(self.run_flow(request=bad))

    def test_v1_missing_boundary_binding_reproduced_v2_blocks(self):
        raw=copy.deepcopy(self.request["v1_request"])
        raw["proposal"]["owner"]["custody_boundary"]="INDEPENDENT_REMOTE_TRUST_DOMAIN_CANDIDATE"
        self.assertEqual(self.fixture.check(raw)["state"],upstream.bridge.CANDIDATE)
        bad=copy.deepcopy(self.request);bad["v1_request"]=raw
        self.blocked(self.run_flow(request=bad))

    def test_v1_missing_budget_binding_reproduced_v2_blocks(self):
        raw=copy.deepcopy(self.request["v1_request"])
        raw["proposal"]["estimated_monthly_brl"]=200
        self.assertEqual(self.fixture.check(raw)["state"],upstream.bridge.CANDIDATE)
        bad=copy.deepcopy(self.request);bad["v1_request"]=raw
        self.blocked(self.run_flow(request=bad))

    def test_v2_signature_cannot_be_replaced_by_v1_signature(self):
        bad=copy.deepcopy(self.request)
        bad["v2_owner_signature_hex"]=bad["v1_request"]["owner_signature_hex"]
        self.blocked(self.run_flow(request=bad))

    def test_v2_role_domains_are_distinct(self):
        binding=ref.build_v2_binding(self.fixture.proposal,NONCE)
        self.assertNotEqual(binding["role_intents"]["owner"],binding["role_intents"]["collector"])

    def test_direct_witness_arbitrary_target_hash_rejected_even_schema_valid(self):
        before=ref.ledger_snapshot(self.store)
        candidate=self.prepare()
        self.witness.state.pending=None # isolated negative fixture, no production reset API
        candidate["ledger_state_sha256"]="sha256:"+"f"*64
        with self.assertRaises(ref.ReferenceWitnessError):
            self.witness.prepare(before_snapshot=before,request=self.request,candidate=candidate)
        self.assertIsNone(self.witness.state.head)

    def test_direct_witness_claim_without_raw_signatures_rejected(self):
        before=ref.ledger_snapshot(self.store)
        candidate=self.prepare()
        self.witness.state.pending=None
        with self.assertRaises(ValueError):
            self.witness.prepare(before_snapshot=before,request={"verified":True},candidate=candidate)

    def test_checkpoint_requires_exact_expected_sequence_not_signature_alone(self):
        prepared,envelope=self.signed()
        expected={**prepared,"phase":"CONFIRMED","checkpoint_sequence":2}
        self.assertFalse(ref.verify_checkpoint(envelope,trusted_public_key_hex=self.witness.pair.public_hex,
            expected=expected)["external_witness_checkpoint_verified"])

    def test_confirm_wrong_hash_blocked_pending_preserved(self):
        self.prepare()
        with self.assertRaises(ref.ReferenceWitnessError):
            self.witness.state.confirm(transaction_id=TX,ledger_state_sha256="sha256:"+"f"*64)
        self.assertIsNotNone(self.witness.state.pending)
        self.assertIsNone(self.witness.state.head)

    def test_confirm_wrong_transaction_blocked(self):
        prepared=self.prepare()
        with self.assertRaises(ref.ReferenceWitnessError):
            self.witness.state.confirm(transaction_id="ac"*32,ledger_state_sha256=prepared["ledger_state_sha256"])

    def test_partial_db_record_fail_closed(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE challenges SET body='{}'")
        self.blocked(self.run_flow())

    def test_audit_tamper_fails_closed(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE evidence SET digest=?",("sha256:"+"f"*64,))
        self.blocked(self.run_flow())

    def test_receipt_tamper_after_consume_no_confirmation(self):
        prepared=self.prepare()
        self.store.consume(request=self.request["v1_request"],now_ts=NOW)
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE challenges SET receipt='{}'")
        self.blocked(self.adapter.recover(prepared=prepared))

    def test_unissued_extra_record_makes_validated_snapshot_block(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO challenges VALUES(?,?,'ISSUED',NULL)",("ac"*32,"{}"))
        self.blocked(self.run_flow())

    def test_snapshot_read_is_read_only_and_complete(self):
        before=Path(self.path).read_bytes()
        snapshot=ref.ledger_snapshot(self.store)
        self.assertEqual(set(snapshot),{"meta","policy","challenges","evidence"})
        self.assertEqual(before,Path(self.path).read_bytes())
        for table in snapshot:
            changed=copy.deepcopy(snapshot)
            if changed[table]:
                if table=="meta":changed[table][0]["last_now"]+=1
                elif table=="policy":changed[table][0]["generation"]+=1
                else:changed[table][0]["body"]+=" "
                self.assertNotEqual(ref.snapshot_digest(snapshot),ref.snapshot_digest(changed))

    def test_concurrent_same_nonce_eight_threads_one_confirmed(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda i:self.run_flow(tx=f"{i+1:064x}"),range(8)))
        self.assertEqual(sum(r["ledger_matches_witness"] for r in results),1)
        self.assertEqual(len(self.witness.state.used),1)
        for out in results:self.gates(out)

    def test_concurrent_distinct_pending_requests_cannot_both_prepare(self):
        second=self.payload(nonce="ac"*32)
        self.assertEqual(self.issue(second)["state"],"ISSUED")
        self.witness=WitnessPort(self.scope,ref.ledger_snapshot(self.store))
        self.adapter=self.make_adapter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(
                lambda i:self.run_flow(request=(self.request,second)[i],tx=f"{i+1:064x}"),range(2)))
        self.assertGreaterEqual(sum(r["ledger_matches_witness"] for r in results),1)
        self.assertLessEqual(sum(r["ledger_matches_witness"] for r in results),2)
        # Both may succeed sequentially, but witness sequences remain unique.
        self.assertGreaterEqual(len(self.witness.state.used),sum(r["ledger_matches_witness"] for r in results))
        self.assertEqual(self.witness.state.head["checkpoint_sequence"],len(self.witness.state.used))

    def test_generation_upgrade_higher_signed_policy_and_old_generation_blocked(self):
        high=self.payload(nonce="ac"*32,generation=8,policy="sha256:"+"f"*64)
        low=self.payload(nonce="ad"*32,generation=6)
        self.assertEqual(self.issue(high)["state"],"ISSUED")
        self.assertEqual(self.issue(low)["state"],"ISSUED")
        self.witness=WitnessPort(self.scope,ref.ledger_snapshot(self.store));self.adapter=self.make_adapter()
        self.assertTrue(self.run_flow(request=high)["ledger_matches_witness"])
        self.blocked(self.run_flow(request=low,tx="ac"*32))
        self.assertEqual(self.witness.state.head["generation"],8)

    def test_equal_generation_conflicting_policy_blocked(self):
        conflict=self.payload(nonce="ac"*32,policy="sha256:"+"f"*64)
        self.issue(conflict)
        self.witness=WitnessPort(self.scope,ref.ledger_snapshot(self.store));self.adapter=self.make_adapter()
        self.assertTrue(self.run_flow()["ledger_matches_witness"])
        self.blocked(self.run_flow(request=conflict,tx="ac"*32))

    def test_old_prepared_recovery_not_current_after_second_checkpoint(self):
        second=self.payload(nonce="ac"*32)
        self.issue(second)
        self.witness=WitnessPort(self.scope,ref.ledger_snapshot(self.store));self.adapter=self.make_adapter()
        prepared,_=self.signed()
        self.assertTrue(self.run_flow(request=second,tx="ac"*32)["ledger_matches_witness"])
        self.blocked(self.adapter.recover(prepared=prepared))

    def test_missing_original_prepared_intent_no_automatic_reconstruction(self):
        self.prepare()
        self.store.consume(request=self.request["v1_request"],now_ts=NOW)
        self.blocked(self.adapter.recover(prepared={}))
        self.assertIsNotNone(self.witness.state.pending)

    def test_mutating_returned_prepare_and_checkpoint_does_not_change_witness(self):
        prepared,envelope=self.signed()
        head=copy.deepcopy(self.witness.state.head)
        prepared["generation"]=0
        envelope["checkpoint"]["generation"]=0
        self.assertEqual(head,self.witness.state.head)

    def test_repeat_verification_deterministic_100_times(self):
        prepared,envelope=self.signed()
        results=[ref.verify_checkpoint(envelope,trusted_public_key_hex=self.witness.pair.public_hex,
            expected={**prepared,"phase":"CONFIRMED"}) for _ in range(100)]
        self.assertTrue(all(r==results[0] for r in results))
        self.assertTrue(results[0]["external_witness_checkpoint_verified"])

    def test_zero_network_subprocess_provider_during_full_reference_flow(self):
        with patch("socket.socket",side_effect=AssertionError("network forbidden")), \
             patch("subprocess.Popen",side_effect=AssertionError("process forbidden")):
            out=self.run_flow()
        self.assertTrue(out["ledger_matches_witness"])
        self.gates(out)

    def test_public_verifier_zero_filesystem_keys_or_external_calls(self):
        prepared,envelope=self.signed()
        with patch("builtins.open",side_effect=AssertionError("read/write forbidden")), \
             patch("pathlib.Path.open",side_effect=AssertionError("read/write forbidden")), \
             patch("socket.socket",side_effect=AssertionError("network forbidden")):
            out=ref.verify_checkpoint(envelope,trusted_public_key_hex=self.witness.pair.public_hex,
                expected={**prepared,"phase":"CONFIRMED"})
        self.assertTrue(out["external_witness_checkpoint_verified"])

    def test_environment_claims_cannot_enable_installer(self):
        with patch.dict(os.environ,{"INSTALLER_AUTHORIZED":"true","TRUSTED_WITNESS":"true","SAFE_TO_RESUME":"1"}):
            out=self.run_flow()
        self.assertTrue(out["ledger_matches_witness"]);self.gates(out)

    def test_bool_claim_rejected_closed_schema(self):
        bad=copy.deepcopy(self.request)
        bad["installer_authorized"]=True
        self.blocked(self.run_flow(request=bad))

    def test_bounds_large_list_rejected_before_crypto(self):
        self.blocked(self.run_flow(request=[True]*100000))

    def test_bounds_deep_recursive_claim_rejected(self):
        bad={};bad["cycle"]=bad
        self.blocked(self.run_flow(request=bad))

    def test_witness_limits_fail_closed_without_reset(self):
        self.witness.state.used={f"{i:064x}" for i in range(2048)}
        self.blocked(self.run_flow())
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_missing_database_not_recreated(self):
        Path(self.path).unlink()
        self.blocked(self.run_flow())
        self.assertFalse(Path(self.path).exists())


# Every generated case is independently collected and counted, not a hidden
# subTest loop. Re-signed malformed or wrong-scope checkpoints still cannot
# satisfy the separately fixed expected checkpoint.
def checkpoint_attack(field,value):
    def test(self):
        prepared,envelope=self.signed()
        expected={**prepared,"phase":"CONFIRMED"}
        bad=copy.deepcopy(envelope["checkpoint"]);bad[field]=value
        try:envelope=self.witness.wrap(bad)
        except (ValueError,TypeError,KeyError):envelope={"checkpoint":bad,"signature_hex":"00"*64}
        self.assertFalse(ref.verify_checkpoint(envelope,
            trusted_public_key_hex=self.witness.pair.public_hex,expected=expected)["external_witness_checkpoint_verified"])
    return test

ATTACKS={
 "cross_install":("installation_id","other-install-001"),
 "cross_chain":("trust_chain_id","other-trust-chain-001"),
 "cross_witness":("witness_id","other-witness-001"),
 "lower_generation":("generation",6),
 "conflicting_policy":("policy_sha256","sha256:"+"f"*64),
 "duplicate_sequence":("checkpoint_sequence",1+1),
 "zero_sequence":("checkpoint_sequence",0),
 "previous_hash":("previous_checkpoint_sha256","sha256:"+"f"*64),
 "ledger_hash":("ledger_state_sha256","sha256:"+"f"*64),
 "nonce":("challenge_id","ac"*32),
 "transaction":("transaction_id","ac"*32),
 "purpose":("purpose","INSTALLER_AUTHORIZATION"),
 "domain":("schema","OTHER_DOMAIN"),
 "future_version":("version",3),
 "clock_claim":("clock_trusted",True),
 "owner_swap":("owner_public_key_sha256","sha256:"+"f"*64),
 "collector_swap":("collector_public_key_sha256","sha256:"+"f"*64),
 "custody_policy":("custody_sha256","sha256:"+"f"*64),
 "partial_time":("observed_at",""),
 "naive_time":("observed_at","2026-10-08T12:00:30"),
 "different_time":("observed_at","2026-10-08T12:00:31Z"),
 "phase":("phase","PREPARED"),
 "bool_generation":("generation",True),
 "float_generation":("generation",7.0),
 "string_generation":("generation","7"),
 "overflow_generation":("generation",2**32),
 "negative_generation":("generation",-1),
 "bool_version":("version",True),
 "bool_sequence":("checkpoint_sequence",True),
 "null_id":("installation_id",None),
 "nul_id":("installation_id","ci-install-\x00-001"),
 "unicode_id":("installation_id","ci-instаll-001"),
}
for name,(field,value) in ATTACKS.items():
    setattr(IndependentWitnessTests,"test_checkpoint_attack_"+name,checkpoint_attack(field,value))

def pin_attack(pin):
    def test(self):
        before=ref.ledger_snapshot(self.store)
        self.blocked(self.run_flow(adapter=self.make_adapter(pin=pin)))
        self.assertEqual(before,ref.ledger_snapshot(self.store))
    return test
for name,pin in (("missing",None),("empty",""),("bool",True),("integer",1),
                 ("unknown_key","00"*32),("uppercase","AB"*32)):
    setattr(IndependentWitnessTests,"test_separate_pin_"+name,pin_attack(pin))
