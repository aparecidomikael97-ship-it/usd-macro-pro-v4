"""WebAuthn-specific commitments from a single V3 read-only SQLite snapshot.

Old financial hold/head digests are NOT WebAuthn commitments. No signatures,
witness persistence, checkpoint reads or permission are created here.
"""
from hashlib import sha256
from pathlib import Path
import sqlite3
from atlasquant_aion_runtime_source_boundary_ref_v1 import canonical_bytes
from atlasquant_aion_first_install_preparation.contracts import (
    exact,integer,token,digest_value)
from .outcomes import result
from atlasquant_aion_first_install_preparation_v3.ledger_storage import (
    LedgerStorage,Refusal,scope_contract,verify_locked,_rows,ORDERS,LIMIT,ZERO)

DOMAIN=b"AION_WEBAUTHN_LEDGER_COMMITMENT_V4\0"
STATE_DOMAIN=b"AION_WEBAUTHN_LEDGER_STATE_V4\0"
CREDENTIAL_DOMAIN=b"AION_WEBAUTHN_CREDENTIAL_STATE_V4\0"
REVOCATION_DOMAIN=b"AION_WEBAUTHN_GENERATIONS_REVOCATIONS_V4\0"
CHALLENGE_DOMAIN=b"AION_WEBAUTHN_CHALLENGE_STATE_V4\0"
CAUSAL_DOMAIN=b"AION_WEBAUTHN_CAUSAL_OPERATIONS_V4\0"
SCHEMA="AION_WEBAUTHN_LEDGER_COMMITMENT_V4"
class MissingCausalReceipt(Refusal):pass
CONFIG=frozenset({"owner_id","tenant_id","workspace_id","ledger_id","epoch",
    "policy_id","policy_version","witness_id"})
FIELDS=CONFIG|frozenset({"schema","ledger_schema","sequence","local_head_sha256",
    "state_digest","credential_state_digest","generation_revocation_digest",
    "challenge_state_digest","causal_operations_digest","previous_commitment_digest"})

def domain_digest(value,domain):
    return sha256(canonical_bytes(value,domain=domain)).hexdigest()

def config_contract(value):
    exact(value,CONFIG)
    scope_contract({k:value[k] for k in ("owner_id","tenant_id","workspace_id")})
    if (not all(token(value[k]) and value[k].startswith("fixture-") for k in ("ledger_id","policy_id","witness_id"))
            or not integer(value["epoch"],1,2**31-1) or not integer(value["policy_version"],1,2**31-1)):
        raise Refusal("COMMITMENT_CONFIG_INVALID")
    return dict(value)

def commitment_contract(value):
    exact(value,FIELDS);config_contract({k:value[k] for k in CONFIG})
    if (value["schema"]!=SCHEMA or value["ledger_schema"]!="AION_WEBAUTHN_LEDGER_REFERENCE_V3"
            or not integer(value["sequence"],0,LIMIT)
            or not all(digest_value(value[k]) for k in FIELDS-CONFIG-{"schema","ledger_schema","sequence"})):
        raise Refusal("WEB_AUTHN_COMMITMENT_INVALID")
    return dict(value)

def commitment_digest(value):return domain_digest(commitment_contract(value),DOMAIN)

def comparable_state(value):
    value=commitment_contract(value)
    return {k:v for k,v in value.items() if k not in ("witness_id","previous_commitment_digest")}

def capture_ledger_reference(path,*,config,previous_commitment_digest,causal=None):
    """Commitment and optional causal receipt share ONE native RO transaction."""
    db=None;out=None
    try:
        config=config_contract(config)
        if not digest_value(previous_commitment_digest):raise Refusal("PREVIOUS_COMMITMENT_REQUIRED")
        if causal is not None:
            exact(causal,{"namespace","operation_id","request_digest"})
            if causal["namespace"]!="CONSUMPTION" or not token(causal["operation_id"]) or not digest_value(causal["request_digest"]):
                raise Refusal("CAUSAL_EXPECTATION_INVALID")
        scope={k:config[k] for k in ("owner_id","tenant_id","workspace_id")}
        reader=object.__new__(LedgerStorage);reader.path=Path(path).resolve();reader.scope=scope;reader.timeout=1
        db=reader.connect(read_only=True);db.execute("BEGIN")
        head=verify_locked(db,scope)
        rows={table:_rows(db,table,order) for table,order in ORDERS.items()}
        credentials=rows["credentials"]
        generations=[{k:r[k] for k in ("credential_id","generation","state","key_sha256")} for r in credentials]
        payload={**config,"schema":SCHEMA,"ledger_schema":"AION_WEBAUTHN_LEDGER_REFERENCE_V3",
            "sequence":head["sequence"],"local_head_sha256":head["head_digest"],
            "state_digest":domain_digest(rows,STATE_DOMAIN),
            "credential_state_digest":domain_digest({"credentials":credentials},CREDENTIAL_DOMAIN),
            "generation_revocation_digest":domain_digest({"generations":generations},REVOCATION_DOMAIN),
            "challenge_state_digest":domain_digest({"challenges":rows["challenges"],"attempts":rows["attempts"]},CHALLENGE_DOMAIN),
            "causal_operations_digest":domain_digest({"receipts":rows["receipts"]},CAUSAL_DOMAIN),
            "previous_commitment_digest":previous_commitment_digest}
        receipt=None
        if causal is not None:
            r=db.execute("SELECT * FROM receipts WHERE namespace=? AND operation_id=?",(causal["namespace"],causal["operation_id"])).fetchone()
            if r is None:
                raise MissingCausalReceipt("CAUSAL_RECEIPT_ABSENT_NO_RETRY")
            attempt=db.execute("SELECT * FROM attempts WHERE attempt_id=?",(causal["operation_id"],)).fetchone()
            if (r["request_digest"]!=causal["request_digest"] or attempt is None
                    or attempt["state"]!="CONSUMED" or attempt["request_digest"]!=causal["request_digest"]):
                raise Refusal("CAUSAL_EFFECT_CONFLICT")
            receipt=dict(namespace="CONSUMPTION",request_digest=r["request_digest"],sequence=r["sequence"],
                         historical_consumption_only=True)
        # Ledger ancestry permits comparison with an earlier pinned signed floor.
        ancestry=[{"sequence":0,"head_digest":ZERO}]+[
            {"sequence":r["sequence"],"head_digest":r["event_digest"]}
            for r in _rows(db,"events","sequence")]
        out=result("REFERENCE_SNAPSHOT_UNTRUSTED","LOCAL_SQLITE_NOT_AN_EXTERNAL_ANCHOR",
            commitment=commitment_contract(payload),commitment_digest=commitment_digest(payload),
            local_ancestry=ancestry,causal_receipt=receipt,
            independent_rollback_protection_verified=False)
    except MissingCausalReceipt:
        out=result("RECONCILIATION_REQUIRED","CAUSAL_RECEIPT_ABSENT_NO_RETRY")
    except Refusal:
        out=result("BLOCKED","SNAPSHOT_SCOPE_OR_CONTRACT_REJECTED")
    except (sqlite3.Error,ValueError,TypeError,KeyError,OSError,RecursionError):
        out=result("UNKNOWN_OUTCOME","SNAPSHOT_UNAVAILABLE_NO_RETRY")
    finally:
        if db is not None:
            try:db.close()
            except sqlite3.Error:out=result("UNKNOWN_OUTCOME","SNAPSHOT_CLOSE_UNCERTAIN_NO_RETRY")
    return out
