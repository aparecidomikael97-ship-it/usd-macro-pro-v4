"""Inert source-only destination proof for 21 known GitHub write callsites.

Never imports inspected modules, resolves DNS, creates requests or grants
network access. A constant HTTPS GitHub ORIGIN in an AST f-string and the
expected GitHub API route are required for every caller-supplied URL.
Python AST cannot prove safe dynamic interpolations, redirect policy,
live DNS/TLS/proxies, or third-party dependency behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from atlasquant_aion_v2_repository_paid_egress_static_audit import (
    LEGACY_OTHER_NETWORK_WRITE_SITES, _dotted, _function_for,
)

SCHEMA="ATLASQUANT_AION_V2_LEGACY_NETWORK_WRITE_DESTINATION_REVIEW_V1"
PASS="STATIC_GITHUB_WRITE_DESTINATIONS_MATCH_NO_NETWORK_AUTHORITY"
BLOCK="BLOCKED_WRITE_DESTINATION_SOURCE_OR_GITHUB_ROUTE_CHANGED"
GITHUB="https://api.github.com/repos/"
CONTENTS="GITHUB_REPOSITORY_CONTENTS_WRITE"
VARIABLES="GITHUB_ACTIONS_VARIABLES_MUTATION"
ALLOWED_HELPERS=frozenset({
    "_url","_contents_url","_variable_collection_url","_variable_url",
})
KNOWN_SITES=frozenset(LEGACY_OTHER_NETWORK_WRITE_SITES)


def _type_for(site:tuple[str,str,str])->str:
    return VARIABLES if site[0]=="atlasquant_aion_global_worker_activation.py" else CONTENTS


def _module_function(tree:ast.Module,name:str)->ast.FunctionDef|None:
    funcs=[n for n in tree.body
           if isinstance(n,ast.FunctionDef) and n.name==name]
    return funcs[0] if len(funcs)==1 else None


def _rooted_literal(node:ast.AST,route:str)->bool:
    """Require immutable origin before ANY attacker-influenced format slot."""
    if not isinstance(node,(ast.JoinedStr,ast.Constant)):
        return False
    if isinstance(node,ast.Constant):
        return False  # a hardcoded literal is not an existing baseline
    if not node.values or not isinstance(node.values[0],ast.Constant):
        return False
    first=node.values[0].value
    if not isinstance(first,str) or not first.startswith(GITHUB):
        return False
    # No dynamic origin: the first substitution occurs AFTER the canonical
    # github.com/repositories prefix. Path chunks must follow the repo slot.
    if len(node.values)<3 or not isinstance(node.values[1],ast.FormattedValue):
        return False
    # A fixed GitHub REST API route MUST appear after the dynamic repo.
    static_tail="".join(
        n.value for n in node.values[2:]
        if isinstance(n,ast.Constant) and isinstance(n.value,str)
    )
    if route==CONTENTS:
        return "/contents/" in static_tail
    return "/actions/variables" in static_tail


def _helper_origin(name:str,tree:ast.Module,route:str,
                   trail:frozenset[str])->bool:
    if name not in ALLOWED_HELPERS or name in trail:
        return False
    fn=_module_function(tree,name)
    if fn is None:
        return False
    returns=[n for n in ast.walk(fn) if isinstance(n,ast.Return)]
    if len(returns)!=1 or returns[0].value is None:
        return False
    expr=returns[0].value
    if name=="_variable_url":
        if route!=VARIABLES or not isinstance(expr,ast.JoinedStr):
            return False
        values=expr.values
        if (len(values)!=3 or not isinstance(values[0],ast.FormattedValue)
            or not isinstance(values[0].value,ast.Call)
            or _dotted(values[0].value.func)!="_variable_collection_url"
            or not isinstance(values[1],ast.Constant)
            or values[1].value!="/"
            or not isinstance(values[2],ast.FormattedValue)
            or not isinstance(values[2].value,ast.Name)
            or values[2].value.id!="name"):
            return False
        # Ensure the appended feature-flag name is percent encoded, rather
        # than making the helper accept arbitrary URL/query fragments.
        encoded=[
            n for n in ast.walk(fn)
            if isinstance(n,ast.Assign)
            and len(n.targets)==1
            and isinstance(n.targets[0],ast.Name)
            and n.targets[0].id=="name"
            and isinstance(n.value,ast.Call)
            and _dotted(n.value.func)=="quote"
            and len(n.value.args)==1
            and isinstance(n.value.args[0],ast.Name)
            and n.value.args[0].id=="FEATURE_FLAG_NAME"
            and len(n.value.keywords)==1
            and n.value.keywords[0].arg=="safe"
            and isinstance(n.value.keywords[0].value,ast.Constant)
            and n.value.keywords[0].value.value==""
        ]
        return len(encoded)==1 and _helper_origin(
            "_variable_collection_url",tree,route,trail|{name}
        )
    return _rooted_literal(expr,route)


def _url_source_ok(expr:ast.AST,fn:ast.FunctionDef,tree:ast.Module,
                   line:int,route:str)->bool:
    if isinstance(expr,ast.JoinedStr):
        return _rooted_literal(expr,route)
    if isinstance(expr,ast.Call):
        name=_dotted(expr.func)
        return _helper_origin(name,tree,route,frozenset())
    if isinstance(expr,ast.Name):
        # Only one local assignment may establish the URL; do not accept
        # later reassignments or a URL supplied as a caller parameter.
        assigned=[
            node for node in ast.walk(fn)
            if isinstance(node,(ast.Assign,ast.AnnAssign,ast.NamedExpr))
            and getattr(node,"lineno",0)<line
            and any(isinstance(t,ast.Name) and t.id==expr.id
                    for t in (node.targets if isinstance(node,ast.Assign)
                              else [node.target]))
        ]
        all_reassign=[
            node for node in ast.walk(fn)
            if isinstance(node,(ast.Assign,ast.AnnAssign,ast.NamedExpr,ast.AugAssign))
            and any(isinstance(t,ast.Name) and t.id==expr.id
                    for t in (node.targets if isinstance(node,ast.Assign)
                              else [node.target]))
        ]
        if len(assigned)!=1 or len(all_reassign)!=1:
            return False
        node=assigned[0]
        return _url_source_ok(node.value,fn,tree,line,route)
    return False


def review_legacy_github_write_destinations(
    root:Path,*,sites:frozenset[tuple[str,str,str]]|None=None,
    require_runtime_guards:bool|None=None,
)->dict[str,Any]:
    """Full baseline by default, limited injected baseline in mutation tests."""
    root=Path(root).resolve()
    expected=KNOWN_SITES if sites is None else frozenset(sites)
    # Prior #1148 synthetic source fixtures isolate destination provenance;
    # full checked-out production scan MUST require real redirect/URL guards.
    enforce_guards=(sites is None if require_runtime_guards is None
                    else require_runtime_guards)
    findings=[]
    checked=0
    seen_files={}
    for path,fn_name,call_name in sorted(expected):
        if path not in seen_files:
            try:
                tree=ast.parse((root/path).read_text("utf-8"),filename=path)
                seen_files[path]=tree
            except (SyntaxError,UnicodeError,OSError):
                seen_files[path]=None
        tree=seen_files[path]
        if tree is None:
            findings.append({"path":path,"function":fn_name,
                             "reason":"UNREADABLE_SOURCE_OR_MISSING_FILE"})
            continue
        # Methods are nested inside classes, e.g. GitHubStore.save.
        all_fn=[n for n in ast.walk(tree)
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))
                and n.name==fn_name]
        if len(all_fn)!=1:
            findings.append({"path":path,"function":fn_name,
                             "reason":"EXACT_FUNCTION_NOT_UNIQUE"})
            continue
        fn=all_fn[0]
        calls=[
            n for n in ast.walk(fn)
            if isinstance(n,ast.Call) and _dotted(n.func)==call_name
            and _function_for(n,{id(child):parent
                for parent in ast.walk(tree)
                for child in ast.iter_child_nodes(parent)})==fn_name
        ]
        if len(calls)!=1:
            findings.append({"path":path,"function":fn_name,
                             "reason":"EXACT_NETWORK_WRITE_NOT_UNIQUE"})
            continue
        call=calls[0]
        if not call.args:
            findings.append({"path":path,"function":fn_name,
                             "reason":"NO_POSITIONAL_DESTINATION"})
            continue
        expected_route=_type_for((path,fn_name,call_name))
        url_expr=call.args[0]
        if (isinstance(url_expr,ast.Call)
            and _dotted(url_expr.func)=="guard_github_write_destination"
            and len(url_expr.args)==1 and not url_expr.keywords):
            url_expr=url_expr.args[0]
        elif enforce_guards:
            findings.append({"path":path,"function":fn_name,
                             "reason":"REQUIRED_RUNTIME_GITHUB_DESTINATION_GUARD_MISSING"})
            continue
        if enforce_guards:
            imported=[
                item for statement in tree.body
                if isinstance(statement,ast.ImportFrom)
                and statement.module=="atlasquant_aion_v2_github_write_url_guard"
                for item in statement.names
                if item.name=="guard_github_write_destination"
                and item.asname is None
            ]
            if len(imported)!=1:
                findings.append({"path":path,"function":fn_name,
                                 "reason":"GITHUB_WRITE_GUARD_IMPORT_NOT_TRUSTED"})
                continue
        if not _url_source_ok(url_expr,fn,tree,call.lineno,expected_route):
            findings.append({"path":path,"function":fn_name,
                             "reason":"DESTINATION_NOT_GITHUB_SOURCE_BOUND"})
            continue
        # For real source, Requests defaults are not accepted: require
        # explicit FALSE. For old mutation fixtures, still reject true.
        redirects=[k for k in call.keywords if k.arg=="allow_redirects"]
        if ((enforce_guards and len(redirects)!=1)
            or any(not (isinstance(k.value,ast.Constant)
                        and k.value.value is False) for k in redirects)):
            findings.append({"path":path,"function":fn_name,
                             "reason":"EXPLICIT_REDIRECT_POLICY_UNSAFE"})
            continue
        checked+=1
    return {
        "schema":SCHEMA,
        "state":BLOCK if findings else PASS,
        "analyzed_legacy_write_callsites":len(expected),
        "github_origin_and_route_bound_sites":checked,
        "github_repository_contents_sites":sum(
            _type_for(site)==CONTENTS for site in expected
        ),
        "github_actions_variable_sites":sum(
            _type_for(site)==VARIABLES for site in expected
        ),
        "unknown_destination_source_count":len(findings),
        "findings":findings,
        "source_static_only":True,
        "write_sites_require_guard_and_no_redirect":enforce_guards,
        "write_redirects_explicitly_disabled":enforce_guards and not findings,
        "runtime_destination_guard_present_in_source":enforce_guards and not findings,
        "redirect_chain_verified_closed":False,
        "interpolated_repo_and_path_sanitized":False,
        "real_dns_tls_cert_validated":False,
        "github_writes_authorized":False,
        "real_provider_called":False,
        "network_called":False,
        "owner_key_enrolled":False,
        "safe_to_deploy":False,
    }


def main()->int:
    output=review_legacy_github_write_destinations(
        Path(__file__).resolve().parent
    )
    print(json.dumps(output,sort_keys=True,ensure_ascii=False))
    return 0 if output["state"]==PASS else 1


if __name__=="__main__":
    raise SystemExit(main())
