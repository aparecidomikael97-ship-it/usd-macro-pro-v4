"""A124 offline *surviving witness* design fixture. NOT external custody.

This process-local witness is a separate *logical* failure domain from A123's
TWO local SQLite databases. It demonstrates what a trusted surviving ledger
must deny after a joint local restore. Its mutable memory, fake HMAC authority,
and caller-provided enrollment cannot prove administrative independence.

NO network, no external provider, no SMS, no production use, no real H0/F1/T1/F2.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import hmac
import threading

from contract import Intent, Denied, Uncertain, canonical, digest, AdmissionFixture, FakeSender


class SimulatedSurvivingWitness:
    """Pinned fixture in the test process, *not* a durable third-party witness.

    This object must NOT be snapshotted/restored alongside the two SQLite files
    for a successful rejection test. Its existence models, rather than proves,
    a separate custody trust root.
    """

    def __init__(self, *, secret=b'A124-FAKE-WITNESS-SECRET', issuer='A124-FIXTURE-ISSUER', online=True, enrolled=True):
        self._secret = secret            # NOT hardware protected; same-process mock
        self.issuer = issuer
        self.online = online
        self.enrolled = enrolled        # Caller supplied MOCK enrollment
        self.signer_ready = True
        self._lock = threading.RLock()  # single-process, NOT distributed consensus
        self._issued: dict[str, dict] = {}
        self._head = 'GENESIS'
        self._seq = 0
        self._history: list[dict] = []

    @staticmethod
    def _identity(intent: Intent):
        if not isinstance(intent, Intent):
            raise Denied('INTENT_TYPE_INVALID')
        return intent.intent_id

    def _gate(self):
        if self.online is not True or self.enrolled is not True or self.signer_ready is not True:
            raise Denied('TRUSTED_WITNESS_NOT_AVAILABLE_OR_UNENROLLED')

    def _sign(self, body: dict) -> str:
        return hmac.new(self._secret, canonical(body).encode(), hashlib.sha256).hexdigest()

    def _verify_history(self):
        prev = 'GENESIS'
        seen = set()
        for idx, receipt in enumerate(self._history, 1):
            if type(receipt) is not dict or set(receipt) != {'body', 'signature'}:
                raise Denied('WITNESS_HISTORY_SHAPE_CHANGED')
            body = receipt['body']
            if type(body) is not dict or set(body) != {'seq', 'issuer', 'kind', 'intent_id', 'binding', 'prior', 'nonce'}:
                raise Denied('WITNESS_RECEIPT_SHAPE_CHANGED')
            if body['seq'] != idx or body['prior'] != prev or body['issuer'] != self.issuer or body['kind'] != 'ISSUE_ONCE':
                raise Denied('WITNESS_CHAIN_INVALID')
            if body['intent_id'] in seen:
                raise Denied('WITNESS_DUPLICATE_IDENTITY')
            seen.add(body['intent_id'])
            if not hmac.compare_digest(self._sign(body), receipt['signature']):
                raise Denied('WITNESS_SIGNATURE_MISMATCH')
            prev = digest(receipt)
            registered = self._issued.get(body['intent_id'])
            if registered != receipt:
                raise Denied('WITNESS_INDEX_TAMPERED')
        if self._seq != len(self._history) or self._head != prev or len(self._issued) != len(self._history):
            raise Denied('WITNESS_ROLLBACK_OR_TRUNCATION')

    def inspect(self, intent: Intent):
        """Read-only check without authority to treat absence as NO_EFFECT_FENCED."""
        self._gate()
        identity = self._identity(intent)
        with self._lock:
            self._verify_history()
            old = self._issued.get(identity)
            if old is None:
                return {'status': 'NO_LOCAL_WITNESS_ISSUE_OBSERVED', 'no_effect_proven': False}
            if old['body']['binding'] != intent.binding:
                raise Denied('LOGICAL_INTENT_SCOPE_CONFLICT')
            return {'status': 'ISSUE_ONCE_ALREADY_RESERVED', 'no_effect_proven': False}

    def reserve_once(self, intent: Intent, *, nonce: str):
        """Commit witness mark BEFORE entering A123's issue_once()."""
        self._gate()
        identity = self._identity(intent)
        if not isinstance(nonce, str) or len(nonce) < 12 or len(nonce) > 128:
            raise Denied('WITNESS_NONCE_INVALID')
        with self._lock:
            self._verify_history()
            old = self._issued.get(identity)
            if old is not None:
                if old['body']['binding'] != intent.binding:
                    raise Denied('LOGICAL_INTENT_SCOPE_CONFLICT')
                raise Denied('ISSUE_ONCE_ALREADY_RESERVED_NO_RETRY')
            if any(r['body']['nonce'] == nonce for r in self._history):
                raise Denied('WITNESS_NONCE_REUSED')
            body = {
                'seq': self._seq + 1,
                'issuer': self.issuer,
                'kind': 'ISSUE_ONCE',
                'intent_id': identity,
                'binding': intent.binding,
                'prior': self._head,
                'nonce': nonce,
            }
            receipt = {'body': body, 'signature': self._sign(body)}
            self._history.append(receipt)
            self._issued[identity] = receipt
            self._seq += 1
            self._head = digest(receipt)
            return deepcopy(receipt)

    def verify_receipt(self, intent: Intent, receipt: dict):
        self._gate()
        with self._lock:
            self._verify_history()
            expected = self._issued.get(self._identity(intent))
            if expected is None or receipt != expected or expected['body']['binding'] != intent.binding:
                raise Denied('WITNESS_RECEIPT_UNTRUSTED_OR_STALE')
            return {'status':'TOY_WITNESS_ADMISSION_ATTESTED',
                    'provider_effect_proven':False,
                    'no_effect_fenced_post_handoff':False}

    def snapshot(self):
        """Test-only mutable state snapshot: illustrates why this is NOT external custody."""
        with self._lock:
            return deepcopy((self._issued, self._head, self._seq, self._history))

    def restore_as_same_admin_for_attack(self, snapshot):
        """An attack that the true AION administrator MUST NOT be able to do."""
        with self._lock:
            self._issued, self._head, self._seq, self._history = deepcopy(snapshot)

    def summary(self):
        self._gate()
        with self._lock:
            self._verify_history()
            return {'seq':self._seq,'head':self._head, 'provider_effect_proven':False}


class GuardedAdmissionFixture:
    """Only a synthetically enforced entrypoint, not enforceable in A123/prod.

    The A123 bare AdmissionFixture and FakeSender remain bypassable within the
    same process. No independent operator credentials exist in this fixture.
    """

    def __init__(self, a123: AdmissionFixture, witness: SimulatedSurvivingWitness):
        if type(a123) is not AdmissionFixture or type(witness) is not SimulatedSurvivingWitness:
            raise Denied('ONLY_OFFLINE_FIXTURES_ALLOWED')
        self.a123 = a123
        self.witness = witness

    def prepare(self, intent: Intent, *, nonce='A124-PREPARE-UNIQUE-01'):
        result = self.witness.inspect(intent)
        if result['status'] != 'NO_LOCAL_WITNESS_ISSUE_OBSERVED':
            raise Denied('EXTERNAL_WITNESS_ALREADY_RESERVED')
        return self.a123.prepare(intent,nonce=nonce)

    def issue_once(self, intent: Intent, *, nonce='A124-ISSUE-WITNESS-01', cut=None):
        # The witness itself never claims provider delivery or NO_EFFECT.
        # A reservation crash leaves a consumed reservation, no retry.
        receipt = self.witness.reserve_once(intent,nonce=nonce)
        if cut == 'after_witness_before_a123':
            raise Uncertain('WITNESS_RESERVED_LOCAL_ISSUE_UNCERTAIN')
        self.witness.verify_receipt(intent,receipt)
        try:
            outcome = self.a123.issue_once(intent,nonce='A123-ISSUE-'+nonce)
        except (Denied,Uncertain):
            # If the A123 ledger refused or failed, the witness reservation
            # stays consumed. Not a 2PC; availability sacrificed for safety.
            raise
        return {'status':'UNKNOWN','witness_receipt':receipt,
                'fixture_outcome':outcome['status'],
                'provider_effect_proven':False,
                'no_effect_fenced_post_handoff':False}

    def pre_fence(self, intent: Intent):
        # No issuance permit when witness already consumed. Does NOT authorize
        # provider-side no-effect after any handoff.
        result=self.witness.inspect(intent)
        if result['status']!='NO_LOCAL_WITNESS_ISSUE_OBSERVED':
            raise Denied('CANNOT_FENCE_AFTER_WITNESS_ISSUE')
        return self.a123.pre_fence(intent)


def production_eligible():
    return False
