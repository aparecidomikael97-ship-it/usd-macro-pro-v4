"""Synthetic Ed25519 dual-domain challenge tests: NO real enrollment/network.

Real signed objects are created with disposable keys IN TEST MEMORY only.
A positive mathematical match MUST NEVER authorize the Global Worker.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from atlasquant_aion_runtime_source_boundary_ref_v1 import (
    SCHEMA as SOURCE_SCHEMA, SOURCE_DOMAIN, canonical_bytes,
)
from atlasquant_aion_checkpoint_dual_challenge_reference_v1 import (
    COORDINATOR_SCHEMA, ANCHOR_SCHEMA, COORDINATOR_DOMAIN, ANCHOR_DOMAIN,
    ReferencePins, review_challenge_bound_dual_head,
)

NOW = datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc)
NONCE = "7f"*32
SHA = "a"*40

def pub(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    )

def timestamp(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")

def signed(record, key, domain):
    row = dict(record)
    row["signature"] = key.sign(canonical_bytes(row, domain=domain)).hex()
    return row

class DualDomainChallengeReferenceTests(unittest.TestCase):
    def setUp(self):
        self.sk_source = Ed25519PrivateKey.generate()
        self.sk_coordinator = Ed25519PrivateKey.generate()
        self.sk_anchor = Ed25519PrivateKey.generate()
        self.pins = ReferencePins(
            owner_id="owner-a",tenant_id="tenant-a",workspace_id="workspace-a",
            repo="owner/repo",branch="atlasquant-runtime",
            path="dados/aion/checkpoint_master.json",
            source_key_id="source-a",source_public_key=pub(self.sk_source),
            coordinator_key_id="coordinator-a",coordinator_public_key=pub(self.sk_coordinator),
            anchor_key_id="anchor-a",anchor_public_key=pub(self.sk_anchor),
            minimum_epoch=3,minimum_sequence=42,
        )
        self.config=SimpleNamespace(
            repo=self.pins.repo,branch=self.pins.branch,path=self.pins.path,
            token="SYNTHETIC_DO_NOT_ECHO",
        )
        shared = {k: getattr(self.pins,k) for k in (
            "owner_id","tenant_id","workspace_id","repo","branch","path",
        )}
        self.source=signed({
            **shared, "schema": SOURCE_SCHEMA,"key_id":"source-a",
            "content_sha":SHA,"sequence":42,
            "issued_at":timestamp(NOW-timedelta(seconds=25)),
            "expires_at":timestamp(NOW+timedelta(minutes=3)),
        },self.sk_source,SOURCE_DOMAIN)
        self.coordinator=signed({
            **shared,"schema":COORDINATOR_SCHEMA,"key_id":"coordinator-a",
            "content_sha":SHA,"epoch":3,"sequence":42,
            "challenge_nonce":NONCE,"observed_at":timestamp(NOW-timedelta(seconds=2)),
        },self.sk_coordinator,COORDINATOR_DOMAIN)
        self.anchor=signed({
            **shared,"schema":ANCHOR_SCHEMA,"key_id":"anchor-a",
            "content_sha":SHA,"epoch":3,"sequence":42,
            "challenge_nonce":NONCE,"observed_at":timestamp(NOW-timedelta(seconds=2)),
        },self.sk_anchor,ANCHOR_DOMAIN)

    def review(self,**kwargs):
        state={
            "config":self.config,"pins":self.pins,"source_proof":self.source,
            "coordinator_head":self.coordinator,"second_domain_head":self.anchor,
            "challenge_nonce":NONCE,"now":NOW,
        }
        state.update(kwargs)
        return review_challenge_bound_dual_head(**state)

    def deny(self,**kwargs):
        x=self.review(**kwargs)
        self.assertEqual(x["status"],"BLOCKED",x)
        self.assertFalse(x["mathematical_match"])
        self.assertFalse(x["worker_authorized"])
        self.assertFalse(x["source_trust_production_verified"])
        self.assertFalse(x["automatic_retry_allowed"])
        self.assertFalse(x["latest_head_independently_verified"])
        self.assertFalse(x["spending_approved"])
        self.assertIsNone(x["checkpoint"])
        self.assertNotIn("SYNTHETIC_DO_NOT_ECHO",str(x))
        return x

    def test_three_ephemeral_signatures_match_but_never_grant_authority(self):
        x=self.review()
        self.assertEqual(x["status"],"REFERENCE_MATCH_UNTRUSTED")
        self.assertTrue(x["mathematical_match"])
        for name in (
            "source_trust_production_verified","coordinator_custody_verified",
            "anchor_custody_verified","freshness_independently_verified",
            "latest_head_independently_verified","rollback_protection_production_verified",
            "worker_authorized","automatic_retry_allowed","spending_approved",
            "deployment_authorized","reader_called",
        ):
            self.assertIs(x[name],False,name)

    def test_missing_evidence_no_keys_no_challenge(self):
        for item in (
            {"pins":None}, {"source_proof":None},
            {"coordinator_head":None},{"second_domain_head":None},
            {"source_proof":{}},{"coordinator_head":{}},{"second_domain_head":{}},
            {"challenge_nonce":""},{"challenge_nonce":"nothex"},
            {"challenge_nonce":"a"*32},
        ):
            with self.subTest(item=str(item)[:55]):
                self.deny(**item)

    def test_challenge_replay_from_prior_request_denied_on_new_nonce(self):
        self.deny(challenge_nonce="1c"*32)
        coordinator=signed({
            **{k:v for k,v in self.coordinator.items() if k!="signature"},
            "challenge_nonce":"1c"*32,
        },self.sk_coordinator,COORDINATOR_DOMAIN)
        self.deny(coordinator_head=coordinator)

    def test_host_reusing_old_nonce_can_match_maths_and_is_not_freshness_proof(self):
        # Critical counterexample: source/heads all valid under the SAME nonce.
        # A hostile host reusing that nonce can replay the signed transcript.
        x=self.review()
        self.assertTrue(x["mathematical_match"])
        self.assertFalse(x["freshness_independently_verified"])
        self.assertFalse(x["worker_authorized"])

    def test_owner_tenant_workspace_resource_cross_domain_forgeries(self):
        for key,new_value in (
            ("owner_id","owner-b"),("tenant_id","tenant-b"),
            ("workspace_id","ws-b"),("repo","attacker/repo"),
            ("branch","main"),("path","other/secret.json"),
        ):
            for field in ("source_proof","coordinator_head","second_domain_head"):
                with self.subTest(key=key,field=field):
                    row=dict(getattr(self, {
                        "source_proof":"source","coordinator_head":"coordinator",
                        "second_domain_head":"anchor",
                    }[field]))
                    row[key]=new_value
                    self.deny(**{field:row})

    def test_valid_signatures_cannot_bridge_different_tenant_source(self):
        poisoned=signed({
            **{k:v for k,v in self.anchor.items() if k!="signature"},
            "tenant_id":"tenant-b",
        },self.sk_anchor,ANCHOR_DOMAIN)
        self.deny(second_domain_head=poisoned)

    def test_forked_sha_sequence_or_epoch_denied(self):
        for key,value in (("content_sha","b"*40),("sequence",43),("epoch",4)):
            with self.subTest(key=key):
                row=signed({
                    **{k:v for k,v in self.coordinator.items() if k!="signature"},
                    key:value,
                },self.sk_coordinator,COORDINATOR_DOMAIN)
                self.deny(coordinator_head=row)
        self.deny(pins=replace(self.pins,minimum_sequence=43))
        self.deny(pins=replace(self.pins,minimum_epoch=4))

    def test_tampered_signatures_or_key_swap_rejected(self):
        for field in ("source_proof","coordinator_head","second_domain_head"):
            row=dict(getattr(self, {
                "source_proof":"source","coordinator_head":"coordinator",
                "second_domain_head":"anchor",
            }[field]))
            row["signature"]="0"*128
            with self.subTest(field=field):
                self.deny(**{field:row})
        self.deny(pins=replace(self.pins,anchor_public_key=pub(self.sk_coordinator)))
        self.deny(pins=replace(self.pins,anchor_key_id="source-a"))

    def test_expired_or_future_head_and_expired_source(self):
        stale=signed({
            **{k:v for k,v in self.anchor.items() if k!="signature"},
            "observed_at":timestamp(NOW-timedelta(seconds=90)),
        },self.sk_anchor,ANCHOR_DOMAIN)
        self.deny(second_domain_head=stale)
        future=signed({
            **{k:v for k,v in self.coordinator.items() if k!="signature"},
            "observed_at":timestamp(NOW+timedelta(seconds=30)),
        },self.sk_coordinator,COORDINATOR_DOMAIN)
        self.deny(coordinator_head=future)
        self.deny(now=NOW+timedelta(minutes=10))
        self.deny(now=NOW.replace(tzinfo=None))

    def test_source_key_schema_and_extra_fields_strict(self):
        x=dict(self.source)
        x["backend_approved"]=True
        self.deny(source_proof=x)
        x=dict(self.anchor)
        x["current"]=True
        self.deny(second_domain_head=x)
        x=dict(self.source)
        x["schema"]="LEGACY"
        self.deny(source_proof=x)
        self.deny(challenge_nonce=NONCE.upper())

    def test_strict_numeric_floor_and_network_outage(self):
        for value in (True,False,0,-1,"42",42.5,None):
            with self.subTest(value=value):
                self.deny(pins=replace(self.pins,minimum_sequence=value))
        for value in (True,False,0,-1,"3",3.1,None):
            with self.subTest(value=value):
                self.deny(pins=replace(self.pins,minimum_epoch=value))
        self.deny(second_domain_head=None)

    def test_untrusted_configuration_cross_path_or_branch_blocked(self):
        for value in (
            {"path":"other.json"},{"branch":"main"},
            {"repo":"another/repo"},
        ):
            with self.subTest(config=value):
                self.deny(config=SimpleNamespace(**{**vars(self.config),**value}))

    def test_distinct_key_id_and_public_key_required(self):
        self.deny(pins=replace(self.pins,anchor_key_id="coordinator-a"))
        self.deny(pins=replace(self.pins,coordinator_public_key=pub(self.sk_anchor)))
        self.deny(pins=replace(self.pins,source_public_key=b""))
        self.deny(pins=replace(self.pins,source_key_id=""))

    def test_false_approval_unaffected_by_github_and_admin_roles(self):
        for level in ("ADMIN","HUMAN_OWNER","TENANT_OWNER"):
            with self.subTest(role=level):
                self.config.role=level
                self.config.authority_verified=True
                x=self.review()
                self.assertTrue(x["mathematical_match"])
                self.assertFalse(x["worker_authorized"])

    def test_not_reachable_from_production_source_gate(self):
        from pathlib import Path
        root=Path(__file__).resolve().parent
        for name in (
            "atlasquant_aion_global_worker.py",
            "atlasquant_aion_global_worker_source_gate_v1.py",
            "atlasquant_aion_global_worker_readiness.py",
        ):
            with self.subTest(path=name):
                content=(root/name).read_text(encoding="utf-8")
                self.assertNotIn("review_challenge_bound_dual_head",content)
        gate=(root/"atlasquant_aion_global_worker_source_gate_v1.py").read_text("utf-8")
        self.assertIn('"source_verified": False',gate)

if __name__=="__main__":
    unittest.main()
