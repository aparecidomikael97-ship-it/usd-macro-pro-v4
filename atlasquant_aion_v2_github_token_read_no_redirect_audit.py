"""Audit all 27 known token-bearing GitHub GET read/preflight sites.

Pure source AST. The protection itself is the runtime URL validator and
Requests' explicit allow_redirects=False; this audit keeps it enforced.
No imports of inspected application modules and NO network.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

SCHEMA="ATLASQUANT_AION_V2_GITHUB_TOKEN_READ_GET_NO_REDIRECT_AUDIT_V1"
PASS="SOURCE_GITHUB_TOKEN_GET_GUARDS_INTACT_NO_AUTHORITY"
BLOCK="BLOCKED_GITHUB_TOKEN_GET_GUARD_OR_REDIRECT_REGRESSION"
IMPORT_MODULE="atlasquant_aion_v2_github_write_url_guard"
GUARD="guard_github_token_read_destination"

SITES={
    "atlasquant_aion_memory.py":("load_runtime_checkpoint",),
    "atlasquant_flight_recorder_store.py":("_fetch_remote",),
    "atlasquant_research_evidence_store.py":("_fetch",),
    "atlasquant_shadow_store.py":("_fetch",),
    "autopilot_v107.py":("gh_get_bytes","gh_put_bytes"),
    "currency_news_v1061.py":("_gh_read_csv_v1061","_gh_write_csv_v1061",
                               "_gh_read_json_v1061"),
    "currency_news_v1062.py":("_gh_read_csv_v1061","_gh_write_csv_v1061",
                               "_gh_read_json_v1061"),
    "currency_news_v107.py":("_gh_read_csv_v1061","_gh_write_csv_v1061",
                              "_gh_read_json_v1061"),
    "market_map_v10.py":("_save_snapshot",),
    "master_panel_v102.py":("_load_state","_save_state"),
    "twelve_budget_v1108.py":("load",),
    "usd_macro_pro_v4_cloud.py":(
        "_github_get_json_v937","_github_ler_csv_v84",
        "_github_salvar_csv_v84","_github_put_bytes_v104",
        "_salvar_feedback_v104","_autopilot_save_inputs_v107",
        "_config_ler_v937","_config_salvar_v937","_scanner_load_v934",
    ),
}


def _dot(node:ast.AST)->str:
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Attribute):
        return _dot(node.value)+"."+node.attr
    return ""


def _func_for(node:ast.AST,parents:dict[int,ast.AST])->str:
    cur=parents.get(id(node))
    while cur is not None:
        if isinstance(cur,(ast.FunctionDef,ast.AsyncFunctionDef)):
            return cur.name
        cur=parents.get(id(cur))
    return "<module>"


def audit_token_github_read_sites(
    root:Path,*,sites:dict[str,tuple[str,...]]|None=None,
)->dict[str,Any]:
    root=Path(root).resolve()
    wanted=SITES if sites is None else sites
    findings=[]
    verified=0
    public_queries_left_unchanged=True
    for file,methods in sorted(wanted.items()):
        try:
            tree=ast.parse((root/file).read_text(encoding="utf-8"),filename=file)
        except (UnicodeError,OSError,SyntaxError):
            findings.append({"file":file,"reason":"MISSING_OR_INVALID_SOURCE"})
            continue
        imports=[
            n for stmt in tree.body if isinstance(stmt,ast.ImportFrom)
            and stmt.module==IMPORT_MODULE
            for n in stmt.names if n.name==GUARD and n.asname is None
        ]
        if len(imports)!=1:
            findings.append({"file":file,"reason":"PINNED_RUNTIME_READ_GUARD_IMPORT_MISSING"})
            continue
        parents={id(ch):parent for parent in ast.walk(tree)
                 for ch in ast.iter_child_nodes(parent)}
        calls=[
            (n,_func_for(n,parents))
            for n in ast.walk(tree) if isinstance(n,ast.Call)
            and _dot(n.func)=="requests.get"
        ]
        for method in methods:
            matches=[node for node,fn in calls if fn==method]
            if len(matches)!=1:
                findings.append({"file":file,"function":method,
                                 "reason":"EXACT_GITHUB_GET_SITE_MISSING_OR_DUPLICATED"})
                continue
            call=matches[0]
            first=call.args[0] if call.args else None
            if (not isinstance(first,ast.Call) or _dot(first.func)!=GUARD
                or len(first.args)!=1 or first.keywords):
                findings.append({"file":file,"function":method,
                                 "reason":"GITHUB_RUNTIME_READ_URL_GUARD_MISSING"})
                continue
            redirects=[kw for kw in call.keywords if kw.arg=="allow_redirects"]
            if (len(redirects)!=1 or not isinstance(redirects[0].value,ast.Constant)
                or redirects[0].value.value is not False):
                findings.append({"file":file,"function":method,
                                 "reason":"GITHUB_READ_REDIRECT_MUST_BE_LITERAL_FALSE"})
                continue
            if (sum(kw.arg=="headers" for kw in call.keywords)!=1
                or sum(kw.arg=="params" for kw in call.keywords)!=1
                or sum(kw.arg=="timeout" for kw in call.keywords)!=1):
                findings.append({"file":file,"function":method,
                                 "reason":"GITHUB_GET_AUTH_REF_TIMEOUT_SHAPE_CHANGED"})
                continue
            verified+=1
        # New candidate `requests.get` with explicit GitHub `ref` params
        # outside the reviewed functions needs inspection; no wildcard allow.
        for node,fn in calls:
            if fn in methods:continue
            for kw in node.keywords:
                if kw.arg!="params" or not isinstance(kw.value,ast.Dict):continue
                if any(isinstance(k,ast.Constant) and k.value=="ref"
                       for k in kw.value.keys):
                    findings.append({"file":file,"function":fn,
                                     "reason":"UNREVIEWED_REF_SCOPED_GET_ADDED"})
                    break
    total=sum(len(m) for m in wanted.values())
    if verified!=total and not findings:
        findings.append({"reason":"VERIFIED_GITHUB_GET_COUNT_DRIFT"})
    return {
        "schema":SCHEMA,
        "state":PASS if not findings else BLOCK,
        "production_files_reviewed":len(wanted),
        "expected_token_github_get_sites":total,
        "exact_url_guard_and_no_redirect_sites":verified,
        "findings":findings[:100],
        "finding_count":len(findings),
        "source_static_only":True,
        "runtime_parser_invoked_by_callsite":bool(not findings),
        "token_redirects_disabled_in_source":bool(not findings),
        "public_non_github_market_gets_out_of_scope":public_queries_left_unchanged,
        "real_github_writes_authorized":False,
        "paid_dispatch_authorized":False,
        "network_called":False,
        "live_request_redirect_tested":False,
        "idp_owner_trust_enrolled":False,
        "safe_to_deploy":False,
    }


def main()->int:
    result=audit_token_github_read_sites(Path(__file__).resolve().parent)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0 if result["state"]==PASS else 1


if __name__=="__main__":
    raise SystemExit(main())
