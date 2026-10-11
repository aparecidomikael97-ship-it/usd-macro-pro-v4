"""Privacy, authorization and BRL cost planning; no legal/financial approval."""
from .contracts import MODE, ContractError, binding, digest, exact, integer, result, token, tokens

COST_CATEGORIES = (
    "COORDINATOR", "SECOND_WITNESS", "RETENTION", "STORAGE", "EGRESS", "LOGS",
    "RECOVERY", "MODEL_API", "TAXES", "FX_MARGIN", "LOCAL_OPERATIONS",
)
PRIVACY_CONTROLS = (
    "PURPOSE_MINIMIZATION", "RESIDENCY", "OPERATORS_SUBPROCESSORS", "RETENTION_DELETION",
    "TENANT_SESSION_ISOLATION", "LOG_SECRET_REDACTION", "INCIDENT_RECOVERY",
)

def review_governance(plan, *, expected_binding, now):
    try:
        scope = binding(expected_binding)
        exact(plan, frozenset({"mode", "binding_digest", "subject", "resource", "costs", "privacy"}))
        if (type(plan["mode"]) is not str or type(plan["binding_digest"]) is not str
                or plan["mode"] != MODE or plan["binding_digest"] != digest(scope) or not integer(now)):
            raise ContractError("GOVERNANCE_SCOPE_INVALID")
        s, r = plan["subject"], plan["resource"]
        exact(s, frozenset({"user_id", "tenant_id", "workspace_id", "role", "permissions"}))
        exact(r, frozenset({"resource_id", "tenant_id", "workspace_id", "required_permission"}))
        if any(type(s[k]) is not str for k in set(s)-{"permissions"}) or any(type(v) is not str for v in r.values()):
            raise ContractError("ACCESS_SCALAR_INVALID")
        if (not token(s["user_id"]) or s["role"] not in ("MEMBER_FIXTURE", "ADMIN_FIXTURE", "OWNER_FIXTURE")
                or not tokens(s["permissions"]) or not token(r["required_permission"])
                or r["required_permission"] not in s["permissions"] or r["resource_id"] != scope["resource_id"]
                or any(s[k] != scope[k] or r[k] != scope[k] for k in ("tenant_id", "workspace_id"))):
            raise ContractError("CROSS_TENANT_OR_RESOURCE_ACCESS_DENIED")
        costs = plan["costs"]
        if type(costs) is not list or len(costs) != len(COST_CATEGORIES):
            raise ContractError("CONSOLIDATED_QUOTE_INCOMPLETE")
        ids = set()
        total = 0
        unknown = []
        for row in costs:
            exact(row, frozenset({"category", "currency", "monthly_cents", "provenance", "expires_at"}))
            if type(row["currency"]) is not str or type(row["provenance"]) is not str:
                raise ContractError("QUOTE_SCALAR_INVALID")
            category = row["category"]
            if type(category) is not str or category not in COST_CATEGORIES or category in ids:
                raise ContractError("COST_CATEGORY_DUPLICATE_OR_UNKNOWN")
            ids.add(category)
            if (row["currency"] != "BRL" or row["provenance"] not in (MODE, "UNKNOWN")
                    or not integer(row["expires_at"]) or now >= row["expires_at"]):
                raise ContractError("UNSUPPORTED_OR_STALE_QUOTE")
            if row["monthly_cents"] is None:
                unknown.append(category)
            elif not integer(row["monthly_cents"], 0, 100_000_000):
                raise ContractError("COST_AMOUNT_INVALID")
            else:
                total += row["monthly_cents"]
            if row["provenance"] == "UNKNOWN" and category not in unknown:
                unknown.append(category)
        privacy = plan["privacy"]
        exact(privacy, frozenset(PRIVACY_CONTROLS))
        if any(type(privacy[k]) is not str or privacy[k] not in ("SIMULATED_REVIEW", "UNKNOWN") for k in PRIVACY_CONTROLS):
            raise ContractError("LEGAL_APPROVAL_NOT_ESTABLISHED")
        missing = tuple(k for k in PRIVACY_CONTROLS if privacy[k] == "UNKNOWN")
        state = "REFERENCE_GOVERNANCE_CONSISTENT_UNTRUSTED" if not unknown and not missing and total <= 20_000 else "BLOCKED"
        return result(state, "ACTUAL_QUOTES_LGPD_AND_DISTINCT_OWNER_APPROVALS_PENDING",
                      simulated_monthly_brl_cents=total if not unknown else None,
                      provisional_cap_brl_cents=20_000, unknown_cost_categories=tuple(unknown),
                      unknown_privacy_controls=missing, full_quote_brl_verified=False)
    except (ContractError, TypeError, ValueError):
        return result("BLOCKED", "GOVERNANCE_CONTRACT_REJECTED", full_quote_brl_verified=False)
