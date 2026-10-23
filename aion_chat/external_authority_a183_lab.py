"""A183 strict wire contract for synthetic independent-authority evidence.

Pinned inputs remain caller-controlled LAB fixtures. Successful verification
NEVER grants send/retry, real identity, external custody or P0 homologation.
"""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import secrets
from threading import Lock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aion_chat.signed_receipt_lab import canonical_bytes

DOMAIN=b"ATLASQUANT:A183:EXTERNAL_CONTRACT_LAB_V1\0"
ROLES=frozenset({"owner","identity_authority","witness","provider"})
REQUIRED={
    "IDENTITY":frozenset({"owner","identity_authority"}),
    "RESERVATION":frozenset({"owner","witness"}),
    "RECEIPT":frozenset({"provider","witness"}),
}
EVENT=frozenset({"event_id","original_sha256","owner_id","tenant_id","workspace_id"})
FIELDS=EVENT | {"schema","kind","challenge","authority_epoch","sequence",
                "issued_at","expires_at","root_snapshot_sha256","status"}


def root_fingerprint(pins):
    return sha256(canonical_bytes({
        role:{"issuer":value["issuer"],"key_id":value["key_id"],
              "public_key":value["public_key"].hex(),"revoked":value["revoked"]}
        for role,value in pins.items()})).hexdigest()


class ExternalAuthorityContractLab:
    def __init__(self, *, pins, expected_root_sha256, authority_epoch,
                 minimum_sequence, now):
        # Validate the same retained configuration that verification will use.
        pins=deepcopy(pins)
        if type(pins) is not dict or set(pins)!=ROLES:
            raise ValueError("EXACT_AUTHORITY_ROLES_REQUIRED")
        for entry in pins.values():
            if (type(entry) is not dict or set(entry)!={"issuer","key_id","public_key","revoked"}
                    or type(entry["public_key"]) is not bytes or len(entry["public_key"])!=32
                    or type(entry["revoked"]) is not bool
                    or any(type(entry[k]) is not str or not entry[k] for k in ("issuer","key_id"))):
                raise ValueError("INVALID_AUTHORITY_PIN")
        if len({e["public_key"] for e in pins.values()})!=len(ROLES):
            raise ValueError("DISTINCT_ROLE_KEYS_REQUIRED_NOT_INDEPENDENCE_PROOF")
        if root_fingerprint(pins)!=expected_root_sha256:
            raise ValueError("ROOT_SNAPSHOT_CHANGED")
        if type(authority_epoch) is not int or authority_epoch<1:
            raise ValueError("EXPLICIT_AUTHORITY_EPOCH_REQUIRED")
        if type(minimum_sequence) is not int or minimum_sequence<0:
            raise ValueError("RETAINED_MONOTONIC_FLOOR_REQUIRED")
        if not isinstance(now,datetime) or now.tzinfo is None:
            raise ValueError("AWARE_FIXTURE_TIME_REQUIRED")
        self._pins=deepcopy(pins)
        self._root=expected_root_sha256
        self._epoch=authority_epoch
        self._high=minimum_sequence
        self._now=now.astimezone(timezone.utc)
        self._seen=set()
        self._lock=Lock()

    def admit(self, kind, event, query):
        with self._lock:
            try:
                # No callback may replace the expected original via a retained
                # reference. These local copies do not authenticate its origin.
                event=deepcopy(event)
                if kind not in REQUIRED or type(event) is not dict or set(event)!=EVENT:
                    return None
                if any(type(v) is not str or not v for v in event.values()):
                    return None
                if len(event["original_sha256"])!=64 or any(
                        c not in "0123456789abcdef" for c in event["original_sha256"]):
                    return None
                identity=(kind,canonical_bytes(event))
                if identity in self._seen:
                    return None
                challenge=secrets.token_hex(32)
                # Capture once: every role must verify one identical message,
                # even if the response producer retains and edits its objects.
                response=deepcopy(query(challenge,deepcopy(event),kind))
                if type(response) is not dict or set(response)!={"payload","signatures"}:
                    return None
                body=response["payload"]
                if type(body) is not dict or set(body)!=FIELDS:
                    return None
                if (body["schema"]!="A183_EXTERNAL_EVIDENCE_LAB_V1"
                        or body["kind"]!=kind or body["status"]!="ATTESTED"
                        or body["challenge"]!=challenge
                        or body["root_snapshot_sha256"]!=self._root
                        or type(body["authority_epoch"]) is not int
                        or body["authority_epoch"]!=self._epoch
                        or any(body[k]!=v for k,v in event.items())):
                    return None
                seq=body["sequence"]
                if type(seq) is not int or seq<=self._high:
                    return None
                issued=datetime.fromisoformat(body["issued_at"])
                expires=datetime.fromisoformat(body["expires_at"])
                if (issued.tzinfo is None or expires.tzinfo is None
                        or not issued<=self._now<=expires
                        or not 0<(expires-issued).total_seconds()<=60):
                    return None
                signatures=response["signatures"]
                if type(signatures) is not dict or set(signatures)!=REQUIRED[kind]:
                    return None
                signed_message=DOMAIN+canonical_bytes(body)
                for role in REQUIRED[kind]:
                    pin=self._pins[role]
                    envelope=signatures[role]
                    if (pin["revoked"] or type(envelope) is not dict
                            or set(envelope)!={"issuer","key_id","signature"}
                            or envelope["issuer"]!=pin["issuer"] or envelope["key_id"]!=pin["key_id"]
                            or type(envelope["signature"]) is not str
                            or len(envelope["signature"])>128):
                        return None
                    signature=base64.b64decode(envelope["signature"],validate=True)
                    Ed25519PublicKey.from_public_bytes(pin["public_key"]).verify(
                        signature,signed_message)
                self._high=seq;self._seen.add(identity)
                return {"lab_verified":True,"kind":kind,
                        "permits_send":False,"permits_retry":False,
                        "external_homologation":False}
            except Exception:
                # A callback is not an authority and arbitrary callback failure
                # cannot turn missing evidence into permission.
                return None

