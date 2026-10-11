"""Fixture-only dual-signature transition review. NEVER root enrollment.

A verified old/new pair is mathematical evidence only. The root pins,
clock, witnesses, custody, governance, and owner approval are caller-owned
synthetic inputs; no state mutation or promotion to production is possible.
"""
from __future__ import annotations
from hashlib import sha256
from typing import Any
from cryptography.exceptions import InvalidSignature
from atlasquant_aion_runtime_source_boundary_ref_v1 import _verify_sig
from atlasquant_aion_first_install_preparation.contracts import exact,integer,token,digest_value
from atlasquant_aion_first_install_preparation_v4.signed_anchors import pin_contract,pin_digest
from atlasquant_aion_first_install_preparation_v4.outcomes import result

OLD_DOMAIN=b"AION_V5_FIXTURE_TRANSITION_OLD\0"
NEW_DOMAIN=b"AION_V5_FIXTURE_TRANSITION_NEW\0"
FIELDS={"schema","mode","scope","old_epoch","new_epoch","old_pin_digest",
        "new_pin_digest","old_head_digest","new_genesis_digest",
        "authorization_claim","operation_id","reason","old_signature","new_signature"}

def review_fixture_transition(transition:Any,*,old_pin:Any,new_pin:Any,
                              expected_old_pin_digest:Any,expected_new_pin_digest:Any,
                              revoked_keys:Any,revoked_operators:Any)->dict:
    try:
        exact(transition,FIELDS)
        old=pin_contract(old_pin);new=pin_contract(new_pin)
        if (transition["schema"]!="AION_V5_ROOT_EPOCH_TRANSITION_FIXTURE"
            or transition["mode"]!="SYNTHETIC_ONLY"
            or transition["authorization_claim"]!="FIXTURE_UNVERIFIED_OWNER_APPROVAL"
            or type(transition["reason"]) is not str or transition["reason"] not in
                 ("SIMULATED_PLANNED_ROTATION","SIMULATED_RECOVERY")
            or not token(transition["operation_id"])
            or not isinstance(revoked_keys,list) or not isinstance(revoked_operators,list)
            or not all(token(v) for v in revoked_keys+revoked_operators)
            or len(revoked_keys)>128 or len(revoked_operators)>128):
            raise ValueError("UNTRUSTED_TRANSITION_INPUT")
        if (old["key_id"] in revoked_keys or new["key_id"] in revoked_keys or
            old["operator_alias"] in revoked_operators or new["operator_alias"] in revoked_operators):
            raise ValueError("REVOKED_TRANSITION_KEY")
        if (transition["old_pin_digest"]!=expected_old_pin_digest or
            transition["new_pin_digest"]!=expected_new_pin_digest or
            pin_digest(old)!=expected_old_pin_digest or pin_digest(new)!=expected_new_pin_digest):
            raise ValueError("EXPECTED_ROOT_PIN_MISMATCH")
        if (not integer(transition["old_epoch"],1,2**31-2)
            or type(transition["new_epoch"]) is not int
            or transition["new_epoch"] != transition["old_epoch"]+1
            or new["key_generation"]!=old["key_generation"]+1
            or old["public_key_hex"]==new["public_key_hex"]
            or old["key_id"]==new["key_id"]
            or old["operator_alias"]==new["operator_alias"]
            or old["expires_at"]<=0 or new["expires_at"]<=0):
            raise ValueError("EPOCH_KEY_DOWNGRADE_OR_NO_ROTATION")
        for key in ("owner_id","tenant_id","workspace_id","ledger_id","witness_id",
                    "policy_id","policy_version"):
            if old[key]!=new[key]:raise ValueError("SCOPE_CHANGED")
        scope={key:old[key] for key in ("owner_id","tenant_id","workspace_id","ledger_id","witness_id")}
        if transition["scope"]!=scope:raise ValueError("CLAIM_SCOPE_CHANGED")
        if not all(digest_value(transition[key]) for key in
                   ("old_head_digest","new_genesis_digest")):
            raise ValueError("TRANSITION_COMMITMENT_INVALID")
        # Verify both signatures over the SAME canonical transition data but
        # under distinct domain separators and key generations.
        body={k:v for k,v in transition.items() if k not in ("old_signature","new_signature")}
        _verify_sig({**body,"signature":transition["old_signature"]},
                    bytes.fromhex(old["public_key_hex"]),OLD_DOMAIN)
        _verify_sig({**body,"signature":transition["new_signature"]},
                    bytes.fromhex(new["public_key_hex"]),NEW_DOMAIN)
        return result("REFERENCE_DUAL_SIGNATURE_MATH_UNTRUSTED",
                      "NO_INDEPENDENT_OWNER_OR_ROOT_ENROLLMENT",
                      mathematical_signatures_valid=True,
                      transition_persisted=False,
                      epoch_transition_authorized=False,
                      root_trust_verified=False,
                      independent_custody_verified=False,
                      owner_identity_verified=False,
                      installer_authorized=False,
                      safe_to_resume=False)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError,InvalidSignature):
        return result("BLOCKED","TRANSITION_DENIED_NO_REAL_AUTHORITY",
                      mathematical_signatures_valid=False,
                      epoch_transition_authorized=False,
                      root_trust_verified=False,
                      independent_custody_verified=False,
                      installer_authorized=False,
                      safe_to_resume=False)
