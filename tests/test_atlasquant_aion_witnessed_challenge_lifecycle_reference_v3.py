"""V3 adversarial lifecycle, ONLY Windows/Linux disposable GitHub CI.

Ephemeral signer objects stay in RAM. No private serialization, owner key,
network/provider/installer or physical owner-computer experiment.
"""
from __future__ import annotations
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import test_atlasquant_aion_dual_ed25519_public_crypto_bridge_v1 as upstream
import atlasquant_aion_durable_dual_ed25519_challenge_registry_v1 as ledger
import atlasquant_aion_independent_monotonic_witness_reference_v2 as v2
import atlasquant_aion_witnessed_challenge_lifecycle_reference_v3 as v3

ISSUED="2026-10-08T12:00:00Z"
NOW="2026-10-08T12:00:30Z"
EXPIRES="2026-10-08T12:05:00Z"
NONCE="ba"*32
OTHER="ac"*32


class WitnessPort:
    """Test-only signing wrapper; independent live state supplied separately."""
    def __init__(self,scope,snapshot,policy,pair=None):
        self.pair=pair or upstream.DisposablePair()
        self.state=v3.LifecycleWitnessState(scope=scope,initial_snapshot=snapshot,
            initial_policy=policy,witness_public_pin=self.pair.public_hex)
    def wrap(self,cp):
        return {"checkpoint":copy.deepcopy(cp),"signature_hex":self.pair._private.sign(v3.checkpoint_message(cp)).hex()}
    def prepare(self,**kwargs):
        return self.wrap(self.state.prepare(**kwargs))
    def recover(self,**kwargs):
        with self.state.lock:
            cp=self.state.confirmation_candidate(**kwargs)
            envelope=self.wrap(cp)
            return self.state.recover(**kwargs,envelope=envelope)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        if (os.environ.get("GITHUB_ACTIONS")!="true"
                or os.environ.get("RUNNER_ENVIRONMENT")!="github-hosted"
                or os.environ.get("RUNNER_OS") not in ("Windows","Linux")):
            raise RuntimeError("Disposable hosted CI only")
        self.fixture=upstream.DualEd25519MathematicalBridgeTests(methodName="runTest")
        self.fixture.setUp()
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=str(Path(self.temp.name).resolve())
        self.path=str(Path(self.root)/"lifecycle.sqlite3")
        self.store=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root,create=True)
        self.scope={"installation_id":"ci-install-0001","trust_chain_id":"ci-trust-chain-0001",
            "witness_id":"ci-witness-0001","owner_public_key_sha256":self.fixture.owner.fingerprint,
            "collector_public_key_sha256":self.fixture.collector.fingerprint,
            "custody_sha256":v2.custody_digest(self.fixture.proposal)}
        self.floor={"generation":7,"digest":self.fixture.proposal["policy_sha256"]}
        self.witness=WitnessPort(self.scope,v2.ledger_snapshot(self.store),self.floor)
        self.adapter=self.make_adapter()
        self.tx=0
        self.clock=ISSUED

    def make_adapter(self,witness=None,state=None,pin=None):
        return v3.LifecycleAdapter(store=self.store,witness=witness or self.witness,
            trusted_state=state or self.witness.state,
            trusted_public_pin=pin if pin is not None else self.witness.pair.public_hex)

    def sign(self,body,raw=None):
        return {"transition":copy.deepcopy(body),
            "owner_public_key_hex":self.fixture.owner.public_hex,
            "owner_signature_hex":self.fixture.owner._private.sign(v3.transition_message(body,"owner")).hex(),
            "collector_public_key_hex":self.fixture.collector.public_hex,
            "collector_signature_hex":self.fixture.collector._private.sign(v3.transition_message(body,"collector")).hex(),
            "v1_request":copy.deepcopy(raw)}

    def request(self,op="ISSUE_CHALLENGE",nonce=NONCE,*,proposal=None,time=None,expires=EXPIRES):
        self.tx+=1
        proposal=copy.deepcopy(proposal or self.fixture.proposal)
        observed=time or (self.clock if op=="ISSUE_CHALLENGE" else EXPIRES if op=="EXPIRE_CHALLENGE" else NOW)
        body=v3.build_transition(store=self.store,state=self.witness.state,operation=op,
            proposal=proposal,nonce=nonce,transaction_id=f"{self.tx:064x}",observed_at=observed,
            issued_at=observed if op=="ISSUE_CHALLENGE" else None,expires_at=expires if op=="ISSUE_CHALLENGE" else None)
        raw=self.fixture.payload(nonce=nonce,proposal=proposal) if op in ("CONSUME_CHALLENGE","EXPIRE_CHALLENGE") else None
        return self.sign(body,raw)

    def run_request(self,request,adapter=None):
        out=(adapter or self.adapter).run(request=request)
        if out["sqlite_transition_committed"]:self.clock=request["transition"]["observed_at"]
        self.gates(out)
        return out

    def gates(self,out):
        for key in v3.FALSE_GATES:self.assertIs(out[key],False,key)
        self.assertIs(out["distributed_atomicity_verified"],False)
        self.assertIs(out["exactly_once_external_execution_verified"],False)

    def confirmed(self,out):
        self.assertEqual(out["state"],"REFERENCE_TRANSITION_CONFIRMED",out)
        for key in ("transition_mathematically_verified","transition_reserved_by_reference_witness",
                    "sqlite_transition_committed","checkpoint_mathematically_verified","reference_ledger_matches_witness"):
            self.assertIs(out[key],True,key)
        self.gates(out)

    def blocked(self,out):
        self.assertEqual(out["state"],"BLOCKED",out);self.assertFalse(out["reference_ledger_matches_witness"]);self.gates(out)

    def issue(self,nonce=NONCE,**kwargs):
        request=self.request(nonce=nonce,**kwargs)
        out=self.run_request(request);self.confirmed(out)
        return request,out

    def apply(self,request):
        b=request["transition"];op=b["operation"]
        if op=="ISSUE_CHALLENGE":
            return self.store.issue(proposal=b["proposal"],nonce=b["nonce"],issued_at=b["issued_at"],expires_at=b["expires_at"])
        if op=="REVOKE_CHALLENGE":
            return self.store.revoke(nonce=b["nonce"],now_ts=b["observed_at"])
        return self.store.consume(request=request["v1_request"],now_ts=b["observed_at"])

    def test_first_issue_empty_bootstrap_is_witnessed(self):
        self.assertEqual(self.witness.state.history,[])
        self.issue()
        self.assertEqual(self.store.inspect()["states"],{NONCE:"ISSUED"})
        self.assertIsNone(self.store.inspect()["policy"])
        self.assertEqual(self.witness.state.head["checkpoint_sequence"],1)

    def test_subsequent_issue_no_reset_or_arbitrary_resynchronization(self):
        initial=self.witness.state.initial_hash
        self.issue();self.issue(OTHER)
        self.assertEqual(self.witness.state.initial_hash,initial)
        self.assertEqual(len(self.witness.state.history),2)
        self.assertEqual(self.store.inspect()["event_count"],2)
        self.assertEqual(set(self.store.inspect()["states"]),{NONCE,OTHER})

    def test_issue_then_consume(self):
        self.issue();self.confirmed(self.run_request(self.request("CONSUME_CHALLENGE")))
        self.assertEqual(self.store.inspect()["states"][NONCE],"CONSUMED")
        self.assertEqual(len(self.witness.state.used),2)

    def test_issue_then_expire_untrusted_clock_not_temporal_proof(self):
        self.issue();out=self.run_request(self.request("EXPIRE_CHALLENGE"));self.confirmed(out)
        self.assertEqual(self.store.inspect()["states"][NONCE],"EXPIRED")
        self.assertFalse(out["trusted_clock_verified"]);self.assertFalse(out["temporal_expiration_proven"])

    def test_issue_then_revoke(self):
        self.issue();self.confirmed(self.run_request(self.request("REVOKE_CHALLENGE")))
        self.assertEqual(self.store.inspect()["states"][NONCE],"REVOKED")

    def test_new_issue_after_consumption_uses_same_witness(self):
        self.issue();self.confirmed(self.run_request(self.request("CONSUME_CHALLENGE")))
        self.issue(OTHER)
        self.assertEqual(self.witness.state.head["checkpoint_sequence"],3)
        self.assertEqual(self.store.inspect()["states"][OTHER],"ISSUED")

    def test_nonempty_v2_ledger_cannot_silently_bootstrap_v3(self):
        self.issue()
        with self.assertRaises(ValueError):
            WitnessPort(self.scope,v2.ledger_snapshot(self.store),self.floor)

    def test_recreated_empty_db_does_not_reset_independent_witness(self):
        self.issue();Path(self.path).unlink()
        self.store=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root,create=True)
        self.adapter=self.make_adapter()
        with self.assertRaises(ValueError):self.request(nonce=OTHER)
        self.assertEqual(len(self.witness.state.history),1)

    def test_db_restore_witness_preserved_blocks_old_issue(self):
        backup=Path(self.root)/"before.sqlite3";shutil.copyfile(self.path,backup)
        request,_=self.issue()
        shutil.copyfile(backup,self.path)
        self.blocked(self.run_request(request))
        self.assertEqual(self.store.inspect()["states"],{})
        self.assertEqual(len(self.witness.state.history),1)

    def test_db_and_local_ticket_restore_with_witness_preserved_blocks(self):
        request,out=self.issue()
        backup=Path(self.root)/"issued.sqlite3";shutil.copyfile(self.path,backup)
        consume=self.request("CONSUME_CHALLENGE");ticket=self.adapter.prepare(request=consume)
        self.apply(consume)
        self.confirmed(self.adapter.recover(request=consume,ticket=ticket))
        shutil.copyfile(backup,self.path)
        self.blocked(self.adapter.recover(request=consume,ticket=ticket))
        self.blocked(self.run_request(consume))
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_db_and_witness_both_restored_protection_disappears(self):
        snapshot=v2.ledger_snapshot(self.store)
        backup=Path(self.root)/"empty.sqlite3";shutil.copyfile(self.path,backup)
        request,_=self.issue()
        shutil.copyfile(backup,self.path)
        # Explicit attacker reset of BOTH independent state and ledger.
        self.witness=WitnessPort(self.scope,snapshot,self.floor,pair=self.witness.pair)
        self.adapter=self.make_adapter()
        out=self.run_request(request);self.confirmed(out)
        self.assertFalse(out["protected_witness_storage_verified"])
        self.assertFalse(out["hardware_antirollback_verified"])

    def test_valid_ephemeral_signature_does_not_authenticate_owner(self):
        out=self.issue()[1]
        self.assertTrue(out["transition_mathematically_verified"])
        self.assertFalse(out["trusted_owner_identity_verified"])
        self.assertFalse(out["owner_identity_authenticated"])

    def test_valid_checkpoint_not_tpm_hsm_or_real_service(self):
        out=self.issue()[1]
        self.assertTrue(out["checkpoint_mathematically_verified"])
        self.assertFalse(out["protected_witness_storage_verified"]);self.gates(out)

    def test_two_concurrent_issues_one_stale_intent_new_signed_retry(self):
        requests=[self.request(nonce=n) for n in (NONCE,OTHER)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(self.run_request,requests))
        self.assertEqual(sum(r["reference_ledger_matches_witness"] for r in results),1)
        self.assertEqual(len(self.witness.state.history),1)
        loser=requests[next(i for i,r in enumerate(results) if not r["reference_ledger_matches_witness"])]
        self.issue(loser["transition"]["nonce"])
        self.assertEqual(len(self.witness.state.history),2)

    def race(self,ops):
        self.issue()
        requests=[self.request(op) for op in ops]
        with ThreadPoolExecutor(max_workers=len(ops)) as pool:
            results=list(pool.map(self.run_request,requests))
        self.assertEqual(sum(r["reference_ledger_matches_witness"] for r in results),1)
        self.assertEqual(len(self.witness.state.history),2)
        self.assertEqual(self.store.inspect()["event_count"],2)
        for out in results:self.gates(out)
        return self.store.inspect()["states"][NONCE]

    def test_two_concurrent_consumptions_single_terminal(self):
        self.assertEqual(self.race(("CONSUME_CHALLENGE","CONSUME_CHALLENGE")),"CONSUMED")

    def test_consumption_vs_revocation_single_terminal(self):
        self.assertIn(self.race(("CONSUME_CHALLENGE","REVOKE_CHALLENGE")),("CONSUMED","REVOKED"))

    def test_consumption_vs_expiration_single_terminal(self):
        self.assertIn(self.race(("CONSUME_CHALLENGE","EXPIRE_CHALLENGE")),("CONSUMED","EXPIRED"))

    def test_eight_threads_same_signed_transaction_one_confirmation(self):
        self.issue();request=self.request("CONSUME_CHALLENGE")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.run_request(request),range(8)))
        self.assertEqual(sum(r["reference_ledger_matches_witness"] for r in results),1)
        self.assertEqual(len(self.witness.state.history),2)

    def high_proposal(self):
        proposal=copy.deepcopy(self.fixture.proposal)
        proposal["policy_generation"]=8;proposal["policy_sha256"]="sha256:"+"f"*64
        return proposal

    def test_issue_race_with_policy_change_never_rolls_back(self):
        high=self.high_proposal()
        self.issue(OTHER,proposal=high)
        requests=[self.request(nonce=NONCE),self.request("CONSUME_CHALLENGE",OTHER,proposal=high)]
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(self.run_request,requests))
        self.assertEqual(sum(r["reference_ledger_matches_witness"] for r in results),1)
        if self.store.inspect()["states"][OTHER]=="ISSUED":
            self.confirmed(self.run_request(self.request("CONSUME_CHALLENGE",OTHER,proposal=high)))
        self.assertEqual(self.witness.state.current_policy()["generation"],8)
        with self.assertRaises(ValueError):self.request(nonce="ad"*32)

    def test_issue_higher_policy_does_not_advance_global_generation(self):
        self.issue(proposal=self.high_proposal())
        self.assertEqual(self.witness.state.current_policy(),self.floor)
        self.assertIsNone(self.store.inspect()["policy"])

    def test_old_consume_intent_blocked_after_policy_change(self):
        self.issue();high=self.high_proposal();self.issue(OTHER,proposal=high)
        old=self.request("CONSUME_CHALLENGE")
        self.confirmed(self.run_request(self.request("CONSUME_CHALLENGE",OTHER,proposal=high)))
        self.blocked(self.run_request(old))
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_old_generation_challenge_can_be_revoked_after_policy_change(self):
        self.issue();high=self.high_proposal();self.issue(OTHER,proposal=high)
        self.confirmed(self.run_request(self.request("CONSUME_CHALLENGE",OTHER,proposal=high)))
        self.confirmed(self.run_request(self.request("REVOKE_CHALLENGE")))
        self.assertEqual(self.witness.state.current_policy()["generation"],8)

    def test_old_generation_challenge_can_expire_after_policy_change(self):
        self.issue();high=self.high_proposal();self.issue(OTHER,proposal=high)
        self.confirmed(self.run_request(self.request("CONSUME_CHALLENGE",OTHER,proposal=high)))
        self.confirmed(self.run_request(self.request("EXPIRE_CHALLENGE")))
        self.assertEqual(self.witness.state.current_policy()["generation"],8)

    def test_early_expiry_rejected_no_strong_clock_claim(self):
        self.issue()
        with self.assertRaises(ValueError):self.request("EXPIRE_CHALLENGE",time=NOW)
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_expired_challenge_consumption_builder_rejects(self):
        self.issue()
        with self.assertRaises(ValueError):self.request("CONSUME_CHALLENGE",time=EXPIRES)

    def test_before_commit_failure_pending_not_repaired(self):
        request=self.request()
        with patch.object(self.store,"_commit",side_effect=sqlite3.OperationalError("before commit")):
            out=self.run_request(request);self.blocked(out)
        self.assertEqual(self.store.inspect()["states"],{})
        self.blocked(self.adapter.recover(request=request,ticket=out["ticket"]))
        self.assertIsNotNone(self.witness.state.pending)

    def test_after_commit_lost_ack_explicit_recovery(self):
        request=self.request();original=self.store._commit
        def lost(conn):
            original(conn);raise sqlite3.OperationalError("lost ack")
        with patch.object(self.store,"_commit",side_effect=lost):
            out=self.run_request(request);self.blocked(out)
        self.assertFalse(out["sqlite_transition_committed"])
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")
        self.confirmed(self.adapter.recover(request=request,ticket=out["ticket"]))
        self.assertEqual(len(self.witness.state.history),1)

    def test_before_confirmation_failure_actual_sqlite_fact_separate(self):
        request=self.request()
        with patch.object(self.witness,"recover",side_effect=OSError("unavailable")):
            out=self.run_request(request);self.blocked(out)
        self.assertTrue(out["sqlite_transition_committed"])
        self.assertFalse(out["checkpoint_mathematically_verified"])
        self.confirmed(self.adapter.recover(request=request,ticket=out["ticket"]))

    def test_after_confirmation_reply_lost_no_second_history_entry(self):
        request=self.request();original=self.witness.recover
        def lost(**kwargs):
            original(**kwargs);raise OSError("reply lost")
        with patch.object(self.witness,"recover",side_effect=lost):
            out=self.run_request(request);self.blocked(out)
        self.assertEqual(len(self.witness.state.history),1)
        self.confirmed(self.adapter.recover(request=request,ticket=out["ticket"]))
        self.assertEqual(len(self.witness.state.history),1)

    def test_restart_adapter_recovers_original_intent_and_repetition_is_observation(self):
        request=self.request();ticket=self.adapter.prepare(request=request);self.apply(request)
        self.store=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        restarted=self.make_adapter()
        first=restarted.recover(request=request,ticket=ticket);self.confirmed(first)
        before=v2.ledger_snapshot(self.store)
        self.confirmed(restarted.recover(request=request,ticket=ticket))
        self.blocked(restarted.run(request=request))
        self.assertEqual(before,v2.ledger_snapshot(self.store));self.assertEqual(len(self.witness.state.history),1)

    def test_restart_before_commit_no_auto_consume(self):
        request=self.request();ticket=self.adapter.prepare(request=request)
        self.store=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        self.blocked(self.make_adapter().recover(request=request,ticket=ticket))
        self.assertEqual(self.store.inspect()["states"],{})

    def test_witness_unavailable_during_recovery_no_local_fallback(self):
        request=self.request();ticket=self.adapter.prepare(request=request);self.apply(request)
        with patch.object(self.witness,"recover",side_effect=OSError("unavailable")):
            self.blocked(self.adapter.recover(request=request,ticket=ticket))
        self.assertIsNone(self.witness.state.head)

    def test_recovery_requires_original_validated_intent(self):
        request,out=self.issue()
        forged=copy.deepcopy(request);forged["transition"]["transaction_id"]="ad"*32
        self.blocked(self.adapter.recover(request=forged,ticket=out["ticket"]))

    def test_recovery_without_signed_prepare_rejected(self):
        request=self.request();ticket=self.adapter.prepare(request=request);self.apply(request)
        self.blocked(self.adapter.recover(request=request,ticket={}))
        self.assertIsNone(self.witness.state.head)

    def test_old_receipt_not_current_after_new_issue(self):
        request,out=self.issue();self.issue(OTHER)
        self.blocked(self.adapter.recover(request=request,ticket=out["ticket"]))

    def test_untrusted_port_head_cannot_supply_expected_state(self):
        request=self.request()
        class FakePort:
            def prepare(_,**kwargs):
                cp={**request["transition"],"checkpoint_schema":v3.CHECKPOINT_SCHEMA,"phase":"PREPARED"}
                return self.witness.wrap(cp)
            def recover(_,**kwargs):raise AssertionError("must not consume")
        out=self.run_request(request,adapter=self.make_adapter(witness=FakePort()));self.blocked(out)
        self.assertEqual(self.store.inspect()["states"],{})

    def test_db_audit_corruption_blocks_no_write_or_repair(self):
        self.issue();request=self.request("CONSUME_CHALLENGE")
        with closing(sqlite3.connect(self.path)) as conn,conn:
            conn.execute("UPDATE evidence SET digest=?",("sha256:"+"f"*64,))
        before=Path(self.path).read_bytes()
        self.blocked(self.run_request(request));self.assertEqual(before,Path(self.path).read_bytes())

    def test_signed_witness_history_tamper_detected(self):
        self.issue();request=self.request(nonce=OTHER)
        self.witness.state.history[0]["envelope"]["checkpoint"]["generation"]=6
        self.blocked(self.run_request(request))
        self.assertEqual(self.store.inspect()["states"],{NONCE:"ISSUED"})

    def test_witness_history_removed_not_silently_reinitialized(self):
        self.issue();request=self.request(nonce=OTHER)
        self.witness.state.history.clear()
        self.blocked(self.run_request(request));self.assertIsNotNone(self.witness.state.head)

    def test_witness_head_only_rollback_detected(self):
        self.issue();request=self.request(nonce=OTHER)
        self.witness.state.head=None
        self.blocked(self.run_request(request))

    def test_witness_pending_binding_tamper_blocks_commit(self):
        request=self.request();ticket=self.adapter.prepare(request=request)
        self.witness.state.pending["ledger_state_sha256"]="sha256:"+"f"*64
        self.apply(request)
        self.blocked(self.adapter.recover(request=request,ticket=ticket))
        self.assertIsNone(self.witness.state.head)

    def test_mutation_outputs_do_not_change_live_history(self):
        request,out=self.issue();head=copy.deepcopy(self.witness.state.head)
        out["ticket"]["checkpoint"]["generation"]=0;request["transition"]["generation"]=0
        self.assertEqual(head,self.witness.state.head)
        self.witness.state.validate_history()

    def test_repeat_recovery_100_times_deterministic_no_double_confirmation(self):
        request,out=self.issue()
        repeated=[self.adapter.recover(request=request,ticket=out["ticket"]) for _ in range(100)]
        self.assertTrue(all(r==repeated[0] for r in repeated))
        self.assertTrue(repeated[0]["reference_ledger_matches_witness"])
        self.assertEqual(len(self.witness.state.history),1)

    def test_full_chain_zero_network_subprocess(self):
        with patch("socket.socket",side_effect=AssertionError("network forbidden")), \
             patch("subprocess.Popen",side_effect=AssertionError("process forbidden")):
            self.issue();self.confirmed(self.run_request(self.request("CONSUME_CHALLENGE")))

    def test_public_verification_zero_filesystem_keys_reads_or_writes(self):
        _,out=self.issue();envelope=self.witness.state.history[0]["envelope"]
        with patch("builtins.open",side_effect=AssertionError("I/O forbidden")), \
             patch("pathlib.Path.open",side_effect=AssertionError("I/O forbidden")):
            self.assertTrue(v3.verify_checkpoint(envelope,pin=self.witness.pair.public_hex,expected=envelope["checkpoint"]))

    def test_environment_flags_never_make_physical_authority(self):
        with patch.dict(os.environ,{"INSTALLER_READY":"true","TRUSTED_OWNER":"1","SAFE_TO_RESUME":"true"}):
            self.issue()

    def test_bool_extra_authorization_request_rejected(self):
        request=self.request();request["installer_authorized"]=True
        self.blocked(self.run_request(request));self.assertEqual(self.store.inspect()["states"],{})

    def test_large_request_bounds_rejected_before_reservation(self):
        self.blocked(self.adapter.run(request=[True]*100000))
        self.assertIsNone(self.witness.state.pending)

    def test_recursive_request_fail_closed(self):
        request={};request["cycle"]=request
        self.blocked(self.adapter.run(request=request))

    def test_math_valid_wrong_witness_key_never_confirms(self):
        request=self.request();attacker=upstream.DisposablePair();original=self.witness.wrap
        def wrong(cp):
            return {"checkpoint":copy.deepcopy(cp),"signature_hex":attacker._private.sign(v3.checkpoint_message(cp)).hex()}
        with patch.object(self.witness,"wrap",side_effect=wrong):self.blocked(self.run_request(request))
        self.assertEqual(self.store.inspect()["states"],{})

    def test_substituted_public_pin_rejected_constructor(self):
        with self.assertRaises(ValueError):self.make_adapter(pin=upstream.DisposablePair().public_hex)

    def test_owner_signature_cannot_replace_collector(self):
        request=self.request();request["collector_signature_hex"]=request["owner_signature_hex"]
        self.blocked(self.run_request(request))

    def test_collector_signature_cannot_replace_owner(self):
        request=self.request();request["owner_signature_hex"]=request["collector_signature_hex"]
        self.blocked(self.run_request(request))

    def test_v1_signature_cannot_satisfy_v3_operation(self):
        request=self.request()
        raw=self.fixture.payload()
        request["owner_signature_hex"]=raw["owner_signature_hex"]
        request["collector_signature_hex"]=raw["collector_signature_hex"]
        self.blocked(self.run_request(request))

    def test_p256_host_claim_cannot_substitute_ed25519_role(self):
        request=self.request();request["owner_public_key_hex"]="04"+"ab"*64
        self.blocked(self.run_request(request))

    def test_custody_budget_mutations_change_v3_intent_not_authenticate_custody(self):
        original=self.request()["transition"]
        for field,value in (("custodian_id","ci-different-owner-002"),
                            ("custody_boundary","INDEPENDENT_REMOTE_TRUST_DOMAIN_CANDIDATE")):
            changed=copy.deepcopy(original);changed["proposal"]["owner"][field]=value
            with self.assertRaises(ValueError):v3.transition_message(changed,"owner")
        changed=copy.deepcopy(original);changed["proposal"]["estimated_monthly_brl"]=200
        with self.assertRaises(ValueError):v3.transition_message(changed,"owner")


    def test_missing_required_field_not_defaulted(self):
        request=self.request();del request["transition"]["transaction_id"]
        self.blocked(self.run_request(request));self.assertIsNone(self.witness.state.pending)

    def test_extra_authorization_field_in_transition_rejected(self):
        request=self.request();request["transition"]["installer_authorized"]=True
        self.blocked(self.run_request(request))

    def test_expiration_wrong_prior_state_cannot_resurrect_terminal(self):
        self.issue();request=self.request("EXPIRE_CHALLENGE")
        self.confirmed(self.run_request(self.request("REVOKE_CHALLENGE")))
        self.blocked(self.run_request(request))
        self.assertEqual(self.store.inspect()["states"][NONCE],"REVOKED")

    def test_pending_prepare_reply_loss_blocks_without_original_ticket(self):
        request=self.request();original=self.witness.prepare
        def lost(**kwargs):
            original(**kwargs);raise OSError("prepare reply lost")
        with patch.object(self.witness,"prepare",side_effect=lost):out=self.run_request(request)
        self.blocked(out);self.assertIsNone(out["ticket"])
        self.assertIsNotNone(self.witness.state.pending)
        self.assertEqual(self.store.inspect()["states"],{})
        self.blocked(self.adapter.recover(request=request,ticket=None))

def terminal_attack(operation):
    def test(self):
        self.issue();self.confirmed(self.run_request(self.request(operation)))
        for op in v3.OPERATIONS:
            with self.assertRaises(ValueError):self.request(op,time=EXPIRES if operation=="EXPIRE_CHALLENGE" else NOW)
        self.assertEqual(self.store.inspect()["states"][NONCE],v3.NEXT[operation])
        self.assertEqual(len(self.witness.state.history),2)
    return test
for op in v3.OPERATIONS[1:]:
    setattr(LifecycleTests,"test_terminal_tombstone_"+op.lower(),terminal_attack(op))

def body_attack(field,value):
    def test(self):
        request=self.request()
        request["transition"][field]=value
        self.blocked(self.run_request(request))
        self.assertEqual(self.store.inspect()["states"],{})
        self.assertIsNone(self.witness.state.head)
    return test

BODY_ATTACKS={
 "schema":("schema","FUTURE_UNKNOWN"),"version":("version",4),
 "bool_version":("version",True),"overflow_sequence":("checkpoint_sequence",2**32),
 "bool_sequence":("checkpoint_sequence",True),"zero_sequence":("checkpoint_sequence",0),
 "negative_generation":("generation",-1),"bool_generation":("generation",True),
 "float_generation":("generation",7.0),"nonce_short":("nonce","aa"),
 "nonce_bool":("nonce",True),"transaction_changed":("transaction_id","ad"*32),
 "prior_ledger_hash":("previous_ledger_sha256","sha256:"+"f"*64),
 "next_ledger_hash":("ledger_state_sha256","sha256:"+"f"*64),
 "policy_hash":("policy_sha256","sha256:"+"f"*64),
 "previous_checkpoint":("previous_checkpoint_sha256","sha256:"+"f"*64),
 "installation":("installation_id","ci-other-install-001"),
 "chain":("trust_chain_id","ci-other-chain-001"),
 "witness":("witness_id","ci-other-witness-001"),
 "owner":("owner_public_key_sha256","sha256:"+"f"*64),
 "collector":("collector_public_key_sha256","sha256:"+"f"*64),
 "binary":("collector_binary_sha256","sha256:"+"f"*64),
 "custody":("custody_sha256","sha256:"+"f"*64),
 "clock":("clock_trusted",True),"time":("observed_at","2026-10-08T12:00:00"),
 "prior_state":("previous_state","CONSUMED"),"next_state":("next_state","CONSUMED"),
 "purpose":("purpose","INSTALLER_AUTHORIZATION"),
}
for name,(field,value) in BODY_ATTACKS.items():
    setattr(LifecycleTests,"test_closed_body_"+name,body_attack(field,value))

def purpose_swap(target):
    def test(self):
        request=self.request();body=request["transition"]
        body["operation"]=target;body["purpose"]=v3.PURPOSES[target]
        body["previous_state"]="ISSUED";body["next_state"]=v3.NEXT[target]
        # Shape/domain are valid, but signature is from ISSUE and MUST fail.
        if target in ("CONSUME_CHALLENGE","EXPIRE_CHALLENGE"):request["v1_request"]=self.fixture.payload()
        with self.assertRaisesRegex(ValueError,"TRANSITION_SIGNATURE_INVALID"):
            v3.verify_request(request,self.scope)
        self.blocked(self.run_request(request));self.assertEqual(self.store.inspect()["states"],{})
    return test
for op in v3.OPERATIONS[1:]:
    setattr(LifecycleTests,"test_issue_signature_not_"+op.lower(),purpose_swap(op))


def signed_forgery(field,value):
    def test(self):
        body=self.request()["transition"];body[field]=value
        request=self.sign(body)
        self.assertEqual(v3.verify_request(request,self.scope),request)
        self.blocked(self.run_request(request))
        self.assertEqual(self.store.inspect()["states"],{})
        self.assertIsNone(self.witness.state.pending)
    return test
for name,field,value in (
    ("next_hash","ledger_state_sha256","sha256:"+"f"*64),
    ("prior_hash","previous_ledger_sha256","sha256:"+"f"*64),
    ("next_sequence","checkpoint_sequence",2),
    ("prior_checkpoint","previous_checkpoint_sha256","sha256:"+"f"*64),
    ("global_policy","policy_sha256","sha256:"+"f"*64),
):
    setattr(LifecycleTests,"test_math_valid_target_forgery_"+name,signed_forgery(field,value))
