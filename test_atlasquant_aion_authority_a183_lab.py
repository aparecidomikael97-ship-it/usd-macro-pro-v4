"""All roles and private keys below are synthetic, on the SAME test host."""
import base64
from copy import deepcopy
from datetime import timedelta
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from aion_chat.external_authority_a183_lab import (
    DOMAIN, REQUIRED, ExternalAuthorityContractLab, root_fingerprint)
from aion_chat.signed_receipt_lab import canonical_bytes
from test_atlasquant_aion_execution_outbox import NOW
from test_atlasquant_aion_signed_receipt_a178_lab import public_bytes

class AuthorityContractTests(unittest.TestCase):
    def setUp(self):
        self.private={role:Ed25519PrivateKey.from_private_bytes(bytes([i])*32)
            for i,role in enumerate(("owner","identity_authority","witness","provider"),41)}
        self.pins={role:{"issuer":"synthetic-"+role,"key_id":"key-"+role,
            "public_key":public_bytes(key),"revoked":False} for role,key in self.private.items()}
        self.root=root_fingerprint(self.pins)
        self.event={"event_id":"synthetic-event","original_sha256":"a"*64,
            "owner_id":"HUMAN_OWNER","tenant_id":"atlasquant-owner","workspace_id":"lab"}
        self.change=lambda b:None

    def verifier(self,**kwargs):
        return ExternalAuthorityContractLab(
            pins=kwargs.pop("pins",self.pins),
            expected_root_sha256=kwargs.pop("expected_root_sha256",self.root),
            authority_epoch=kwargs.pop("authority_epoch",3),
            minimum_sequence=kwargs.pop("minimum_sequence",0),
            now=NOW,**kwargs)

    def query(self,challenge,event,kind):
        body=dict(event,schema="A183_EXTERNAL_EVIDENCE_LAB_V1",kind=kind,status="ATTESTED",
            challenge=challenge,authority_epoch=3,sequence=1,
            root_snapshot_sha256=self.root,issued_at=(NOW-timedelta(seconds=1)).isoformat(),
            expires_at=(NOW+timedelta(seconds=30)).isoformat())
        self.change(body)
        return {"payload":body,"signatures":{
            role:{"issuer":self.pins[role]["issuer"],"key_id":self.pins[role]["key_id"],
                  "signature":base64.b64encode(self.private[role].sign(
                      DOMAIN+canonical_bytes(body))).decode("ascii")}
            for role in REQUIRED[kind]}}

    def test_all_three_contracts_verify_but_never_grant_execution(self):
        for kind in REQUIRED:
            result=self.verifier().admit(kind,self.event,self.query)
            self.assertTrue(result["lab_verified"])
            for flag in ("permits_send","permits_retry","external_homologation"):
                self.assertIs(result[flag],False)

    def test_signed_wrong_binding_epoch_challenge_or_root_denied(self):
        values={"event_id":"other","owner_id":"fake","tenant_id":"other",
            "workspace_id":"other","original_sha256":"b"*64,"authority_epoch":2,
            "challenge":"old","root_snapshot_sha256":"0"*64,"sequence":True,
            "status":"self-asserted"}
        for field,value in values.items():
            with self.subTest(field=field):
                self.change=lambda b,f=field,v=value:b.update({f:v})
                self.assertIsNone(self.verifier().admit("RESERVATION",self.event,self.query))

    def test_signed_stale_and_expired_evidence_denied(self):
        for field,value in (
            ("sequence",0),
            ("expires_at",(NOW-timedelta(seconds=1)).isoformat()),
            ("expires_at",(NOW+timedelta(seconds=100)).isoformat()),
            ("issued_at","2026-01-01T00:00:00")):
            self.change=lambda b,f=field,v=value:b.update({f:v})
            self.assertIsNone(self.verifier().admit("RECEIPT",self.event,self.query))

    def test_revoked_role_and_rotated_root_denied(self):
        pins=deepcopy(self.pins);pins["witness"]["revoked"]=True
        with self.assertRaises(ValueError):self.verifier(pins=pins)
        self.pins=pins;self.root=root_fingerprint(pins)
        self.assertIsNone(self.verifier().admit("RESERVATION",self.event,self.query))

    def test_missing_role_and_forged_signature_denied(self):
        def missing(*args):
            response=self.query(*args);response["signatures"].pop("witness");return response
        self.assertIsNone(self.verifier().admit("RECEIPT",self.event,missing))
        def forged(*args):
            response=self.query(*args)
            response["signatures"]["witness"]["signature"]=base64.b64encode(b"x"*64).decode()
            return response
        self.assertIsNone(self.verifier().admit("RECEIPT",self.event,forged))

    def test_role_key_reuse_denied(self):
        pins=deepcopy(self.pins);pins["witness"]["public_key"]=pins["owner"]["public_key"]
        with self.assertRaises(ValueError):self.verifier(pins=pins,expected_root_sha256=root_fingerprint(pins))

    def test_lost_response_and_boolean_authority_denied(self):
        def lost(*args):raise TimeoutError("synthetic committed reservation, lost ACK")
        for query in (lost,lambda *args:True,lambda *args:None):
            self.assertIsNone(self.verifier().admit("RESERVATION",self.event,query))

    def test_same_instance_replay_denied_and_original_input_is_copied(self):
        verifier=self.verifier()
        self.pins["owner"]["revoked"]=True
        self.assertIsNotNone(verifier.admit("RESERVATION",self.event,self.query))
        self.assertIsNone(verifier.admit("RESERVATION",self.event,self.query))

    def test_minimum_floor_and_missing_original_deny(self):
        self.assertIsNone(self.verifier(minimum_sequence=1).admit("RECEIPT",self.event,self.query))
        for field in self.event:
            body=deepcopy(self.event);del body[field]
            self.assertIsNone(self.verifier().admit("IDENTITY",body,self.query))

    def test_local_rebootstrap_still_revalidates_same_evidence_risk(self):
        self.assertIsNotNone(self.verifier().admit("RESERVATION",self.event,self.query))
        self.assertIsNotNone(self.verifier().admit("RESERVATION",self.event,self.query))
        print("A183_AUTHORITY_CONTRACT_RESET=LOCAL_ROOT_AND_FLOOR_NOT_EXTERNAL")


if __name__=="__main__":unittest.main(verbosity=2)

