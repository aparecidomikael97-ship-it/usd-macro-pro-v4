"""Private evidence blueprint. Synthetic inputs only; safe public projection.

No artifact retrieval, signing, enrollment, verification or checkpoint writes.
Future private collectors need separate authorization and institutional trust.
"""
from atlasquant_aion_first_install_preparation.contracts import digest_value, exact, integer, result, token, tokens, ContractError
from atlasquant_aion_first_install_preparation.plan import DEPENDENCIES

FIELDS = frozenset({"requirement_id", "tenant_alias", "scope_alias", "experiment_id",
    "proof_type", "source_ref", "artifact_sha256", "attestation_ref", "observed_at",
    "expires_at", "negative_result", "unsatisfied_dependencies", "verifier_alias",
    "revocation", "audit_decision", "block_reason"})

def synthetic_dossier():
    return {"schema":"AION_PRIVATE_EVIDENCE_BLUEPRINT_V2", "mode":"SYNTHETIC_ONLY",
        "requirements":[dict(requirement_id=k,tenant_alias="fixture-tenant",scope_alias="fixture-scope",
            experiment_id="fixture-experiment",proof_type="SIMULATION",source_ref="fixture://not-evidence",
            artifact_sha256="a"*64,attestation_ref="fixture://untrusted-attestation",observed_at=1000,
            expires_at=1100,negative_result="UNKNOWN",unsatisfied_dependencies=list(DEPENDENCIES[k]),
            verifier_alias="fixture-institution",revocation="UNKNOWN",audit_decision="BLOCKED",
            block_reason="INDEPENDENT_PROOF_ABSENT") for k in DEPENDENCIES]}

def review_dossier(value, *, now):
    try:
        exact(value, {"schema", "mode", "requirements"})
        if (value["schema"] != "AION_PRIVATE_EVIDENCE_BLUEPRINT_V2"
                or value["mode"] != "SYNTHETIC_ONLY" or not integer(now)):
            raise ContractError("SCHEMA_INVALID")
        rows = value["requirements"]
        if type(rows) is not list or len(rows) != 20:
            raise ContractError("TWENTY_REQUIRED")
        seen = set()
        for row in rows:
            exact(row, FIELDS)
            if type(row["requirement_id"]) is not str or row["requirement_id"] not in DEPENDENCIES:
                raise ContractError("REQUIREMENT_UNKNOWN")
            if row["requirement_id"] in seen:
                raise ContractError("DUPLICATE_REQUIREMENT")
            seen.add(row["requirement_id"])
            for field in ("tenant_alias", "scope_alias", "experiment_id", "verifier_alias"):
                if not token(row[field]) or not row[field].startswith("fixture-"):
                    raise ContractError("SYNTHETIC_ALIAS_REQUIRED")
            for field in ("source_ref", "attestation_ref"):
                if (type(row[field]) is not str or not row[field].startswith("fixture://")
                        or len(row[field]) > 160):
                    raise ContractError("PRIVATE_SOURCE_NOT_PERMITTED")
            if (not digest_value(row["artifact_sha256"])
                    or row["proof_type"] != "SIMULATION"
                    or not integer(row["observed_at"]) or not integer(row["expires_at"])
                    or not row["observed_at"] <= now < row["expires_at"]
                    or row["expires_at"]-row["observed_at"] > 86400
                    or type(row["negative_result"]) is not str or row["negative_result"] not in ("UNKNOWN", "SIMULATED_PASS", "SIMULATED_FAIL")
                    or type(row["revocation"]) is not str or row["revocation"] not in ("UNKNOWN", "REVOKED", "SIMULATED_NOT_REVOKED")
                    or row["audit_decision"] != "BLOCKED"
                    or row["block_reason"] != "INDEPENDENT_PROOF_ABSENT"
                    or not tokens(row["unsatisfied_dependencies"],20)
                    or set(row["unsatisfied_dependencies"]) != set(DEPENDENCIES[row["requirement_id"]])):
                raise ContractError("EVIDENCE_CONTRACT_INVALID")
        # Whitelist-only projection. Never echo hashes, URIs, aliases or exceptions.
        return result("REFERENCE_DOSSIER_VALID_UNTRUSTED", "TWENTY_INDEPENDENT_PROOFS_STILL_ABSENT",
            unresolved_gate_count=20, requirements=[{"id":k,"state":"BLOCKED"} for k in DEPENDENCIES])
    except (ValueError, TypeError, KeyError, RecursionError):
        return result("BLOCKED", "DOSSIER_REJECTED_NO_PRIVATE_DATA_ECHO", unresolved_gate_count=20)
