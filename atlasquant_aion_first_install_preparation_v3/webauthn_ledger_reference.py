"""Durable disposable WebAuthn ledger. NEVER wired to production authentication.

Valid signature -> durable admission -> atomic consume/counter/receipt -> RO
readback. Interrupted admissions remain quarantined, never reclaimed or retried.
"""
from copy import deepcopy
from hashlib import sha256
import json
from atlasquant_aion_first_install_preparation.contracts import (
    digest, digest_value, exact, integer, result, token)
from atlasquant_aion_first_install_preparation.ceremony import prepare_intent
from atlasquant_aion_first_install_preparation_v2.webauthn_reference import (
    PACKET_FIELDS, challenge_for, verify_assertion_reference)
from .ledger_storage import (LedgerStorage, Refusal, append_event, canonical,
                             read_receipt_reference)
from .credential_contracts import credential_contract,current_credential,verification_credential

def attempt_binding(intent,packet):
    """Bounded bytes and full intent. Persist digests, never raw assertion."""
    intent=prepare_intent(intent);exact(packet,PACKET_FIELDS)
    bounded=dict(packet)
    for field,lo,hi in (("client_data_json",1,4096),("authenticator_data",37,37),("signature",8,80)):
        value=packet[field]
        if type(value) is not bytes or not lo<=len(value)<=hi:raise Refusal("ASSERTION_BYTE_BOUND_INVALID")
        bounded[field]=value.hex()
    if not token(packet["credential_id"]):raise Refusal("PACKET_CREDENTIAL_INVALID")
    assertion=digest(bounded)
    return intent,dict(intent_digest=digest(intent),assertion_digest=assertion,
        request_digest=digest({"intent":digest(intent),"assertion":assertion}),challenge=challenge_for(intent))

class ReferenceWebAuthnLedger(LedgerStorage):
    def _committed(self,namespace,operation_id,request_digest,callback):
        if not token(operation_id):return result("BLOCKED","OPERATION_ID_INVALID")
        outcome=self.transaction(callback)
        if outcome["state"]!="REFERENCE_TRANSACTION_COMMITTED_UNTRUSTED":return outcome
        return read_receipt_reference(self.path,scope=self.scope,namespace=namespace,
            operation_id=operation_id,expected_request_digest=request_digest,
            minimum_sequence=outcome["sequence"],timeout=self.timeout)

    def register_credential_reference(self,bind,credential,*,operation_id):
        try:row=credential_contract(self.scope,bind,credential)
        except (ValueError,TypeError,KeyError):return result("BLOCKED","CREDENTIAL_INPUT_REJECTED")
        request_digest=digest({"binding":bind,"credential":row})
        def register(db):
            if row["generation"]!=1 or db.execute("SELECT 1 FROM credentials WHERE credential_id=?",(row["credential_id"],)).fetchone():
                raise Refusal("NO_REGISTRATION_OVERWRITE")
            self._insert_credential(db,row)
            seq=append_event(db,"REGISTER",operation_id,request_digest)
            return result("REFERENCE_TRANSACTION_COMMITTED_UNTRUSTED","DISPOSABLE_REGISTRY_ONLY",sequence=seq)
        return self._committed("REGISTER",operation_id,request_digest,register)

    @staticmethod
    def _insert_credential(db,row):
        keys=("credential_id","generation","device_id","key_hex","key_sha256","backup_eligible","sign_count","backup_state","expires_at","state")
        db.execute("INSERT INTO credentials VALUES (?,?,?,?,?,?,?,?,?,?)",tuple(row[k] for k in keys))

    def rotate_credential_reference(self,bind,credential,*,operation_id,expected_generation,
                                    expected_key_sha256,decision):
        try:
            row=credential_contract(self.scope,bind,credential)
            if (decision!="SIMULATE_ROTATION_ONLY" or not integer(expected_generation,1,2**31-1)
                    or not digest_value(expected_key_sha256) or row["generation"]!=expected_generation+1):
                raise Refusal("ROTATION_CONTRACT_INVALID")
        except (ValueError,TypeError,KeyError):return result("BLOCKED","ROTATION_INPUT_REJECTED")
        request_digest=digest({"binding":bind,"credential":row,"expected_generation":expected_generation,
                               "expected_key_sha256":expected_key_sha256,"decision":decision})
        def rotate(db):
            old=current_credential(db,row["credential_id"])
            if (old["generation"]!=expected_generation or old["key_sha256"]!=expected_key_sha256
                    or old["device_id"]!=row["device_id"] or old["key_sha256"]==row["key_sha256"]):
                raise Refusal("ROTATION_COMPARE_AND_SWAP_FAILED")
            if old["state"]=="ACTIVE":
                db.execute("UPDATE credentials SET state='RETIRED' WHERE credential_id=? AND generation=?",(old["credential_id"],old["generation"]))
            # REVOKED stays REVOKED forever. Only explicit new generation allowed.
            self._insert_credential(db,row)
            seq=append_event(db,"ROTATE",operation_id,request_digest)
            return result("REFERENCE_TRANSACTION_COMMITTED_UNTRUSTED","ROTATION_NOT_REAL_ENROLLMENT",sequence=seq)
        return self._committed("ROTATE",operation_id,request_digest,rotate)

    def revoke_credential_reference(self,credential_id,*,generation,expected_key_sha256,operation_id):
        if not token(credential_id) or not integer(generation,1) or not digest_value(expected_key_sha256):
            return result("BLOCKED","REVOCATION_INPUT_INVALID")
        request_digest=digest({"credential_id":credential_id,"generation":generation,"key_sha256":expected_key_sha256})
        def revoke(db):
            old=current_credential(db,credential_id)
            if old["generation"]!=generation or old["key_sha256"]!=expected_key_sha256 or old["state"]!="ACTIVE":
                raise Refusal("REVOCATION_COMPARE_AND_SWAP_FAILED")
            db.execute("UPDATE credentials SET state='REVOKED' WHERE credential_id=? AND generation=?",(credential_id,generation))
            seq=append_event(db,"REVOKE",operation_id,request_digest)
            return result("REFERENCE_TRANSACTION_COMMITTED_UNTRUSTED","REVOCATION_IRREVERSIBLE_FOR_GENERATION",sequence=seq)
        return self._committed("REVOKE",operation_id,request_digest,revoke)

    def issue_challenge_reference(self,intent,*,generation,rp_id,origin,operation_id,now):
        try:
            intent=prepare_intent(intent)
            if (any(intent["binding"][k]!=self.scope[k] for k in self.scope)
                    or not integer(generation,1) or not integer(now)
                    or not intent["not_before"]<=now<intent["expires_at"]
                    or rp_id!="offline-fixture.invalid" or origin!="https://offline-fixture.invalid"):
                raise Refusal("ISSUE_SCOPE_OR_TIME_INVALID")
        except (ValueError,TypeError,KeyError):return result("BLOCKED","CHALLENGE_INPUT_INVALID")
        intent=deepcopy(intent);challenge=challenge_for(intent)
        request_digest=digest({"intent":intent,"generation":generation,"rp_id":rp_id,"origin":origin})
        def issue(db):
            row=current_credential(db,intent["binding"]["credential_id"])
            verification_credential(row,intent["binding"])
            if row["generation"]!=generation or row["expires_at"]<intent["expires_at"]:
                raise Refusal("CREDENTIAL_GENERATION_OR_VALIDITY_MISMATCH")
            if db.execute("SELECT 1 FROM challenges WHERE challenge=? OR request_id=? OR nonce_hex=?",(challenge,intent["request_id"],intent["nonce"])).fetchone():
                raise Refusal("CHALLENGE_ALREADY_ISSUED_NO_REACTIVATION")
            db.execute("INSERT INTO challenges VALUES (?,?,?,?,?,?,?,?,?,?,?,'ISSUED',NULL)",
                (challenge,intent["request_id"],intent["nonce"],canonical(intent),digest(intent),row["credential_id"],generation,rp_id,origin,now,intent["expires_at"]))
            seq=append_event(db,"ISSUE",operation_id,request_digest)
            return result("REFERENCE_TRANSACTION_COMMITTED_UNTRUSTED","CHALLENGE_NOT_CONSENT",sequence=seq)
        return self._committed("ISSUE",operation_id,request_digest,issue)

    def _verify(self,db,intent,packet,challenge,now):
        row=current_credential(db,challenge["credential_id"])
        if row["generation"]!=challenge["generation"]:raise Refusal("CREDENTIAL_CHANGED_DURING_ATTEMPT")
        credential=verification_credential(row,intent["binding"])
        outcome=verify_assertion_reference(intent,packet,credential,expected_binding=intent["binding"],
            expected_public_key_sha256=row["key_sha256"],expected_generation=challenge["generation"],
            rp_id=challenge["rp_id"],origin=challenge["origin"],now=now,
            revoked_credentials=[],consumed_challenges=[])
        if outcome["state"]!="REFERENCE_ASSERTION_CRYPTO_VALID_UNTRUSTED":
            raise Refusal("CRYPTO_OR_COUNTER_REJECTED")
        return row,outcome["reference_sign_count"]

    def confirm_assertion_reference(self,intent,packet,*,attempt_id,now):
        try:
            intent,bound=attempt_binding(intent,packet)
            if (not token(attempt_id) or not integer(now)
                    or any(intent["binding"][k]!=self.scope[k] for k in self.scope)):
                raise Refusal("ATTEMPT_SCOPE_INVALID")
            intent=deepcopy(intent);packet=deepcopy(packet)
        except (ValueError,TypeError,KeyError):return result("BLOCKED","ATTEMPT_INPUT_INVALID")
        def admit(db):
            if db.execute("SELECT 1 FROM attempts WHERE attempt_id=?",(attempt_id,)).fetchone():
                raise Refusal("ATTEMPT_ID_USED_READBACK_ONLY")
            challenge=db.execute("SELECT * FROM challenges WHERE challenge=?",(bound["challenge"],)).fetchone()
            if (challenge is None or challenge["state"]!="ISSUED"
                    or challenge["intent_digest"]!=bound["intent_digest"]
                    or challenge["intent_json"]!=canonical(intent)):
                raise Refusal("CHALLENGE_NOT_AVAILABLE")
            self._verify(db,intent,packet,challenge,now)
            db.execute("INSERT INTO attempts VALUES (?,?,?,?,?,'PENDING',NULL)",
                (attempt_id,bound["challenge"],bound["intent_digest"],bound["assertion_digest"],bound["request_digest"]))
            db.execute("UPDATE challenges SET state='ATTEMPT_PENDING',attempt_id=? WHERE challenge=?",(attempt_id,bound["challenge"]))
            seq=append_event(db,"ADMISSION",attempt_id,bound["request_digest"])
            return result("REFERENCE_TRANSACTION_COMMITTED_UNTRUSTED","VALID_FIXTURE_DURABLY_QUARANTINED",sequence=seq)
        admission=self._committed("ADMISSION",attempt_id,bound["request_digest"],admit)
        if admission["state"]!="REFERENCE_DURABLE_RECEIPT_UNTRUSTED":return admission
        def consume(db):
            challenge=db.execute("SELECT * FROM challenges WHERE challenge=?",(bound["challenge"],)).fetchone()
            attempt=db.execute("SELECT * FROM attempts WHERE attempt_id=?",(attempt_id,)).fetchone()
            if (challenge is None or attempt is None or challenge["state"]!="ATTEMPT_PENDING"
                    or challenge["attempt_id"]!=attempt_id or attempt["state"]!="PENDING"
                    or attempt["request_digest"]!=bound["request_digest"]):
                raise Refusal("PENDING_CAUSAL_BINDING_LOST")
            try:row,count=self._verify(db,intent,packet,challenge,now)
            except Refusal:
                db.execute("UPDATE attempts SET state='QUARANTINED' WHERE attempt_id=?",(attempt_id,))
                db.execute("UPDATE challenges SET state='QUARANTINED' WHERE challenge=?",(bound["challenge"],))
                append_event(db,"QUARANTINE",attempt_id,bound["request_digest"])
                return result("BLOCKED","CREDENTIAL_OR_COUNTER_CHANGED_NO_RETRY")
            db.execute("UPDATE credentials SET sign_count=?,backup_state=? WHERE credential_id=? AND generation=?",
                (count,int(bool(packet["authenticator_data"][32]&16)),row["credential_id"],row["generation"]))
            db.execute("UPDATE challenges SET state='CONSUMED' WHERE challenge=?",(bound["challenge"],))
            db.execute("UPDATE attempts SET state='CONSUMED',consumed_counter=? WHERE attempt_id=?",(count,attempt_id))
            seq=append_event(db,"CONSUMPTION",attempt_id,bound["request_digest"])
            return result("REFERENCE_TRANSACTION_COMMITTED_UNTRUSTED","CONSUMPTION_NOT_OPERATIONAL_AUTHORITY",sequence=seq)
        return self._committed("CONSUMPTION",attempt_id,bound["request_digest"],consume)

    def reconcile_attempt_reference(self,*,attempt_id,expected_request_digest,minimum_sequence):
        return read_receipt_reference(self.path,scope=self.scope,namespace="CONSUMPTION",operation_id=attempt_id,
            expected_request_digest=expected_request_digest,minimum_sequence=minimum_sequence,timeout=self.timeout)
