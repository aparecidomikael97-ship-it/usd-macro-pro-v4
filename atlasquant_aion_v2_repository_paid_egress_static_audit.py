"""Static inventory of Python paid-AI egress bypasses and source hard-deny.

CI-only source audit: never executes imported repository modules or network.
Fail CLOSED when a new direct HTTP POST/SDK model call appears outside the
only known provider adapter. This is *not* a dynamic runtime/JS/dependency
audit, nor a proof against import hooks, compiled code or arbitrary exec.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

SCHEMA="ATLASQUANT_AION_V2_PAID_EGRESS_REPOSITORY_STATIC_AUDIT_V1"
STATE_PASS="EXPLICIT_PYTHON_EGRESS_BOUNDARY_STATICALLY_INTACT_NOT_AUTHORIZED"
STATE_FAIL="BLOCKED_PYTHON_PROVIDER_EGRESS_BYPASS_OR_LOCK_MUTATION"
PROVIDER_PATH="atlasquant_aion_provider.py"
GATE="_PAID_MODEL_DISPATCH_HARD_DENY"
VENDOR_MODULES={
    "openai","anthropic","litellm","cohere","groq",
    "google.generativeai","google.genai","mistralai",
}
NETWORK_MODULES={
    "requests","httpx","aiohttp","urllib.request","urllib3",
}
EXCLUDES={".git",".venv","venv","__pycache__","node_modules",
          ".pytest_cache",".tox","build","dist","site-packages"}
# This allowlist is ONE exact source location/function. A new path, even
# with the same endpoint or signature, is a failure needing human review.
ALLOWED_SOURCE_SINK=(PROVIDER_PATH,"execute_openai_answer","client.post")
DANGEROUS_METHODS={
    "post","request","send","create","acreate","generate_content",
    "generate_content_async","generate","responses_create",
    "create_async","invoke",
}
HTTP_METHODS={"post","request","send","put","patch","delete"}
SDK_CHAIN_MARKERS={"responses","completions","messages","chat","batches",
                   "generate_content","generate","invoke"}


def _is_prod(path:Path,root:Path)->bool:
    try:
        rel=path.relative_to(root)
    except ValueError:
        return False
    if any(x in EXCLUDES for x in rel.parts):
        return False
    if (rel.parts[0] in {"tests","test","fixtures","examples","scripts"}
        or path.name.startswith("test_")
        or path.name.endswith("_test.py")
        or path.name=="conftest.py"):
        return False
    return path.suffix==".py"


def _dotted(node:ast.AST)->str:
    if isinstance(node,ast.Name):
        return node.id
    if isinstance(node,ast.Attribute):
        prefix=_dotted(node.value)
        return prefix+"."+node.attr if prefix else node.attr
    if isinstance(node,ast.Call):
        return _dotted(node.func)+"()"
    if isinstance(node,ast.Subscript):
        return _dotted(node.value)+"[]"
    return ""


def _imports(tree:ast.Module)->dict[str,str]:
    aliases:dict[str,str]={}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for n in node.names:
                aliases[n.asname or n.name.split(".")[0]]=(
                    n.name if n.asname else n.name.split(".")[0]
                )
        elif isinstance(node,ast.ImportFrom):
            base="."*node.level+(node.module or "")
            for n in node.names:
                if n.name!="*":
                    aliases[n.asname or n.name]=base+"."+n.name
    return aliases


def _resolved(name:str,aliases:dict[str,str])->str:
    root,_,tail=name.partition(".")
    return aliases.get(root,root)+("." +tail if tail else "")


def _function_for(call:ast.AST,parents:dict[int,ast.AST])->str:
    current=parents.get(id(call))
    while current is not None:
        if isinstance(current,(ast.FunctionDef,ast.AsyncFunctionDef)):
            return current.name
        current=parents.get(id(current))
    return "<module>"


def _risk_class(name:str,resolved:str,imports:set[str])->str:
    end=name.rsplit(".",1)[-1]
    if end in HTTP_METHODS:
        # Calls on caller-controlled methods like client.post must be
        # inventoried even when their object type is not statically known.
        if end in {"post","request"}:
            return "POTENTIAL_HTTP_SEND_METHOD"
        if (resolved.startswith(tuple(x+"." for x in NETWORK_MODULES))
            or any(x in imports for x in NETWORK_MODULES)
            and end in {"send","put","patch","delete"}):
            return "POTENTIAL_HTTP_TRANSPORT_METHOD"
    if (resolved.split(".",1)[0] in {"openai","anthropic","cohere","groq",
                                       "litellm","mistralai"}
        or resolved.startswith("google.genai")
        or resolved.startswith("google.generativeai")):
        if end in DANGEROUS_METHODS or end in {
            "OpenAI","AsyncOpenAI","Anthropic","AsyncAnthropic",
            "Client","AsyncClient","GenerativeModel",
        }:
            return "VENDOR_SDK_CREATION_OR_MODEL_CALL"
    if end in {"create","acreate","generate_content","generate","invoke"}:
        if (any(x in name.lower().split(".") for x in SDK_CHAIN_MARKERS)
            or any(x in imports for x in VENDOR_MODULES)):
            return "UNSCOPED_MODEL_SDK_CALL"
    if end in {"urlopen","urlretrieve","PoolManager","ClientSession"}:
        if any(x in resolved for x in ("urllib.","urllib3.","aiohttp.")):
            return "POTENTIAL_RAW_HTTP_CLIENT"
    return ""


def _source_lock(tree:ast.Module)->list[str]:
    issues:list[str]=[]
    assignments=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.Assign,ast.AnnAssign,ast.NamedExpr)):
            targets=(node.targets if isinstance(node,ast.Assign)
                     else [node.target])
            if any(isinstance(t,ast.Name) and t.id==GATE for t in targets):
                assignments.append(node)
        elif isinstance(node,(ast.AugAssign,ast.Delete)):
            targets=[node.target] if isinstance(node,ast.AugAssign) else node.targets
            if any(isinstance(t,ast.Name) and t.id==GATE for t in targets):
                assignments.append(node)
    if len(assignments)!=1 or not isinstance(assignments[0],ast.Assign):
        return ["PROVIDER_LOCK_NOT_EXACT_SINGLE_ASSIGNMENT"]
    assignment=assignments[0]
    if (not isinstance(assignment.value,ast.Constant)
        or assignment.value.value is not True):
        issues.append("PROVIDER_LOCK_NOT_LITERAL_TRUE")
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)
               and n.name=="execute_openai_answer"]
    if len(functions)!=1:
        return issues+["PUBLIC_PROVIDER_ENTRYPOINT_MISSING_OR_DUPLICATED"]
    fn=functions[0]
    gates=[]
    posts=[]
    for n in ast.walk(fn):
        if (isinstance(n,ast.If)
            and isinstance(n.test,ast.Compare)
            and isinstance(n.test.left,ast.Name)
            and n.test.left.id==GATE
            and len(n.test.ops)==1 and isinstance(n.test.ops[0],ast.Is)
            and len(n.test.comparators)==1
            and isinstance(n.test.comparators[0],ast.Constant)
            and n.test.comparators[0].value is True):
            gates.append(n)
        if isinstance(n,ast.Call) and _dotted(n.func)=="client.post":
            posts.append(n)
    if len(gates)!=1:
        issues.append("REAL_PROVIDER_LOCK_GUARD_MISSING_OR_DUPLICATED")
    if len(posts)!=1:
        issues.append("REAL_PROVIDER_POST_SITE_UNEXPECTED")
    if len(gates)==1:
        gate=gates[0]
        if (len(gate.body)!=1
            or not isinstance(gate.body[0],ast.Return)
            or not isinstance(gate.body[0].value,ast.Dict)):
            issues.append("LOCK_BRANCH_DOES_NOT_UNCONDITIONALLY_RETURN")
        else:
            literal=gate.body[0].value
            mapped={
                k.value:v for k,v in zip(literal.keys,literal.values)
                if isinstance(k,ast.Constant) and isinstance(k.value,str)
            }
            if (not isinstance(mapped.get("state"),ast.Constant)
                or mapped["state"].value!="BLOCKED_INDEPENDENT_TRUST_NOT_ENROLLED"):
                issues.append("LOCK_RETURN_STATE_CHANGED")
            for field in ("called","paid_dispatch_authorized",
                          "model_invocation_authorized","provider_called"):
                v=mapped.get(field)
                if not isinstance(v,ast.Constant) or v.value is not False:
                    issues.append("LOCK_RETURN_AUTHORITY_FLAG_NOT_FALSE:"+field)
        if len(posts)==1 and gate.lineno>=posts[0].lineno:
            issues.append("PAID_POST_BEFORE_TRUST_LOCK")
    return issues


def audit_python_paid_egress(root:Path)->dict[str,Any]:
    root=Path(root).resolve()
    violations=[]
    approved=[]
    candidates=[]
    files=0
    for path in sorted(root.rglob("*.py")):
        if not _is_prod(path,root):
            continue
        files+=1
        relative=path.relative_to(root).as_posix()
        try:
            tree=ast.parse(path.read_text("utf-8"),filename=relative)
        except (SyntaxError,UnicodeError,OSError) as exc:
            violations.append({"path":relative,"line":0,
                               "reason":"UNREADABLE_OR_INVALID_PYTHON_SOURCE",
                               "kind":type(exc).__name__})
            continue
        alias=_imports(tree)
        deps=set(alias.values())
        parents={id(child):node for node in ast.walk(tree)
                 for child in ast.iter_child_nodes(node)}
        if relative==PROVIDER_PATH:
            for issue in _source_lock(tree):
                violations.append({"path":relative,"line":0,"reason":issue})
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                raw=_dotted(node.func)
                resolved=_resolved(raw,alias)
                reason=_risk_class(raw,resolved,deps)
                if not reason:
                    continue
                current=_function_for(node,parents)
                entry={"path":relative,"line":node.lineno,
                       "function":current,"call":raw,"reason":reason}
                candidates.append(entry)
                if (relative,current,raw)==ALLOWED_SOURCE_SINK:
                    approved.append(entry)
                else:
                    violations.append(entry)
    if files==0:
        violations.append({"path":"","line":0,"reason":"NO_PRODUCTION_PYTHON_SCANNED"})
    if len(approved)!=1:
        violations.append({"path":PROVIDER_PATH,"line":0,
                           "reason":"EXPECTED_SINGLE_SEALED_PROVIDER_POST_NOT_FOUND"})
    # Never emit source contents, token strings, stack traces or secrets.
    return {
        "schema":SCHEMA,
        "state":STATE_FAIL if violations else STATE_PASS,
        "static_analysis_only":True,
        "production_python_files_scanned":files,
        "recognized_potential_send_sites":len(candidates),
        "expected_sealed_send_site_count":len(approved),
        "violations":violations[:200],
        "violations_total":len(violations),
        "paid_dispatch_authorized":False,
        "real_provider_called":False,
        "network_called":False,
        "runtime_dynamic_imports_verified":False,
        "javascript_typescript_scanned":False,
        "third_party_dependencies_scanned":False,
        "runtime_monkeypatch_resistance_verified":False,
        "safe_to_merge_or_deploy":False,
    }


def main()->int:
    import json
    result=audit_python_paid_egress(Path(__file__).resolve().parent)
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0 if result["state"]==STATE_PASS else 1


if __name__=="__main__":
    raise SystemExit(main())
