"""Bounded closed schemas. Digests identify simulation inputs, never trust."""
from hashlib import sha256
import json
import re

MODE = "OFFLINE_SIMULATION"
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
AUTHORITY_FIELDS = (
    "owner_identity_verified", "device_physically_verified",
    "independent_custody_verified", "installation_authorized",
    "worker_authorized", "execution_authorized", "merge_authorized",
    "deploy_authorized", "spending_approved", "network_authorized",
    "automatic_retry_authorized", "checkpoint_write_authorized",
)
BINDING_FIELDS = frozenset({
    "owner_id", "tenant_id", "workspace_id", "device_id", "credential_id",
    "repo", "branch", "path", "resource_id", "artifact_sha256",
    "operation", "permissions", "policy_generation",
})
OPERATIONS = frozenset({"INVENTORY_READ_ONLY", "INSTALL", "MERGE", "DEPLOY", "ACTIVATE_WORKER", "SPEND"})

class ContractError(ValueError):
    """Contains fixed reason codes only, never caller data."""

def exact(value, fields):
    if type(value) is not dict or len(value) != len(fields) or set(value) != fields:
        raise ContractError("CLOSED_SCHEMA_INVALID")

def token(value):
    return type(value) is str and bool(_TOKEN.fullmatch(value))

def digest_value(value):
    return type(value) is str and bool(_HASH.fullmatch(value))

def integer(value, minimum=0, maximum=2**53-1):
    return type(value) is int and minimum <= value <= maximum

def tokens(value, limit=16):
    return (type(value) is list and len(value) <= limit
            and all(token(x) for x in value) and len(set(value)) == len(value))

def binding(value):
    exact(value, BINDING_FIELDS)
    identifiers = BINDING_FIELDS - {"repo", "branch", "path", "artifact_sha256", "operation", "permissions", "policy_generation"}
    if not all(token(value[k]) for k in identifiers):
        raise ContractError("SCOPE_INVALID")
    repo, branch, path = value["repo"], value["branch"], value["path"]
    if (type(repo) is not str or len(repo) > 241 or repo.count("/") != 1
            or not all(token(x) for x in repo.split("/"))):
        raise ContractError("REPOSITORY_INVALID")
    if (type(branch) is not str or not 1 <= len(branch) <= 240
            or not all(token(x) and x not in (".", "..") for x in branch.split("/"))
            or ".." in branch or branch.endswith(".lock")):
        raise ContractError("BRANCH_INVALID")
    if (type(path) is not str or not 1 <= len(path) <= 240
            or "\\" in path or ":" in path or not path.isascii()
            or not all(token(x) and x not in (".", "..") and not x.endswith(".")
                       and x.split(".")[0].upper() not in {"CON", "PRN", "AUX", "NUL", *["COM"+str(i) for i in range(1,10)], *["LPT"+str(i) for i in range(1,10)]}
                       for x in path.split("/"))):
        raise ContractError("RESOURCE_PATH_INVALID")
    if (not digest_value(value["artifact_sha256"])
            or value["operation"] not in OPERATIONS
            or not tokens(value["permissions"]) or not value["permissions"]
            or not integer(value["policy_generation"], 1)):
        raise ContractError("OPERATION_BINDING_INVALID")
    # Private runtime data never enters this closed schema.
    return json.loads(json.dumps(value, allow_nan=False))

def digest(value):
    return sha256(b"AION_FIRST_INSTALL_OFFLINE_V1\0" + json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    ).encode()).hexdigest()

def result(state="BLOCKED", *reasons, **details):
    return {
        **details,
        "schema": "AION_FIRST_INSTALL_PREPARATION_V1", "mode": MODE,
        "status": "HARD_NO_GO", "state": state,
        "provenance": "SIMULATED_OR_UNKNOWN_NOT_INDEPENDENT_EVIDENCE",
        "blockers": tuple(sorted(set(reasons))),
        "network_called": False, "physical_checks_performed": False,
        "real_credentials_created": False,
        **{field: False for field in AUTHORITY_FIELDS},
    }

def production_authority(*_args, **_kwargs):
    """No callback, token, environment, receipt or fixture can authorize anything."""
    return result("BLOCKED", "INDEPENDENT_ENROLLMENT_AND_PHYSICAL_EVIDENCE_ABSENT")
