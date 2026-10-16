"""A125 synthetic contract for pinned witness and exclusive sender boundaries.

OFFLINE. Same Python process and same administrative trust domain; no real
provider, IAM, WORM, signature, KMS, certificate, or owner enrollment.
DO NOT DEPLOY, connect to a live adapter or infer F1/T1/H0/F2 readiness.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
from threading import RLock
from typing import Any


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(obj: Any) -> str:
    return sha256(canonical(obj)).hexdigest()


class Denied(Exception):
    pass


class Unknown(Exception):
    pass


@dataclass(frozen=True)
class Enrollment:
    owner_id: str
    tenant_id: str
    workspace_id: str
    provider_account: str
    endpoint: str
    witness_id: str
    issuer: str
    key_id: str
    epoch: int

    def validate(self):
        for key, value in vars(self).items():
            if key == 'epoch':
                if type(value) is not int or value < 1:
                    raise Denied('ENROLLMENT_EPOCH_INVALID')
            elif type(value) is not str or not value or value != value.strip() or len(value) > 150:
                raise Denied('ENROLLMENT_FIELD_INVALID')
        if not self.endpoint.startswith('custody://'):
            raise Denied('UNPINNED_ENDPOINT_PROTOCOL')


@dataclass(frozen=True)
class Intent:
    intent_id: str
    owner_id: str
    tenant_id: str
    workspace_id: str
    provider_account: str
    action: str
    payload_digest: str
    recipient_digest: str
    epoch: int

    def validate(self):
        for key, value in vars(self).items():
            if key == 'epoch':
                if type(value) is not int or value < 1:
                    raise Denied('INTENT_EPOCH_INVALID')
            elif type(value) is not str or not value or value != value.strip() or len(value) > 150:
                raise Denied('INTENT_FIELD_INVALID')
        if self.action not in ('FAKE_MESSAGE',):
            raise Denied('ACTION_NOT_ALLOWED_IN_OFFLINE_LAB')
        for attr in ('payload_digest', 'recipient_digest'):
            value = getattr(self,attr)
            if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise Denied('DIGEST_INVALID')

    def identity(self):
        return digest(vars(self))


class MockProvider:
    """Shows that direct provider access is impossible ONLY if the token stays secret.

    Python caller with memory / filesystem / operator privileges can steal
    _provider_token; A125 includes a passing attack demonstration of this.
    """
    def __init__(self, token='FAKE-OPERATOR-CUSTODY-ONLY-DO-NOT-USE'):
        self._provider_token = token
        self.sent: list[str] = []

    def send(self, *, credential: str, intention: str):
        if not hmac.compare_digest(credential, self._provider_token):
            raise Denied('PROVIDER_CREDENTIAL_REQUIRED')
        self.sent.append(intention)
        return {'status': 'FAKE_PROVIDER_ACCEPTED', 'delivery_proven': False}


class MockCustodian:
    """Toy atomic reservation, not third-party CAS or durable independent WORM."""
    def __init__(self, enrollment: Enrollment, *, signature_key: bytes, provider: MockProvider):
        enrollment.validate()
        self.enrollment = enrollment
        self._signature_key = signature_key    # in-process, NOT protected
        self._provider = provider
        self._lock = RLock()                # one process, NOT cross-host
        self._issued: dict[str, dict] = {}
        self._nonces: set[str] = set()
        self._seq = 0
        self.available = True

    def attest_identity(self, challenge: str):
        """Toy nonce-bound identity attestation, not PKI or remote attestation."""
        if not self.available or type(challenge) is not str or len(challenge) < 12:
            raise Unknown('CUSTODIAN_IDENTITY_UNAVAILABLE')
        body={'enrollment':vars(self.enrollment), 'challenge':challenge}
        return {'body':body,'signature':hmac.new(self._signature_key,canonical(body),'sha256').hexdigest()}

    def _receipt(self, intent: Intent, nonce: str):
        return {
            'kind': 'ISSUE_ONCE_RESERVED', 'status': 'UNKNOWN',
            'witness_id': self.enrollment.witness_id,
            'issuer': self.enrollment.issuer,
            'key_id': self.enrollment.key_id,
            'endpoint': self.enrollment.endpoint,
            'epoch': self.enrollment.epoch,
            'intent_binding': intent.identity(),
            'owner_id': intent.owner_id,
            'tenant_id': intent.tenant_id,
            'workspace_id': intent.workspace_id,
            'provider_account': intent.provider_account,
            'nonce': nonce,
            'seq': self._seq,
            'provider_effect_proven': False,
            'no_effect_fenced': False,
        }

    def reserve_and_issue(self, intent: Intent, *, nonce: str, cut: str | None = None):
        if self.available is not True:
            raise Unknown('CUSTODIAN_UNAVAILABLE_NO_RETRY')
        intent.validate()
        with self._lock:
            if intent.intent_id in self._issued:
                previous=self._issued[intent.intent_id]
                if previous['intent_binding'] != intent.identity():
                    raise Denied('LOGICAL_INTENT_REBOUND')
                raise Denied('ALREADY_ISSUED_NO_RETRY')
            if type(nonce) is not str or len(nonce) < 12 or len(nonce)>128 or nonce in self._nonces:
                raise Denied('NONCE_INVALID_OR_REPLAY')
            self._seq += 1
            row=self._receipt(intent,nonce)
            # Simulates durable commit, but mutable same-process dictionary only.
            self._issued[intent.intent_id]=row
            self._nonces.add(nonce)
            signature=hmac.new(self._signature_key,canonical(row),'sha256').hexdigest()
            receipt={'body':row, 'signature':signature}
        if cut == 'after_reservation':
            raise Unknown('RESERVED_BEFORE_FAKE_SEND_NO_RETRY')
        self._provider.send(credential=self._provider._provider_token,intention=intent.identity())
        if cut == 'after_fake_send':
            raise Unknown('FAKE_PROVIDER_OUTCOME_UNKNOWN_NO_RETRY')
        return receipt

    def attack_restore_as_same_admin(self):
        """Known OPEN issue: fake custodian reset through shared admin power."""
        with self._lock:
            self._issued.clear()
            self._nonces.clear()
            self._seq=0


class PinnedClient:
    """Mock verifier pins enrollment + HMAC fixture out of request payload.

    Caller can still replace PinnedClient or steal signer key in this process.
    This tests only *contract invariants*, not authenticated external origin.
    """
    def __init__(self, enrollment: Enrollment, *, verifier_key: bytes):
        enrollment.validate()
        self._enrollment = enrollment
        self._verifier_key = verifier_key  # same-process toy: NOT out-of-band

    def _verify_binding(self,intent: Intent):
        intent.validate()
        e=self._enrollment
        if (intent.owner_id, intent.tenant_id, intent.workspace_id,
            intent.provider_account, intent.epoch) != (e.owner_id,e.tenant_id,e.workspace_id,e.provider_account,e.epoch):
            raise Denied('INDEPENDENT_ENROLLMENT_SCOPE_MISMATCH')

    def _verify_custodian(self, custodian: MockCustodian, challenge: str):
        if type(custodian) is not MockCustodian or custodian.enrollment != self._enrollment:
            raise Denied('WITNESS_ENDPOINT_OR_ISSUER_REPLACED')
        proof=custodian.attest_identity(challenge)
        expected={'enrollment':vars(self._enrollment),'challenge':challenge}
        if proof.get('body') != expected:
            raise Denied('WITNESS_CHALLENGE_BINDING_FAILED')
        correct=hmac.new(self._verifier_key,canonical(expected),'sha256').hexdigest()
        if type(proof.get('signature')) is not str or not hmac.compare_digest(correct,proof['signature']):
            raise Denied('WITNESS_ATTESTATION_INVALID')

    def verify_receipt(self, intent: Intent, nonce: str, receipt: dict):
        self._verify_binding(intent)
        if type(receipt) is not dict or set(receipt) != {'body','signature'}:
            raise Denied('RECEIPT_SHAPE_INVALID')
        b=receipt['body']
        if type(b) is not dict or type(receipt['signature']) is not str:
            raise Denied('RECEIPT_SHAPE_INVALID')
        e=self._enrollment
        expected={
            'kind':'ISSUE_ONCE_RESERVED', 'status':'UNKNOWN',
            'witness_id':e.witness_id,'issuer':e.issuer,'key_id':e.key_id,
            'endpoint':e.endpoint,'epoch':e.epoch,'intent_binding':intent.identity(),
            'owner_id':intent.owner_id,'tenant_id':intent.tenant_id,
            'workspace_id':intent.workspace_id,'provider_account':intent.provider_account,
            'nonce':nonce,'provider_effect_proven':False,'no_effect_fenced':False,
        }
        if set(b) != set(expected)|{'seq'} or type(b.get('seq')) is not int or b['seq']<1:
            raise Denied('RECEIPT_FIELDS_INVALID')
        if any(b.get(k)!=v or type(b.get(k)) is not type(v) for k,v in expected.items()):
            raise Denied('RECEIPT_INTENT_OR_PIN_MISMATCH')
        expected_sig=hmac.new(self._verifier_key,canonical(b),'sha256').hexdigest()
        if not hmac.compare_digest(expected_sig,receipt['signature']):
            raise Denied('RECEIPT_SIGNATURE_INVALID')
        return {'status':'UNKNOWN', 'issue_attempt_consumed':True,
                'provider_effect_proven':False,'no_effect_fenced':False}

    def issue_once(self, intent:Intent,custodian:MockCustodian,*,nonce:str,cut:str|None=None):
        self._verify_binding(intent)
        self._verify_custodian(custodian, nonce)
        receipt=custodian.reserve_and_issue(intent,nonce=nonce,cut=cut)
        return self.verify_receipt(intent,nonce,receipt)


def production_eligible():
    return False
