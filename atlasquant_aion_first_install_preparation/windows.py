"""Windows pre-install checks as data contracts only. No host probes."""
from .contracts import MODE, ContractError, binding, digest, digest_value, exact, integer, result

CONTROLS = (
    "OS_ARCH_PREREQUISITES", "INSTALLER_SIGNATURE_INTEGRITY", "DEVICE_OWNER_AUTHORIZATION",
    "SECURE_CREDENTIAL_STORAGE", "LEAST_PRIVILEGE", "PROCESS_NETWORK_ISOLATION",
    "FILES_AND_ACL_INTEGRITY", "RESTART_RECOVERY", "CROSS_TENANT_ISOLATION",
    "AUDIT_REDACTION", "WINDOWS_HELLO_FIDO2_CAPABILITY",
)
FIELDS = frozenset({"id", "binding_digest", "claim", "provenance", "observed_at", "expires_at"})

def review_windows_checks(rows, *, expected_binding, now):
    try:
        scope_digest = digest(binding(expected_binding))
        if type(rows) is not list or len(rows) != len(CONTROLS) or not integer(now):
            raise ContractError("CHECKLIST_BOUND_INVALID")
        seen = set()
        unknown = []
        failed = []
        for row in rows:
            exact(row, FIELDS)
            if (not digest_value(row["binding_digest"]) or type(row["provenance"]) is not str
                    or type(row["claim"]) is not str):
                raise ContractError("CONTROL_SCALAR_INVALID")
            if type(row["id"]) is not str or row["id"] not in CONTROLS or row["id"] in seen:
                raise ContractError("CONTROL_ID_INVALID_OR_DUPLICATE")
            seen.add(row["id"])
            if row["binding_digest"] != scope_digest:
                raise ContractError("CONTROL_SCOPE_MISMATCH")
            if row["provenance"] not in (MODE, "UNKNOWN") or row["claim"] not in ("PASS", "FAIL", "UNKNOWN"):
                raise ContractError("PHYSICAL_CLAIM_NOT_SUPPORTED")
            if (not integer(row["observed_at"]) or not integer(row["expires_at"])
                    or not row["observed_at"] <= now < row["expires_at"]
                    or not 1 <= row["expires_at"] - row["observed_at"] <= 180):
                raise ContractError("CONTROL_STALE")
            if row["claim"] == "UNKNOWN" or row["provenance"] == "UNKNOWN":
                unknown.append(row["id"])
            elif row["claim"] == "FAIL":
                failed.append(row["id"])
        state = "REFERENCE_CHECKLIST_CONSISTENT_UNTRUSTED" if not unknown and not failed else "BLOCKED"
        return result(state, "REAL_WINDOWS_VALIDATION_NOT_PERFORMED",
                      unknown_controls=tuple(unknown), failed_controls=tuple(failed),
                      physical_control_count_verified=0, simulation_control_count=len(rows)-len(unknown))
    except (ContractError, TypeError, ValueError):
        return result("BLOCKED", "WINDOWS_CHECK_CONTRACT_REJECTED",
                      physical_control_count_verified=0, unknown_controls=CONTROLS)
