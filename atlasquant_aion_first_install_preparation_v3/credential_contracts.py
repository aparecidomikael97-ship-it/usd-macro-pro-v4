"""Closed disposable credential contracts; simulated rotation is not enrollment."""
from hashlib import sha256
from cryptography.hazmat.primitives.asymmetric import ec
from atlasquant_aion_first_install_preparation.contracts import (
    binding, digest, exact, integer, token)
from atlasquant_aion_first_install_preparation_v2.webauthn_reference import CREDENTIAL_FIELDS, _key
from .ledger_storage import Refusal

def credential_contract(scope,bind,credential):
    bind=binding(bind);exact(credential,CREDENTIAL_FIELDS)
    if any(bind[k]!=scope[k] for k in scope):raise Refusal("CREDENTIAL_SCOPE_MISMATCH")
    if (not all(bind[k].startswith("fixture-") for k in ("device_id","credential_id"))
            or credential["schema"]!="AION_WEBAUTHN_DISPOSABLE_CREDENTIAL_V2"
            or credential["role"]!="OWNER_CEREMONY_FIXTURE"
            or credential["scope_digest"]!=digest(bind)
            or credential["credential_id"]!=bind["credential_id"]
            or not integer(credential["generation"],1,2**31-1)
            or type(credential["backup_eligible"]) is not bool
            or not integer(credential["stored_sign_count"],0,2**32-1)
            or not integer(credential["expires_at"],1)):
        raise Refusal("DISPOSABLE_CREDENTIAL_CONTRACT_INVALID")
    key=_key(credential["public_key_cose"])
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),b'\x04'+key[-2]+key[-3])
    return dict(credential_id=bind["credential_id"],generation=credential["generation"],
        device_id=bind["device_id"],key_hex=credential["public_key_cose"].hex(),
        key_sha256=sha256(credential["public_key_cose"]).hexdigest(),
        backup_eligible=int(credential["backup_eligible"]),sign_count=credential["stored_sign_count"],
        backup_state=None,expires_at=credential["expires_at"],state="ACTIVE")

def current_credential(db,credential_id):
    if not token(credential_id):raise Refusal("CREDENTIAL_ID_INVALID")
    row=db.execute("SELECT * FROM credentials WHERE credential_id=? ORDER BY generation DESC LIMIT 1",(credential_id,)).fetchone()
    if row is None:raise Refusal("CREDENTIAL_UNKNOWN")
    return dict(row)

def verification_credential(row,bind):
    # Identity is registry-scoped; operation scope is pinned by the issued intent.
    # This projection does NOT enroll a physical authenticator or a real owner.
    if row["state"]!="ACTIVE" or row["device_id"]!=bind["device_id"]:
        raise Refusal("CREDENTIAL_REVOKED_RETIRED_OR_WRONG_DEVICE")
    return dict(schema="AION_WEBAUTHN_DISPOSABLE_CREDENTIAL_V2",role="OWNER_CEREMONY_FIXTURE",
        scope_digest=digest(bind),credential_id=row["credential_id"],public_key_cose=bytes.fromhex(row["key_hex"]),
        generation=row["generation"],backup_eligible=bool(row["backup_eligible"]),
        stored_sign_count=row["sign_count"],expires_at=row["expires_at"])
