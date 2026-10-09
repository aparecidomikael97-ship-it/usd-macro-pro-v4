"""Fail-closed AST source audit for all 21 legacy GitHub HTTP mutation returns.

Only checks checked-out source, no imports of application files or network.
The expected 17 Contents PUT and 4 Actions variables POST/PATCH sites are
the same pinned inventory as #1147; all must wrap the returned response.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from atlasquant_aion_v2_repository_paid_egress_static_audit import (
    LEGACY_OTHER_NETWORK_WRITE_SITES,_dotted,_function_for,
)

SCHEMA="ATLASQUANT_AION_V2_GITHUB_WRITE_RESPONSE_STATUS_AUDIT_V1"
PASS="ALL_21_GITHUB_WRITE_RESPONSE_STATUS_GUARDS_PRESENT_NO_AUTHORITY"
BLOCK="BLOCKED_GITHUB_WRITE_RESPONSE_ACCEPTANCE_REGRESSION"
GUARD="reject_github_write_unexpected_status"
IMPORT_MODULE="atlasquant_aion_v2_github_write_response_guard"
MODES={"requests.put":"contents_put","requests.post":"variable_post","requests.patch":"variable_patch"}

def audit_github_write_response_status(
    root:Path,*,sites:frozenset[tuple[str,str,str]]|None=None,
)->dict[str,Any]:
    root=Path(root).resolve()
    expected=LEGACY_OTHER_NETWORK_WRITE_SITES if sites is None else sites
    findings=[]
    checked=0
    module_cache={}
    for path,fn_name,call_name in sorted(expected):
        if path not in module_cache:
            try:
                module_cache[path]=ast.parse((root/path).read_text("utf-8"),filename=path)
            except (OSError,UnicodeError,SyntaxError):
                module_cache[path]=None
        tree=module_cache[path]
        if tree is None:
            findings.append({"file":path,"function":fn_name,"reason":"MISSING_OR_INVALID_SOURCE"})
            continue
        imports=[
            item for statement in tree.body if isinstance(statement,ast.ImportFrom)
            and statement.module==IMPORT_MODULE
            for item in statement.names if item.name==GUARD and item.asname is None
        ]
        if len(imports)!=1:
            findings.append({"file":path,"function":fn_name,"reason":"RESPONSE_GUARD_PINNED_IMPORT_REQUIRED"})
            continue
        parents={id(child):parent for parent in ast.walk(tree)
                 for child in ast.iter_child_nodes(parent)}
        matches=[
            node for node in ast.walk(tree)
            if isinstance(node,ast.Call) and _dotted(node.func)==call_name
            and _function_for(node,parents)==fn_name
        ]
        if len(matches)!=1:
            findings.append({"file":path,"function":fn_name,"reason":"EXACT_WRITE_SITE_NOT_UNIQUE"})
            continue
        original=matches[0]
        wrapper=parents.get(id(original))
        mode=MODES.get(call_name)
        if (not isinstance(wrapper,ast.Call)
            or _dotted(wrapper.func)!=GUARD
            or len(wrapper.args)!=2 or wrapper.args[0] is not original
            or not isinstance(wrapper.args[1],ast.Constant)
            or wrapper.args[1].value!=mode or wrapper.keywords):
            findings.append({"file":path,"function":fn_name,
                             "reason":"WRITE_RESULT_NOT_IMMEDIATELY_CHECKED"})
            continue
        checked+=1
    wanted=len(expected)
    if checked!=wanted and not findings:
        findings.append({"reason":"WRITE_SITE_COUNT_MISMATCH"})
    return {
        "schema":SCHEMA,
        "state":PASS if not findings else BLOCK,
        "expected_write_sites":wanted,
        "exact_response_wrapped_sites":checked,
        "files_reviewed":len(set(x[0] for x in expected)),
        "findings":findings[:100],
        "finding_count":len(findings),
        "source_only":True,
        "actual_http_writes_executed":False,
        "response_origin_verified":False,
        "write_success_certified":False,
        "unknown_outcome_reconciled":False,
        "safe_to_retry":False,
        "owner_trust_enrolled":False,
        "paid_dispatch_authorized":False,
        "safe_to_deploy":False,
    }

def main()->int:
    result=audit_github_write_response_status(Path(__file__).resolve().parent)
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0 if result["state"]==PASS else 1
if __name__=="__main__":
    raise SystemExit(main())
