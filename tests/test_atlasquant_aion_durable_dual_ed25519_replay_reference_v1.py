"""Adversarial ACID/replay reference, ONLY disposable GitHub runner fixtures.

Private Ed25519 keys are inherited test fixtures in runner RAM, never exported,
logged, saved or enrolled. Public signatures may cross child stdin, not the DB.
"""
from __future__ import annotations
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_atlasquant_aion_dual_ed25519_public_crypto_bridge_v1 as upstream
import atlasquant_aion_durable_dual_ed25519_challenge_registry_v1 as ledger
from atlasquant_aion_dual_ed25519_durable_replay_reference_v1 import verify_and_consume_reference

ISSUED = "2026-10-08T12:00:00Z"
NOW = "2026-10-08T12:00:30Z"
EXPIRES = "2026-10-08T12:05:00Z"
NONCE = "ba"*32
CHILD = """
import json,sys,os
from atlasquant_aion_durable_dual_ed25519_challenge_registry_v1 import ReferenceChallengeRegistry
p=json.loads(sys.stdin.read())
r=ReferenceChallengeRegistry(p['path'],fixture_root=p['root'])
if p.get('crash'):
    r._commit=lambda conn:os._exit(73)
out=r.consume(request=p['request'],now_ts=p['now'])
print(json.dumps({'consumed':out['nonce_transaction_consumed'],'state':out['state']}))
"""


class DurableReplayReferenceTests(unittest.TestCase):
    def setUp(self):
        if (os.environ.get("GITHUB_ACTIONS") != "true"
                or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
                or os.environ.get("RUNNER_OS") not in ("Linux","Windows")):
            raise RuntimeError("Disposable hosted CI required; never run on owner host")
        self.fixture = upstream.DualEd25519MathematicalBridgeTests(methodName="runTest")
        self.fixture.setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = str(Path(self.temp.name).resolve())
        self.path = str(Path(self.root)/"challenges.sqlite3")
        self.store = ledger.ReferenceChallengeRegistry(self.path, fixture_root=self.root, create=True)

    def request(self, *, nonce=NONCE, generation=7, policy=None):
        proposal = copy.deepcopy(self.fixture.proposal)
        proposal["policy_generation"] = generation
        if policy is not None:
            proposal["policy_sha256"] = policy
        return self.fixture.payload(nonce=nonce, proposal=proposal)

    def issue(self, request=None, *, issued_at=ISSUED, expires_at=EXPIRES):
        request = request or self.request()
        return self.store.issue(proposal=request["proposal"],nonce=request["nonce"],
                                issued_at=issued_at,expires_at=expires_at)

    def consume(self, request=None, *, now=NOW, store=None):
        return verify_and_consume_reference(registry=store or self.store,
                    request=request or self.request(),now_ts=now)

    def false_gates(self, out):
        for key in ledger.FALSE_GATES:
            self.assertIs(out[key],False,key)
        if out.get("receipt"):
            for key in ledger.FALSE_GATES:
                self.assertIs(out["receipt"][key],False,key)

    def child(self, request, *, crash=False):
        return subprocess.run([sys.executable,"-c",CHILD],
            input=json.dumps({"path":self.path,"root":self.root,"request":request,"now":NOW,"crash":crash}),
            text=True,capture_output=True,timeout=30,check=False)

    def test_first_consume_is_math_and_transaction_not_identity_or_authority(self):
        self.assertEqual(self.issue()["state"],"ISSUED")
        out=self.consume()
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertTrue(out["nonce_transaction_consumed"])
        self.false_gates(out)
        self.assertEqual(self.store.inspect()["policy"],{"generation":7,"digest":self.fixture.proposal["policy_sha256"]})
        self.assertEqual(self.store.inspect()["event_count"],2)

    def test_second_attempt_cannot_consume_again(self):
        self.issue()
        self.assertTrue(self.consume()["nonce_transaction_consumed"])
        out=self.consume()
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertFalse(out["nonce_transaction_consumed"])
        self.assertEqual(out["reason"],"CHALLENGE_CONSUMED")
        self.false_gates(out)
        self.assertEqual(self.store.inspect()["event_count"],2)

    def test_duplicate_issuance_never_replaces_nonce(self):
        self.issue()
        out=self.issue()
        self.assertEqual(out["state"],"BLOCKED")
        self.assertEqual(self.store.inspect()["event_count"],1)

    def test_expiry_at_boundary_is_persisted_and_blocks(self):
        self.issue()
        out=self.consume(now=EXPIRES)
        self.assertFalse(out["nonce_transaction_consumed"])
        self.assertEqual(self.store.inspect()["states"][NONCE],"EXPIRED")
        self.assertEqual(self.store.inspect()["event_count"],2)
        self.false_gates(out)

    def test_expired_nonce_is_never_reissued_or_pruned(self):
        self.issue()
        self.consume(now=EXPIRES)
        self.assertEqual(self.issue(issued_at=EXPIRES,expires_at="2026-10-08T12:06:00Z")["state"],"BLOCKED")
        self.assertEqual(self.store.inspect()["states"][NONCE],"EXPIRED")

    def test_nonexistent_nonce_with_valid_signatures_is_denied(self):
        out=self.consume()
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertFalse(out["nonce_transaction_consumed"])
        self.assertEqual(out["reason"],"CHALLENGE_NOT_FOUND")

    def test_revocation_is_durable_and_terminal(self):
        self.issue()
        self.assertEqual(self.store.revoke(nonce=NONCE,now_ts=NOW)["state"],"REVOKED")
        self.assertFalse(self.consume()["nonce_transaction_consumed"])
        self.assertEqual(self.issue()["state"],"BLOCKED")

    def test_consumed_nonce_cannot_be_revoked_or_reset(self):
        self.issue(); self.consume()
        self.assertEqual(self.store.revoke(nonce=NONCE,now_ts=NOW)["state"],"BLOCKED")
        self.assertEqual(self.store.inspect()["states"][NONCE],"CONSUMED")

    def test_thread_race_has_exactly_one_winner(self):
        self.issue()
        request=self.request()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.consume(copy.deepcopy(request)),range(8)))
        self.assertEqual(sum(r["nonce_transaction_consumed"] for r in results),1)
        self.assertEqual(self.store.inspect()["event_count"],2)
        for r in results:self.false_gates(r)

    def test_process_race_has_exactly_one_winner(self):
        self.issue()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.child(self.request()),range(4)))
        self.assertTrue(all(r.returncode==0 for r in results))
        self.assertEqual(sum(json.loads(r.stdout)["consumed"] for r in results),1)
        self.assertEqual(self.store.inspect()["event_count"],2)

    def test_restart_after_consumption_rejects_replay(self):
        self.issue()
        out=self.child(self.request())
        self.assertEqual(out.returncode,0,out.stderr[-300:])
        self.assertTrue(json.loads(out.stdout)["consumed"])
        reopened=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        self.assertFalse(self.consume(store=reopened)["nonce_transaction_consumed"])

    def test_crash_before_commit_rolls_back_all_three_changes(self):
        self.issue()
        out=self.child(self.request(),crash=True)
        self.assertEqual(out.returncode,73)
        reopened=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        snapshot=reopened.inspect()
        self.assertEqual(snapshot["states"][NONCE],"ISSUED")
        self.assertIsNone(snapshot["policy"])
        self.assertEqual(snapshot["event_count"],1)
        self.assertTrue(self.consume(store=reopened)["nonce_transaction_consumed"])

    def test_commit_failure_never_returns_consumption(self):
        self.issue()
        with patch.object(self.store,"_commit",side_effect=sqlite3.OperationalError("commit fault")):
            out=self.consume()
        self.assertFalse(out["nonce_transaction_consumed"]);self.false_gates(out)
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")
        self.assertIsNone(self.store.inspect()["policy"])

    def test_failure_after_real_commit_is_conservatively_denied(self):
        self.issue()
        def uncertain(conn):
            conn.commit()
            raise sqlite3.OperationalError("lost ack")
        with patch.object(self.store,"_commit",side_effect=uncertain):
            out=self.consume()
        self.assertFalse(out["nonce_transaction_consumed"]);self.false_gates(out)
        self.assertEqual(self.store.inspect()["states"][NONCE],"CONSUMED")
        self.assertFalse(self.consume()["nonce_transaction_consumed"])

    def test_issue_write_failure_rolls_back(self):
        with patch.object(self.store,"_event",side_effect=sqlite3.OperationalError("write fault")):
            self.assertEqual(self.issue()["state"],"BLOCKED")
        self.assertEqual(self.store.inspect()["states"],{})
        self.assertEqual(self.store.inspect()["event_count"],0)

    def test_consume_failure_after_row_update_rolls_back_receipt_and_policy(self):
        self.issue()
        with patch.object(self.store,"_event",side_effect=sqlite3.OperationalError("write fault")):
            out=self.consume()
        self.assertFalse(out["nonce_transaction_consumed"])
        snapshot=self.store.inspect()
        self.assertEqual(snapshot["states"][NONCE],"ISSUED")
        self.assertIsNone(snapshot["policy"]);self.assertEqual(snapshot["event_count"],1)

    def test_locked_database_blocks_without_grant(self):
        self.issue()
        conn=sqlite3.connect(self.path,isolation_level=None)
        try:
            conn.execute("BEGIN EXCLUSIVE")
            out=self.consume()
            self.assertFalse(out["nonce_transaction_consumed"]);self.false_gates(out)
        finally:
            conn.rollback();conn.close()
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_missing_database_not_silently_created(self):
        os.unlink(self.path)
        out=self.consume()
        self.assertFalse(out["nonce_transaction_consumed"])
        self.assertFalse(Path(self.path).exists())
        with self.assertRaises((ledger.ReferenceStoreError,sqlite3.Error)):
            ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)

    def test_corrupt_database_blocks(self):
        Path(self.path).write_bytes(b"corrupt fixture")
        out=self.consume()
        self.assertFalse(out["nonce_transaction_consumed"]);self.false_gates(out)

    def test_schema_version_mismatch_blocks(self):
        conn=sqlite3.connect(self.path)
        try:conn.execute("PRAGMA user_version=99");conn.commit()
        finally:conn.close()
        self.assertFalse(self.consume()["nonce_transaction_consumed"])

    def test_extra_table_is_schema_inconsistency(self):
        conn=sqlite3.connect(self.path)
        try:conn.execute("CREATE TABLE unexpected (x)");conn.commit()
        finally:conn.close()
        self.assertFalse(self.consume()["nonce_transaction_consumed"])

    def test_state_without_matching_evidence_blocks(self):
        self.issue()
        conn=sqlite3.connect(self.path)
        try:conn.execute("UPDATE challenges SET state='CONSUMED'");conn.commit()
        finally:conn.close()
        self.assertFalse(self.consume()["nonce_transaction_consumed"])

    def test_receipt_corruption_blocks_recovery(self):
        self.issue();self.consume()
        conn=sqlite3.connect(self.path)
        try:conn.execute("UPDATE challenges SET receipt='{}'");conn.commit()
        finally:conn.close()
        with self.assertRaises(ledger.ReferenceStoreError):self.store.inspect()

    def test_audit_head_tamper_blocks(self):
        self.issue()
        conn=sqlite3.connect(self.path)
        try:conn.execute("UPDATE evidence SET digest=?",("sha256:"+"f"*64,));conn.commit()
        finally:conn.close()
        self.assertFalse(self.consume()["nonce_transaction_consumed"])

    def test_event_deletion_blocks(self):
        self.issue()
        conn=sqlite3.connect(self.path)
        try:conn.execute("DELETE FROM evidence");conn.commit()
        finally:conn.close()
        self.assertFalse(self.consume()["nonce_transaction_consumed"])

    def test_policy_head_without_consumption_blocks(self):
        conn=sqlite3.connect(self.path)
        try:conn.execute("INSERT INTO policy VALUES(1,7,?)",("sha256:"+"e"*64,));conn.commit()
        finally:conn.close()
        self.assertFalse(self.consume()["nonce_transaction_consumed"])

    def test_same_generation_same_policy_different_nonce_is_allowed(self):
        self.issue();self.consume()
        request=self.request(nonce="bc"*32)
        self.assertEqual(self.issue(request)["state"],"ISSUED")
        self.assertTrue(self.consume(request)["nonce_transaction_consumed"])

    def test_same_generation_different_policy_is_rejected(self):
        self.issue();self.consume()
        request=self.request(nonce="bc"*32,policy="sha256:"+"f"*64)
        self.assertEqual(self.issue(request)["state"],"BLOCKED")

    def test_older_generation_rejected(self):
        self.issue();self.consume()
        self.assertEqual(self.issue(self.request(nonce="bc"*32,generation=6))["state"],"BLOCKED")

    def test_higher_issuance_alone_does_not_advance_generation(self):
        self.issue();self.consume()
        self.issue(self.request(nonce="bc"*32,generation=8,policy="sha256:"+"f"*64))
        self.assertEqual(self.store.inspect()["policy"]["generation"],7)

    def test_advance_requires_both_valid_role_signatures(self):
        self.issue();self.consume()
        request=self.request(nonce="bc"*32,generation=8,policy="sha256:"+"f"*64)
        self.issue(request);request["collector_signature_hex"]="00"*64
        self.assertFalse(self.consume(request)["nonce_transaction_consumed"])
        self.assertEqual(self.store.inspect()["policy"]["generation"],7)

    def test_concurrent_generations_cannot_regress(self):
        a=self.request(nonce="bc"*32,generation=8)
        b=self.request(nonce="bd"*32,generation=9,policy="sha256:"+"f"*64)
        self.issue(a);self.issue(b)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(self.consume,[a,b]))
        self.assertEqual(self.store.inspect()["policy"]["generation"],9)
        self.assertGreaterEqual(sum(r["nonce_transaction_consumed"] for r in results),1)

    def test_old_issued_challenge_blocked_after_new_policy_commit(self):
        a=self.request(generation=7);b=self.request(nonce="bc"*32,generation=8)
        self.issue(a);self.issue(b);self.consume(b)
        self.assertFalse(self.consume(a)["nonce_transaction_consumed"])
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_generation_survives_reopen(self):
        self.issue();self.consume()
        new=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        self.assertEqual(new.inspect()["policy"]["generation"],7)

    def test_uint32_maximum_generation_is_supported(self):
        request=self.request(generation=ledger.MAX_GENERATION)
        self.issue(request)
        self.assertTrue(self.consume(request)["nonce_transaction_consumed"])

    def test_clock_watermark_blocks_backward_time(self):
        self.issue();self.consume()
        out=self.consume(now=ISSUED)
        self.assertFalse(out["nonce_transaction_consumed"]);self.false_gates(out)

    def test_caller_verification_claim_is_not_accepted(self):
        self.issue()
        out=verify_and_consume_reference(registry=self.store,request={"signature_mathematically_valid":True},now_ts=NOW)
        self.assertFalse(out["nonce_transaction_consumed"])
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_receipt_cannot_be_reused_as_signed_request_or_installer_authority(self):
        self.issue();out=self.consume()
        replay=verify_and_consume_reference(registry=self.store,request=out["receipt"],now_ts=NOW)
        self.assertFalse(replay["nonce_transaction_consumed"]);self.false_gates(replay)
        self.false_gates(out["receipt"])

    def test_fake_registry_is_not_accepted(self):
        class Fake:
            def consume(self,**kw):raise AssertionError("untrusted callback")
        out=verify_and_consume_reference(registry=Fake(),request=self.request(),now_ts=NOW)
        self.assertFalse(out["nonce_transaction_consumed"]);self.false_gates(out)

    def test_restored_database_demonstrates_disk_antirollback_limit(self):
        self.issue()
        backup=str(Path(self.root)/"before.sqlite3")
        shutil.copyfile(self.path,backup)
        self.consume()
        # Administrator replaces the WHOLE unkeyed ledger; no external anchor.
        shutil.copyfile(backup,self.path)
        self.assertTrue(self.consume()["nonce_transaction_consumed"])
        self.assertFalse(self.consume()["hardware_antirollback_verified"])

    def test_no_private_key_or_signature_is_stored(self):
        request=self.request();self.issue(request);self.consume(request)
        conn=sqlite3.connect(self.path)
        try:
            text="".join(str(r) for table in ("challenges","evidence","policy","meta")
                         for r in conn.execute("SELECT * FROM "+table))
        finally:conn.close()
        for signature in (request["owner_signature_hex"],request["collector_signature_hex"]):
            self.assertNotIn(signature,text)
        for forbidden in ("private_key","owner_signature_hex","collector_signature_hex"):
            self.assertNotIn(forbidden,text)

    def test_fixture_creation_is_exclusive_and_never_resets_existing_db(self):
        with self.assertRaises(FileExistsError):
            ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root,create=True)

    def test_owner_host_path_not_accepted(self):
        with self.assertRaises(ledger.ReferenceStoreError):
            ledger.ReferenceChallengeRegistry("C:/am12/security.sqlite3",fixture_root=self.root,create=True)

    def test_environment_or_installer_claims_do_not_promote_gates(self):
        self.issue()
        with patch.dict(os.environ,{"AION_INSTALLER_AUTHORIZED":"true","HARDWARE_ANTIROLLBACK_VERIFIED":"true"}):
            self.false_gates(self.consume())

    def test_input_and_output_mutations_do_not_change_stored_evidence(self):
        request=self.request();saved=copy.deepcopy(request)
        self.issue(request);out=self.consume(request)
        self.assertEqual(request,saved)
        out["receipt"]["binding"]["policy_generation"]=0
        self.assertEqual(self.store.inspect()["policy"]["generation"],7)


    def test_read_only_sqlite_write_failure_is_denied(self):
        self.issue()
        original=self.store._connect
        def readonly():
            conn=original()
            conn.execute("PRAGMA query_only=ON")
            return conn
        with patch.object(self.store,"_connect",side_effect=readonly):
            out=self.consume()
        self.assertFalse(out["nonce_transaction_consumed"]);self.false_gates(out)
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_valid_resigned_different_policy_cannot_use_issued_nonce(self):
        self.issue()
        changed=self.request(policy="sha256:"+"f"*64)
        out=self.consume(changed)
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertEqual(out["reason"],"ISSUED_BINDING_MISMATCH")
        self.assertFalse(out["nonce_transaction_consumed"])

    def test_valid_resigned_new_owner_key_cannot_use_issued_nonce(self):
        self.issue()
        self.fixture.owner=upstream.DisposablePair()
        self.fixture.proposal["owner"]["public_key_sha256"]=self.fixture.owner.fingerprint
        out=self.consume(self.request())
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertEqual(out["reason"],"ISSUED_BINDING_MISMATCH")

    def test_valid_resigned_new_collector_key_cannot_use_issued_nonce(self):
        self.issue()
        self.fixture.collector=upstream.DisposablePair()
        self.fixture.proposal["collector"]["public_key_sha256"]=self.fixture.collector.fingerprint
        out=self.consume(self.request())
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertEqual(out["reason"],"ISSUED_BINDING_MISMATCH")

    def test_nonpositive_or_excessive_expiry_window_is_rejected(self):
        for expiry in (ISSUED,"2026-10-08T11:59:59Z","2026-10-08T12:05:01Z"):
            with self.subTest(expiry=expiry):
                self.assertEqual(self.issue(expires_at=expiry)["state"],"BLOCKED")
        self.assertEqual(self.store.inspect()["event_count"],0)

    def test_revocation_error_rolls_back(self):
        self.issue()
        with patch.object(self.store,"_event",side_effect=sqlite3.OperationalError("fault")):
            self.assertEqual(self.store.revoke(nonce=NONCE,now_ts=NOW)["state"],"BLOCKED")
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")

    def test_expiry_commit_error_does_not_leave_partial_transition(self):
        self.issue()
        with patch.object(self.store,"_commit",side_effect=sqlite3.OperationalError("fault")):
            self.assertFalse(self.consume(now=EXPIRES)["nonce_transaction_consumed"])
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")
        self.assertEqual(self.store.inspect()["event_count"],1)

    def test_application_clock_rollback_is_rejected_after_process_restart(self):
        self.issue();self.consume()
        reopened=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        self.assertFalse(self.consume(store=reopened,now=ISSUED)["nonce_transaction_consumed"])

    def test_retained_state_has_no_process_local_replay_cache_dependency(self):
        self.issue()
        reopened=ledger.ReferenceChallengeRegistry(self.path,fixture_root=self.root)
        self.assertTrue(self.consume(store=reopened)["nonce_transaction_consumed"])
        self.assertFalse(self.consume()["nonce_transaction_consumed"])

    def test_huge_or_hostile_input_is_denied_without_coercion(self):
        class Hostile:
            def __str__(self):raise AssertionError("coercion")
        for request in ({"proposal":Hostile()}, {"nonce":"x"*100000}, [0]*100000):
            with self.subTest(kind=type(request).__name__):
                out=verify_and_consume_reference(registry=self.store,request=request,now_ts=NOW)
                self.assertFalse(out["nonce_transaction_consumed"])
                self.false_gates(out)


def add_case(name,fn):
    fn.__name__="test_"+name
    setattr(DurableReplayReferenceTests,fn.__name__,fn)


for index,value in enumerate((True,False,-1,2**32,1.5,"7",None)):
    def case(self,value=value):
        proposal=copy.deepcopy(self.fixture.proposal);proposal["policy_generation"]=value
        out=self.store.issue(proposal=proposal,nonce=NONCE,issued_at=ISSUED,expires_at=EXPIRES)
        self.assertEqual(out["state"],"BLOCKED");self.false_gates(out)
    add_case("invalid_generation_"+str(index),case)

for index,value in enumerate(("",None,"2026-10-08T12:00:00","2026-10-08T12:00:00+99:00","2026-02-30T12:00:00Z",True)):
    def case(self,value=value):
        self.assertEqual(self.issue(issued_at=value)["state"],"BLOCKED")
        self.issue()
        self.assertFalse(self.consume(now=value)["nonce_transaction_consumed"])
    add_case("invalid_time_"+str(index),case)

for index,value in enumerate(("x"*64,"ba"*31,"BA"*32,"x'; DROP TABLE policy; --",None,True)):
    def case(self,value=value):
        proposal=self.fixture.proposal
        out=self.store.issue(proposal=proposal,nonce=value,issued_at=ISSUED,expires_at=EXPIRES)
        self.assertEqual(out["state"],"BLOCKED")
    add_case("nonce_validation_"+str(index),case)

for field in ("policy_sha256","collector_binary_sha256","host","owner","collector"):
    def case(self,field=field):
        request=self.request();self.issue(request)
        if field in ("host","owner","collector"):
            request["proposal"][field]["public_key_sha256"]="sha256:"+"a"*64
        else:request["proposal"][field]="sha256:"+"f"*64
        self.assertFalse(self.consume(request)["nonce_transaction_consumed"])
        self.assertEqual(self.store.inspect()["states"][NONCE],"ISSUED")
    add_case("signed_binding_mutation_"+field,case)

for label in ("owner_forgery","collector_forgery","swapped_signatures","p256_as_owner","domain_change","purpose_change"):
    def case(self,label=label):
        request=self.request();self.issue(request)
        if label=="owner_forgery":request["owner_signature_hex"]="00"*64
        elif label=="collector_forgery":request["collector_signature_hex"]="00"*64
        elif label=="swapped_signatures":
            request["owner_signature_hex"],request["collector_signature_hex"]=request["collector_signature_hex"],request["owner_signature_hex"]
        elif label=="p256_as_owner":request["proposal"]["owner"]["algorithm"]="ECDSA_P256_SHA256"
        elif label=="domain_change":request["proposal"]["owner"]["role"]="HOST_ECDSA_P256"
        else:request["proposal"]["purpose"]="INSTALL_AUTHORIZED"
        out=self.consume(request)
        self.assertFalse(out["nonce_transaction_consumed"]);self.false_gates(out)
    add_case("signature_attack_"+label,case)


if __name__=="__main__":unittest.main()
