"""Read-only AION Library integrity/recovery preflight. SANDBOX CONTRACT ONLY.

A trusted host provides the external identity adapter, DB factory, verification
keys and archival checkpoint storage. No recovery, indexing, migrations or writes
are performed. Raw DB/catalog and this module must remain server-private.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Callable

from .library_authorization import AttestationVerifier, AuthorizationDenied, _encode
from .library_security_runtime import ExternalIdentityBridge

SCHEMA = 'AION_LIBRARY_RECOVERY_PREFLIGHT_V1'
_ZERO = '0' * 64
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')

_DOC = """SELECT document_id,version,content_sha256,state FROM aion_library_documents
 WHERE entry_id=%s AND tenant_id=%s AND domain_id=%s"""
_AUDIT = """SELECT seq,prev_hash,event_hash,event_type,state_from,state_to,approval_key,recorded_at_unix
 FROM aion_library_atomic_audit WHERE entry_id=%s ORDER BY seq ASC LIMIT 11"""
_BURN = """SELECT binding_sha256,burned_at_unix FROM aion_library_atomic_approval_burns
 WHERE approval_key=%s"""
_READ_ONLY_TX = 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'


def _sha(payload: object) -> str:
    return hashlib.sha256(_encode(payload)).hexdigest()


def _id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _hex(value: object) -> bool:
    return type(value) is str and _HEX.fullmatch(value) is not None


def _deny() -> AuthorizationDenied:
    # Deliberately avoid leaking private document state or DB details.
    return AuthorizationDenied('library integrity preflight denied')


@dataclass(frozen=True)
class IntegrityReport:
    tenant_id: str
    domain_id: str
    entry_id: str
    version: int
    state: str
    content_sha256: str
    event_count: int
    last_event_hash: str
    last_event_seq: int
    integrity_digest: str


@dataclass(frozen=True)
class SignedCheckpoint:
    payload: dict
    mac_sha256: str


class LibraryRecoveryGate:
    """Scoped, authenticated *read-only* integrity inspection and checkpointing.

    IMPORTANT: This is not the application's login endpoint, credential store,
    backup engine, restore procedure or independent proof of archival integrity.
    A trusted operator must archive checkpoints OUTSIDE the mutable database.
    """

    def __init__(self, *, identities: ExternalIdentityBridge,
                 verifier: AttestationVerifier, connect: Callable[[], object],
                 checkpoint_key: bytes, clock: Callable[[], int] | None = None):
        if (type(identities) is not ExternalIdentityBridge or type(verifier) is not AttestationVerifier
                or not callable(connect) or type(checkpoint_key) is not bytes or len(checkpoint_key) < 32):
            raise AuthorizationDenied('trusted recovery gate configuration required')
        # Prevent a checkpoint MAC key being reused as any current proof key.
        if checkpoint_key in (key for group in verifier._keys.values() for key in group.values()):
            raise AuthorizationDenied('checkpoint key must be independently managed')
        self._identities, self._verifier, self._connect = identities, verifier, connect
        self._key = checkpoint_key
        self._clock = clock if clock is not None else lambda: int(time.time())
        if not callable(self._clock):
            raise AuthorizationDenied('trusted clock required')

    def _identity(self, token: str, tenant: str, domain: str, *, admin: bool):
        envelope = self._identities.identity_envelope(token=token, tenant_id=tenant,
                                                      domain_id=domain, action='READ')
        claims = self._verifier.verify('identity', envelope)
        if (claims['tenant_id'], claims['domain_id'], claims['action']) != (tenant,domain,'READ'):
            raise _deny()
        role_set = set(claims['roles'])
        if not role_set.intersection({'LIBRARY_READER', 'LIBRARY_REVIEWER', 'LIBRARY_ADMIN'}):
            raise _deny()
        if admin and 'LIBRARY_ADMIN' not in role_set:
            raise _deny()
        return claims['subject']

    def inspect(self, *, token: str, tenant_id: str, domain_id: str, entry_id: str) -> IntegrityReport:
        if not all(_id(x) for x in (tenant_id, domain_id, entry_id)):
            raise _deny()
        self._identity(token, tenant_id, domain_id, admin=False)
        conn = cursor = None
        try:
            conn = self._connect()
            if conn is None or getattr(conn, 'autocommit', None) is not False:
                raise _deny()
            cursor = conn.cursor()
            # First SQL operation fixes a consistent read-only PostgreSQL snapshot.
            # The host must ALSO grant SELECT-only database credentials.
            cursor.execute(_READ_ONLY_TX)
            cursor.execute(_DOC, (entry_id, tenant_id, domain_id))
            doc = cursor.fetchone()
            if doc is None or len(doc) != 4:
                raise _deny()
            document_id, version, content_sha, state = doc
            if (not _id(document_id) or type(version) is not int or version < 1
                    or not _hex(content_sha) or state not in ('METADATA_REVIEW','APPROVED_FOR_INDEXING')):
                # Revoked/unrecognized documents are not eligible for restore/read.
                raise _deny()
            cursor.execute(_AUDIT, (entry_id,))
            events = cursor.fetchall()
            if not 1 <= len(events) <= 2:
                # Current contract supports exactly genesis then optional approval;
                # refuse long, truncated or unknown audit histories.
                raise _deny()
            last_seq = -1
            previous_hash, previous_state = _ZERO, 'RECEIVED'
            for index, event in enumerate(events):
                if len(event) != 8:
                    raise _deny()
                seq, prev, digest, kind, before, after, approval_key, timestamp = event
                if (type(seq) is not int or seq <= last_seq or not _hex(prev) or
                        not _hex(digest) or not _hex(approval_key) or
                        type(timestamp) is not int or timestamp < 0 or
                        prev != previous_hash or before != previous_state or
                        digest != _sha([prev,kind,before,after,approval_key,timestamp])):
                    raise _deny()
                if index == 0:
                    if (kind,before,after,approval_key) != ('GENESIS','RECEIVED','METADATA_REVIEW',_ZERO):
                        raise _deny()
                elif (kind,before,after) != ('APPROVE_INDEX','METADATA_REVIEW','APPROVED_FOR_INDEXING'):
                    raise _deny()
                previous_hash, previous_state, last_seq = digest, after, seq
            if state != previous_state:
                raise _deny()
            if state == 'APPROVED_FOR_INDEXING':
                if len(events) != 2:
                    raise _deny()
                cursor.execute(_BURN, (events[-1][6],))
                burn = cursor.fetchone()
                if (burn is None or len(burn) != 2 or not _hex(burn[0]) or
                        type(burn[1]) is not int or burn[1] != events[-1][7]):
                    raise _deny()
            elif len(events) != 1:
                raise _deny()
            body = {'tenant_id':tenant_id,'domain_id':domain_id,'entry_id':entry_id,
                    'version':version,'state':state,'content_sha256':content_sha,
                    'event_count':len(events),'last_event_hash':previous_hash,
                    'last_event_seq':last_seq}
            report = IntegrityReport(**body,integrity_digest=_sha(body))
            # Recheck current membership/expiry before returning any result,
            # preventing a caller being revoked during a long database read.
            self._identity(token,tenant_id,domain_id,admin=False)
            conn.rollback()  # end read-only snapshot without DB modifications
            return report
        except AuthorizationDenied:
            if conn is not None:
                try: conn.rollback()
                except Exception: pass
            raise
        except Exception as exc:
            if conn is not None:
                try: conn.rollback()
                except Exception: pass
            raise _deny() from exc
        finally:
            if cursor is not None:
                try: cursor.close()
                except Exception: pass
            if conn is not None:
                try: conn.close()
                except Exception: pass

    def admin_checkpoint(self, *, token: str, tenant_id: str, domain_id: str,
                         entry_id: str) -> SignedCheckpoint:
        # Only authorized admin may mint a new checkpoint; keep and periodically
        # anchor it outside this database under a separately controlled key.
        self._identity(token,tenant_id,domain_id,admin=True)
        report = self.inspect(token=token,tenant_id=tenant_id,domain_id=domain_id,entry_id=entry_id)
        self._identity(token,tenant_id,domain_id,admin=True)
        now = self._clock()
        if type(now) is not int or now < 0:
            raise _deny()
        payload = {'schema':SCHEMA,'issued_at':now,'report':asdict(report)}
        mac = hmac.new(self._key,_encode(payload),hashlib.sha256).hexdigest()
        return SignedCheckpoint(payload,mac)

    def compare_archived_checkpoint(self, *, token: str, tenant_id: str, domain_id: str,
                                     entry_id: str, archived: SignedCheckpoint) -> IntegrityReport:
        # Requires an authenticated admin and independently retained checkpoint.
        self._identity(token,tenant_id,domain_id,admin=True)
        if (type(archived) is not SignedCheckpoint or type(archived.payload) is not dict
                or set(archived.payload) != {'schema','issued_at','report'} or
                archived.payload.get('schema') != SCHEMA or
                type(archived.payload['issued_at']) is not int or
                not isinstance(archived.payload['report'],dict) or
                not _hex(archived.mac_sha256)):
            raise _deny()
        mac = hmac.new(self._key,_encode(archived.payload),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac,archived.mac_sha256):
            raise _deny()
        report = self.inspect(token=token,tenant_id=tenant_id,domain_id=domain_id,entry_id=entry_id)
        self._identity(token,tenant_id,domain_id,admin=True)
        if archived.payload['report'] != asdict(report):
            # Includes scope, document digest, state, latest audit hash and seq.
            # Legitimate later state transitions require a new admin checkpoint.
            raise _deny()
        return report
