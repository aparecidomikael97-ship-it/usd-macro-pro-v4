"""Source-only CI gate: 28 authenticated GitHub GET results have a status wrapper.

This checks literal call structure only, not actual network or response origin.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from atlasquant_aion_v2_github_token_read_no_redirect_audit import SITES,_dot,_func_for

SCHEMA="ATLASQUANT_AION_V2_GITHUB_TOKEN_GET_RESPONSE_STATUS_AUDIT_V1"
PASS="EXACT_GITHUB_GET_RESPONSE_STATUS_GUARDS_PRESENT_NO_AUTHORITY"
BLOCK="BLOCKED_GITHUB_GET_RESPONSE_STATUS_GUARD_BYPASS"
GUARD="reject_github_read_unexpected_status"
IMPORT_MODULE="atlasquant_aion_v2_github_read_response_guard"

def audit_github_get_response_status(
    root:Path,*,sites:dict[str,tuple[str,...]]|None=None,
)->dict[str,Any]:
    root=Path(root).resolve()
    expected=SITES if sites is None else sites
    findings=[]
    verified=0
    for filename,methods in sorted(expected.items()):
        try:
            tree=ast.parse((root/filename).read_text("utf-8"),filename=filename)
        except (OSError,UnicodeError,SyntaxError):
            findings.append({"file":filename,"reason":"SOURCE_NOT_AVAILABLE_OR_INVALID"})
            continue
        imports=[
            node for stmt in tree.body if isinstance(stmt,ast.ImportFrom)
            and stmt.module==IMPORT_MODULE
            for node in stmt.names if node.name==GUARD and node.asname is None
        ]
        if len(imports)!=1:
            findings.append({"file":filename,"reason":"STATUS_GUARD_PINNED_IMPORT_REQUIRED"})
            continue
        parents={id(child):parent for parent in ast.walk(tree)
                 for child in ast.iter_child_nodes(parent)}
        calls=[
            (n,_func_for(n,parents))
            for n in ast.walk(tree) if isinstance(n,ast.Call)
            and _dot(n.func)=="requests.get"
        ]
        for method in methods:
            matching=[n for n,fn in calls if fn==method]
            if len(matching)!=1:
                findings.append({"file":filename,"function":method,
                                 "reason":"EXACT_AUTHENTICATED_GET_NOT_UNIQUE"})
                continue
            req=matching[0]
            parent=parents.get(id(req))
            if (not isinstance(parent,ast.Call) or _dot(parent.func)!=GUARD
                or len(parent.args)!=1 or parent.args[0] is not req
                or parent.keywords):
                findings.append({"file":filename,"function":method,
                                 "reason":"GITHUB_GET_RESPONSE_NOT_WRAPPED_IMMEDIATELY"})
                continue
            verified+=1
    total=sum(len(methods) for methods in expected.values())
    if verified!=total and not findings:
        findings.append({"reason":"RESPONSE_STATUS_GUARD_INVENTORY_COUNT_DRIFT"})
    return {
        "schema":SCHEMA,
        "state":PASS if not findings else BLOCK,
        "expected_github_token_get_sites":total,
        "exact_response_status_wrapped_sites":verified,
        "files_scanned":len(expected),
        "findings":findings[:100],
        "finding_count":len(findings),
        "source_static_only":True,
        "unexpected_status_rejected_at_instrumented_sites":not findings,
        "github_response_provenance_verified":False,
        "external_proxy_tls_verified":False,
        "live_github_traffic_tested":False,
        "owner_trust_enrolled":False,
        "real_github_write_authorized":False,
        "paid_provider_authorized":False,
        "safe_to_deploy":False,
        "network_called":False,
    }

def main()->int:
    result=audit_github_get_response_status(Path(__file__).resolve().parent)
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0 if result["state"]==PASS else 1

if __name__=="__main__":
    raise SystemExit(main())
