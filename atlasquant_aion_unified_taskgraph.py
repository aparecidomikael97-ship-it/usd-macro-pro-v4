"""V2.4 bounded task orchestration inside the existing single AION Core.

Pure planning and state transitions. RUNNABLE is eligibility, never execution.
Approval methods are trusted application boundaries, not client JSON handlers.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping

from atlasquant_aion_unified_runtime import AionRequest
from atlasquant_aion_unified_mission import prepare_aion_mission, validate_aion_mission
from atlasquant_aion_role_authority import official_role_authority_matrix
from atlasquant_aion_truth import normalize_evidence_record, assess_truth

SCHEMA = "ATLASQUANT_AION_TASKGRAPH_V24"
MAX_TASKS = 32
MAX_REFS = 64
MAX_AUDIT = 128
MAX_DOCUMENT_BYTES = 128 * 1024
MAX_PAYLOAD_BYTES = 4096
TASK_STATES = ("PLANNED", "QUEUED", "RUNNABLE", "WAITING_DEPENDENCY",
               "WAITING_APPROVAL", "BLOCKED", "COMPLETED", "FAILED",
               "CANCELLED", "SUPERSEDED")
BUDGET_STATES = ("ZERO_COST_LOCAL", "FREE_TIER", "PAID_ALLOWED", "PAID_BLOCKED")
ECOSYSTEMS = ("TRADER", "NEGOCIOS", "INVESTIMENTOS")
DANGEROUS_FLAGS = ("provider_calls", "external_email", "whatsapp", "crm_write",
                   "calendar_write", "payment_action", "real_orders",
                   "broker_execution", "biometric_approval")
INVARIANTS = {"external_action_executed": False, "execution_allowed": False,
              "executes_provider_call": False, "executes_billing": False,
              "real_orders_enabled": False, "automatic_resume_executes": False}
TRANSITIONS = {
    "PLANNED": {"QUEUED", "CANCELLED", "SUPERSEDED"},
    "QUEUED": {"RUNNABLE", "WAITING_DEPENDENCY", "WAITING_APPROVAL", "BLOCKED", "CANCELLED", "SUPERSEDED"},
    "RUNNABLE": {"COMPLETED", "FAILED", "WAITING_DEPENDENCY", "WAITING_APPROVAL", "BLOCKED", "CANCELLED", "SUPERSEDED"},
    "WAITING_DEPENDENCY": {"QUEUED", "RUNNABLE", "BLOCKED", "CANCELLED", "SUPERSEDED"},
    "WAITING_APPROVAL": {"QUEUED", "RUNNABLE", "BLOCKED", "CANCELLED", "SUPERSEDED"},
    "BLOCKED": {"QUEUED", "CANCELLED", "SUPERSEDED"},
    "FAILED": {"QUEUED", "CANCELLED", "SUPERSEDED"},
    "COMPLETED": set(), "CANCELLED": set(), "SUPERSEDED": set(),
}
# Future external intents remain metadata. No dispatcher/provider is imported.
_EXTERNAL_ROLES = {
    "provider_calls": "shadow", "external_email": "prime", "whatsapp": "commercial",
    "crm_write": "commercial", "calendar_write": "prime", "payment_action": "prime",
    "real_orders": "prime", "broker_execution": "prime", "biometric_approval": "guardian",
}
_ALIASES = {"pesquisa": "research", "arquitetura": "design", "auditoria": "audit",
            "execucao": "prepare_guarded_execution", "monitoramento": "observe",
            "lead": "qualify", "crm": "crm_context", "treinamento": "train",
            "coordenacao": "coordinate"}


class AionTaskgraphError(ValueError):
    def __init__(self, code):
        self.error_code = code
        super().__init__(code)


def _text(value, limit=256, *, empty=False):
    if not isinstance(value, str) or "\x00" in value or len(value) > limit:
        raise AionTaskgraphError("STRING_BOUND_OR_TYPE")
    text = " ".join(value.split())
    if not text and not empty:
        raise AionTaskgraphError("EMPTY_STRING")
    return text


def _bounded(value, depth=0):
    if depth > 5:
        raise AionTaskgraphError("PAYLOAD_DEPTH")
    if value is None or type(value) is bool:
        return value
    if type(value) in (int, float):
        if not math.isfinite(value) or abs(value) > 1e12:
            raise AionTaskgraphError("INVALID_NUMBER")
        return value
    if isinstance(value, str):
        return _text(value, 2000, empty=True)
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_REFS:
            raise AionTaskgraphError("LIST_BOUND")
        return [_bounded(v, depth+1) for v in value]
    if isinstance(value, Mapping):
        if len(value) > 32:
            raise AionTaskgraphError("MAPPING_BOUND")
        result = {}
        for key, item in value.items():
            key = _text(key, 80)
            if key in result:
                raise AionTaskgraphError("DUPLICATE_NORMALIZED_KEY")
            if any(s in key.casefold() for s in ("password", "secret", "api_key", "credential", "access_token")):
                raise AionTaskgraphError("SECRET_PAYLOAD_FORBIDDEN")
            result[key] = _bounded(item, depth+1)
        return result
    raise AionTaskgraphError("MALFORMED_PAYLOAD")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def _seal(plan):
    plan["plan_digest"] = _digest({k:v for k,v in plan.items() if k != "plan_digest"})
    if len(_canonical(plan).encode()) > MAX_DOCUMENT_BYTES:
        raise AionTaskgraphError("DOCUMENT_BOUND")
    return plan


def _stamp(now=None):
    stamp = now or datetime.now(timezone.utc)
    if not isinstance(stamp, datetime) or stamp.tzinfo is None:
        raise AionTaskgraphError("TIMESTAMP_INVALID")
    return stamp.astimezone(timezone.utc).isoformat()


def ecosystem_route(value):
    raw = unicodedata.normalize("NFKD", _text(value, 80))
    code = "".join(c for c in raw if not unicodedata.combining(c)).upper()
    code = {"BUSINESS":"NEGOCIOS", "TRADING":"TRADER", "INVESTMENTS":"INVESTIMENTOS"}.get(code, code)
    if code not in ECOSYSTEMS:
        raise AionTaskgraphError("ECOSYSTEM_INVALID")
    return code


def capability_catalog():
    rows = {}
    for role in official_role_authority_matrix()["roles"]:
        for cap in role["capabilities"]:
            rows[cap] = {"role":role["role_id"], "ecosystems":list(ECOSYSTEMS), "feature_flag":"", "risk":"LOCAL"}
    for cap in ("qualify", "draft_followup", "crm_context"):
        rows[cap]["ecosystems"] = ["NEGOCIOS"]
    for flag, role in _EXTERNAL_ROLES.items():
        rows[flag] = {"role":role, "ecosystems":["NEGOCIOS"] if flag in {"crm_write","whatsapp","external_email"} else ["TRADER"] if flag in {"real_orders","broker_execution"} else list(ECOSYSTEMS),
                     "feature_flag":flag, "risk":"EXTERNAL"}
    return rows


def route_task_role(capability, ecosystem):
    cap = _text(capability, 120)
    cap = _ALIASES.get(cap, cap)
    row = capability_catalog().get(cap)
    if not row:
        raise AionTaskgraphError("UNKNOWN_CAPABILITY")
    if ecosystem_route(ecosystem) not in row["ecosystems"]:
        raise AionTaskgraphError("ECOSYSTEM_CAPABILITY_MISMATCH")
    return {"capability":cap, **deepcopy(row)}


def feature_policy(flags=None):
    flags = {} if flags is None else flags
    if not isinstance(flags, Mapping):
        raise AionTaskgraphError("FEATURE_FLAGS_INVALID")
    return {name: flags.get(name) is True for name in DANGEROUS_FLAGS}


def budget_policy(budget=None):
    budget = {} if budget is None else budget
    if not isinstance(budget, Mapping):
        raise AionTaskgraphError("BUDGET_INVALID")
    mode = budget.get("mode", "ZERO_COST_LOCAL")
    if mode not in BUDGET_STATES:
        raise AionTaskgraphError("BUDGET_INVALID")
    limit = budget.get("authorized_limit", 0)
    if type(limit) not in (int, float) or not math.isfinite(limit) or not 0 <= limit <= 1e6:
        raise AionTaskgraphError("BUDGET_INVALID")
    paid = budget.get("paid_authorized") is True
    if mode == "PAID_ALLOWED" and not paid:
        mode = "PAID_BLOCKED"
    return {"mode":mode, "paid_authorized":paid, "authorized_limit":limit, "billing_executed":False}


def _refs(value):
    if not isinstance(value, (list, tuple)) or len(value) > MAX_REFS:
        raise AionTaskgraphError("REFS_BOUND_OR_TYPE")
    result = [_text(v, 120) for v in value]
    if len(set(result)) != len(result):
        raise AionTaskgraphError("DUPLICATE_REFERENCE")
    return result


def _normalized_request(request, ecosystem, access):
    if not isinstance(request, AionRequest):
        raise TypeError("AionRequest required")
    for v in (request.request_id, request.conversation_id, request.owner_id, request.tenant_id, request.workspace_id):
        _text(v)
    _text(request.request_id,140)
    _text(request.conversation_id,160)
    _text(request.user_message, 2000)
    _text(request.requested_action, 120)
    if not isinstance(request.attachments, (tuple, list)) or len(request.attachments)>16:
        raise AionTaskgraphError("ATTACHMENTS_BOUND")
    for v in request.attachments: _text(v)
    if not isinstance(request.evidence, (tuple,list)) or len(request.evidence)>MAX_REFS:
        raise AionTaskgraphError("EVIDENCE_BOUND")
    if not isinstance(request.source_context, Mapping):
        raise AionTaskgraphError("SOURCE_CONTEXT_INVALID")
    for key in ("owner_id","tenant_id","workspace_id"):
        if key in request.source_context and request.source_context[key] != getattr(request,key):
            raise AionTaskgraphError("SOURCE_SCOPE_MISMATCH")
    evidence = []
    for raw in request.evidence:
        if not isinstance(raw, Mapping):
            raise AionTaskgraphError("EVIDENCE_INVALID")
        row = _bounded(raw)
        if len(_canonical(row).encode())>MAX_PAYLOAD_BYTES:
            raise AionTaskgraphError("EVIDENCE_BOUND")
        # Legacy/unscoped evidence is not silently reclassified as CRM/market data.
        if not row.get("ecosystem"):
            continue
        if ecosystem_route(row["ecosystem"]) != ecosystem:
            raise AionTaskgraphError("EVIDENCE_ECOSYSTEM_MISMATCH")
        for key in ("owner_id","tenant_id","workspace_id"):
            if row.get(key) != getattr(request,key):
                raise AionTaskgraphError("EVIDENCE_SCOPE_MISMATCH")
        evidence.append(row)
    trusted_role = (access or {}).get("role", "USER")
    if trusted_role not in ("USER","SALES","ADMIN"):
        trusted_role = "USER"
    return replace(request, sector=ecosystem, evidence=tuple(evidence), source_context={},
                   authorization_context={"role":trusted_role})


def _defaults(objective, ecosystem):
    normalized = unicodedata.normalize("NFKD", objective).casefold()
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    if ecosystem == "NEGOCIOS" and any(word in normalized for word in ("automacao","implantacao")):
        stages = [("diagnostico","research","Diagnóstico",[]),
                  ("levantamento","qualify","Levantamento",["diagnostico"]),
                  ("proposta","design","Proposta",["levantamento"]),
                  ("configuracao","draft_action_plan","Configuração local proposta",["proposta"]),
                  ("testes","audit","Plano de testes e auditoria",["configuracao"]),
                  ("aprovacao","review","Revisão para aprovação",["testes"]),
                  ("implantacao","crm_write","Handoff de implantação futura",["aprovacao"])]
    else:
        stages = [("coordenacao","coordinate","Decompor objetivo",[]),
                  ("pesquisa","research","Levantar evidências",["coordenacao"]),
                  ("arquitetura","design","Preparar estratégia",["pesquisa"]),
                  ("auditoria","audit","Revisar plano",["arquitetura"]),
                  ("preparacao","draft_action_plan","Preparar entrega local",["auditoria"]),
                  ("monitoramento","observe","Plano de monitoramento",["preparacao"]),
                  ("treinamento","train","Preparar orientação",["preparacao"])]
    return [{"key":key, "capability":cap, "title":title, "depends_on":deps,
             "payload":{"objective":objective}, "expected_output":title,
             "evidence_required":["objective"]} for key,cap,title,deps in stages]


def _specs(raw, ecosystem):
    if not isinstance(raw, (tuple,list)) or not 1 <= len(raw) <= MAX_TASKS:
        raise AionTaskgraphError("TASKS_BOUND_OR_TYPE")
    result = []
    for row in raw:
        if not isinstance(row, Mapping) or len(row)>32:
            raise AionTaskgraphError("TASK_SPEC_INVALID")
        route = route_task_role(row.get("capability"),ecosystem)
        payload = _bounded(row.get("payload",{}))
        if not isinstance(payload, dict) or len(_canonical(payload).encode())>MAX_PAYLOAD_BYTES:
            raise AionTaskgraphError("PAYLOAD_BOUND_OR_TYPE")
        priority = row.get("priority",50)
        cost = row.get("estimated_cost",0)
        if type(priority) is not int or not 0 <= priority <= 100:
            raise AionTaskgraphError("PRIORITY_INVALID")
        if type(cost) not in (int,float) or not math.isfinite(cost) or not 0 <= cost <= 1e6:
            raise AionTaskgraphError("COST_INVALID")
        result.append({"key":_text(row.get("key"),120), "title":_text(row.get("title",row.get("key")),300),
                       "capability":route["capability"], "role":route["role"],
                       "depends_on":_refs(row.get("depends_on",[])), "payload":payload,
                       "evidence_required":_refs(row.get("evidence_required",[])),
                       "priority":priority, "estimated_cost":cost, "risk":route["risk"],
                       "feature_flag":route["feature_flag"],
                       "expected_output":_text(row.get("expected_output","local proposal"),300)})
    keys = [r["key"] for r in result]
    if len(keys) != len(set(keys)):
        raise AionTaskgraphError("DUPLICATE_TASK")
    return sorted(result,key=lambda r:r["key"])


def dependency_graph(tasks):
    if not isinstance(tasks, (tuple,list)) or len(tasks)>MAX_TASKS:
        raise AionTaskgraphError("TASKS_BOUND_OR_TYPE")
    by_key = {row["key"]:row for row in tasks}
    if len(by_key)!=len(tasks):
        raise AionTaskgraphError("DUPLICATE_TASK")
    indegree = {key:0 for key in by_key}
    children = {key:[] for key in by_key}
    for row in tasks:
        for dep in row["depends_on"]:
            if dep not in by_key:
                raise AionTaskgraphError("MISSING_DEPENDENCY")
            indegree[row["key"]] += 1
            children[dep].append(row["key"])
    ready = sorted(key for key,count in indegree.items() if count==0)
    order = []
    while ready:
        key = ready.pop(0); order.append(key)
        for child in sorted(children[key]):
            indegree[child] -= 1
            if indegree[child]==0:
                ready.append(child);ready.sort()
    if len(order)!=len(tasks):
        raise AionTaskgraphError("DEPENDENCY_CYCLE")
    return {"order":order, "edges":[[dep,row["key"]] for row in sorted(tasks,key=lambda r:r["key"]) for dep in sorted(row["depends_on"])]}


def _approval_binding(plan, task):
    return {"mission_id":plan["mission_id"], "task_id":task["task_id"],
            "capability":task["capability"], "approval_class":task["approval_class"],
            "payload_digest":task["payload_digest"], "scope_digest":plan["scope_digest"],
            "intent_digest":plan["intent_digest"]}


def _approval_valid(plan, task):
    if task["approved"] is not True or task["approved_scope"] != plan["scope"]:
        return False
    return task["approval_digest"] == _digest(_approval_binding(plan,task))


def _gate(plan, task, now=None):
    blockers = list(plan["base_mission"]["blockers"])
    dependencies = {t["key"]:t for t in plan["tasks"]}
    for dep in task["depends_on"]:
        state = dependencies[dep]["state"]
        if state in {"FAILED","BLOCKED","CANCELLED","SUPERSEDED"}:
            blockers.append("DEPENDENCY_"+state+":"+dep)
        elif state!="COMPLETED":
            blockers.append("WAITING_DEPENDENCY:"+dep)
    if task["feature_flag"] and plan["feature_flags"][task["feature_flag"]] is not True:
        blockers.append("FEATURE_DISABLED:"+task["feature_flag"])
    policy = plan["budget"]
    total = sum(row["estimated_cost"] for row in plan["tasks"])
    if policy["mode"]=="PAID_BLOCKED" or (total>0 and (policy["mode"]!="PAID_ALLOWED" or policy["paid_authorized"] is not True or total>policy["authorized_limit"])):
        blockers.append("PAID_BLOCKED")
    available = set()
    for raw in plan["evidence_snapshot"]:
        assessed = normalize_evidence_record(raw, now=now)
        if assessed["truth_state"] == "CONFIRMED":
            available.update(raw[k] for k in ("ref", "id", "source", "claim") if isinstance(raw.get(k), str))
    required = set(task["evidence_required"])
    required.update(ref for step in plan["base_mission"]["steps"] for ref in step["required_evidence"])
    if any(ref not in available for ref in required):
        blockers.append("MISSING_EVIDENCE")
    if assess_truth(plan["evidence_snapshot"],now=now)["conflict_state"] == "CONFLICT":
        blockers.append("EVIDENCE_CONFLICT")
    if plan["base_mission"]["mission_state"]=="WAITING_EVIDENCE":
        blockers.append("CANONICAL_EVIDENCE_REQUIRED")
    if task["approval_required"] and not _approval_valid(plan,task):
        blockers.append("WAITING_APPROVAL")
    return list(dict.fromkeys(blockers))


def evaluate_taskgraph(plan, *, now=None):
    validate_taskgraph(plan)
    rows = []
    for task in plan["tasks"]:
        blockers = _gate(plan,task,now)
        if any(b.startswith("DEPENDENCY_") for b in blockers) or any(b.startswith("FEATURE_DISABLED:") or b=="PAID_BLOCKED" or b in plan["base_mission"]["blockers"] for b in blockers):
            gate = "BLOCKED"
        elif any(b.startswith("WAITING_DEPENDENCY:") for b in blockers):
            gate = "WAITING_DEPENDENCY"
        elif any("EVIDENCE" in b for b in blockers):
            gate = "WAITING_EVIDENCE"
        elif "WAITING_APPROVAL" in blockers:
            gate = "WAITING_APPROVAL"
        else:
            gate = "RUNNABLE"
        rows.append({"task_id":task["task_id"], "key":task["key"], "state":task["state"],
                     "gate":gate, "blockers":blockers, **INVARIANTS})
    return rows


def _refresh_mission(plan):
    # Recovery never calls this function; only explicit state changes do.
    gates = [_gate(plan,t) for t in plan["tasks"] if t["state"] not in {"COMPLETED","CANCELLED","SUPERSEDED"}]
    blockers = list(dict.fromkeys(b for row in gates for b in row if not b.startswith("WAITING_DEPENDENCY:")))
    plan["blockers"] = blockers[:32]
    if plan["base_mission"]["blockers"] or any(t["state"] in {"FAILED","BLOCKED"} for t in plan["tasks"]) or any(b.startswith("FEATURE_DISABLED:") or b=="PAID_BLOCKED" or b.startswith("DEPENDENCY_") for b in blockers):
        state = "BLOCKED"
    elif any("EVIDENCE" in b for b in blockers):
        state = "WAITING_EVIDENCE"
    elif "WAITING_APPROVAL" in blockers:
        state = "WAITING_APPROVAL"
    elif any(t["state"] == "RUNNABLE" and not _gate(plan,t) and any(h["task_id"] == t["task_id"] for h in plan["handoffs"]) for t in plan["tasks"]):
        state = "READY_FOR_GUARDED_HANDOFF"
    else:
        state = "PREPARED"
    plan["mission_state"] = state


def prepare_taskgraph(request, *, ecosystem=None, task_specs=None, constraints=(),
                      access=None, feature_flags=None, budget=None, prior_plan=None, now=None):
    if not isinstance(request, AionRequest):
        raise TypeError("AionRequest required")
    ecosystem = ecosystem_route(ecosystem or request.sector)
    if not isinstance(access or {},Mapping):
        raise AionTaskgraphError("ACCESS_INVALID")
    request = _normalized_request(request,ecosystem,access)
    specs = _specs(task_specs if task_specs is not None else _defaults(request.user_message,ecosystem),ecosystem)
    graph = dependency_graph(specs)
    constraints = _refs(constraints)
    policy = budget_policy(budget); flags = feature_policy(feature_flags)
    scope = {"owner_id":request.owner_id,"tenant_id":request.tenant_id,
             "workspace_id":request.workspace_id,"ecosystem":ecosystem}
    scope_digest = _digest(scope)
    identity = {"request_id":request.request_id,"conversation_id":request.conversation_id,
                "scope":scope,"objective":request.user_message,"action":request.requested_action,
                "attachments":list(request.attachments),"evidence":list(request.evidence),
                "constraints":constraints,"task_specs":specs,"budget":policy,"feature_flags":flags,
                "access_role":request.authorization_context["role"]}
    intent_digest = _digest(identity)
    if prior_plan is not None:
        validate_taskgraph(prior_plan)
        if prior_plan["scope"]!=scope:
            raise AionTaskgraphError("CROSS_ECOSYSTEM_OR_TENANT_REPLAY")
        if prior_plan["intent_digest"]!=intent_digest:
            raise AionTaskgraphError("REQUEST_PAYLOAD_MISMATCH")
        return deepcopy(prior_plan)
    # Compose the existing canonical mission once. Client role/system context cannot override it.
    mission = prepare_aion_mission(request,access=access,approved=False,
                                  feature_flags={},system_context={},provider_state="ZERO_COST_LOCAL")
    mission = json.loads(_canonical(mission))
    plan = {"schema":SCHEMA,"mission_id":mission["mission_id"],"request_id":request.request_id,
            "conversation_id":request.conversation_id,"scope":scope,"scope_digest":scope_digest,
            "objective":request.user_message,"constraints":constraints,"intent_digest":intent_digest,
            "request_fingerprint":_request_fingerprint(request),
            "base_mission":mission,"tasks":[],"graph":graph,"feature_flags":flags,"budget":policy,
            "evidence_snapshot":list(request.evidence),
            "available_evidence":sorted({str(row[k]) for row in request.evidence for k in ("ref","id","source","claim") if isinstance(row.get(k),str)}),
            "evidence_required":sorted({ref for row in specs for ref in row["evidence_required"]}),
            "created_at":_stamp(now),"revision":0,"audit":[],"handoffs":[],**INVARIANTS}
    inherited_approval = mission["authorization_class"]=="REQUIRES_APPROVAL" or bool(mission["approval_requirements"])
    for spec in specs:
        task_id = "AION-TSK-"+hashlib.sha256((mission["mission_id"]+"|"+ecosystem+"|"+spec["key"]).encode()).hexdigest()[:24].upper()
        required = bool(spec["feature_flag"]) or spec["estimated_cost"]>0 or inherited_approval
        plan["tasks"].append({**spec,"task_id":task_id,"payload_digest":_digest(spec["payload"]),
            "scope_digest":scope_digest,"state":"PLANNED","revision":0,"blockers":[],
            "approval_class":"REQUIRES_APPROVAL" if required else "READ_ONLY",
            "approval_required":required,"approved":False,"approval_digest":"","approved_scope":{},
            "output":None,**INVARIANTS})
    _refresh_mission(plan)
    return _seal(plan)


def validate_taskgraph(plan):
    if not isinstance(plan, Mapping) or plan.get("schema")!=SCHEMA:
        raise AionTaskgraphError("PLAN_SCHEMA_INVALID")
    try:
        if len(_canonical(plan).encode())>MAX_DOCUMENT_BYTES:
            raise AionTaskgraphError("DOCUMENT_BOUND")
        if plan.get("plan_digest")!=_digest({k:v for k,v in plan.items() if k!="plan_digest"}):
            raise AionTaskgraphError("PLAN_DIGEST_MISMATCH")
        if any(plan.get(k) is not v for k,v in INVARIANTS.items()):
            raise AionTaskgraphError("EXECUTION_CLAIM_FORBIDDEN")
        if validate_aion_mission(plan["base_mission"]).get("valid") is not True:
            raise AionTaskgraphError("BASE_MISSION_INVALID")
        if any(plan["base_mission"].get(k) is not False for k in ("external_action_executed","execution_allowed","executes_provider_call","executes_billing","real_orders_enabled")):
            raise AionTaskgraphError("BASE_EXECUTION_CLAIM_FORBIDDEN")
        scope = plan["scope"]
        ecosystem = ecosystem_route(scope["ecosystem"])
        if plan["scope_digest"]!=_digest(scope) or scope.get("ecosystem")!=ecosystem:
            raise AionTaskgraphError("SCOPE_DIGEST_MISMATCH")
        if {k:scope[k] for k in ("owner_id","tenant_id","workspace_id")}!=plan["base_mission"]["scope"]:
            raise AionTaskgraphError("SCOPE_MISMATCH")
        if plan["mission_id"]!=plan["base_mission"]["mission_id"] or plan["request_id"]!=plan["base_mission"]["request_id"]:
            raise AionTaskgraphError("MISSION_ID_MISMATCH")
        if not 1 <= len(plan["tasks"]) <= MAX_TASKS or len(plan["audit"])>MAX_AUDIT or len(plan["handoffs"])>MAX_TASKS:
            raise AionTaskgraphError("COLLECTION_BOUND")
        if plan["graph"]!=dependency_graph(plan["tasks"]):
            raise AionTaskgraphError("GRAPH_MISMATCH")
        if plan["feature_flags"]!=feature_policy(plan["feature_flags"]) or plan["budget"]!=budget_policy(plan["budget"]):
            raise AionTaskgraphError("POLICY_INVALID")
        if plan["mission_state"] not in ("PREPARED","WAITING_EVIDENCE","WAITING_APPROVAL","BLOCKED","READY_FOR_GUARDED_HANDOFF"):
            raise AionTaskgraphError("MISSION_STATE_INVALID")
        _validate_stamp(plan["created_at"])
        if type(plan["revision"]) is not int or plan["revision"] != len(plan["audit"]):
            raise AionTaskgraphError("AUDIT_REVISION_INVALID")
        _refs(plan["constraints"])
        _refs(plan["evidence_required"])
        for field in ("owner_id", "tenant_id", "workspace_id"):
            _text(scope[field])
        if len(plan["evidence_snapshot"]) > MAX_REFS:
            raise AionTaskgraphError("EVIDENCE_BOUND")
        for raw in plan["evidence_snapshot"]:
            _bounded(raw)
            if ecosystem_route(raw["ecosystem"]) != ecosystem or any(raw[k] != scope[k] for k in ("owner_id", "tenant_id", "workspace_id")):
                raise AionTaskgraphError("EVIDENCE_SCOPE_MISMATCH")
        for task in plan["tasks"]:
            normalized = _specs([task],ecosystem)[0]
            if any(task[k] != v for k,v in normalized.items()):
                raise AionTaskgraphError("TASK_SPEC_NONCANONICAL")
            if type(task["revision"]) is not int or task["revision"] < 0:
                raise AionTaskgraphError("TASK_REVISION_INVALID")
            if task["output"] is not None and len(_canonical(_bounded(task["output"])).encode()) > MAX_PAYLOAD_BYTES:
                raise AionTaskgraphError("OUTPUT_BOUND")
            route = route_task_role(task["capability"],ecosystem)
            if task["role"]!=route["role"] or task["feature_flag"]!=route["feature_flag"] or task["risk"]!=route["risk"]:
                raise AionTaskgraphError("ROLE_OR_POLICY_FORGED")
            expected_id = "AION-TSK-"+hashlib.sha256((plan["mission_id"]+"|"+ecosystem+"|"+task["key"]).encode()).hexdigest()[:24].upper()
            if task["task_id"]!=expected_id or task["scope_digest"]!=plan["scope_digest"] or task["payload_digest"]!=_digest(task["payload"]):
                raise AionTaskgraphError("TASK_ID_OR_PAYLOAD_MISMATCH")
            if task["state"] not in TASK_STATES or any(task.get(k) is not v for k,v in INVARIANTS.items()):
                raise AionTaskgraphError("TASK_STATE_OR_EXECUTION_INVALID")
            if task["state"]=="COMPLETED" and task["feature_flag"]:
                raise AionTaskgraphError("EXTERNAL_COMPLETION_FORBIDDEN")
            required = bool(task["feature_flag"]) or task["estimated_cost"]>0 or plan["base_mission"]["authorization_class"]=="REQUIRES_APPROVAL" or bool(plan["base_mission"]["approval_requirements"])
            if task["approval_required"] is not required or task["approval_class"]!=("REQUIRES_APPROVAL" if required else "READ_ONLY"):
                raise AionTaskgraphError("APPROVAL_POLICY_FORGED")
            if task["approved"] is not False and not _approval_valid(plan,task):
                raise AionTaskgraphError("APPROVAL_BINDING_MISMATCH")
            if task["approved"] is False and (task["approval_digest"] or task["approved_scope"]):
                raise AionTaskgraphError("UNAPPROVED_RECEIPT_FORGED")
            if task["state"] == "COMPLETED" and task["output"] is None:
                raise AionTaskgraphError("LOCAL_OUTPUT_REQUIRED")
        if len({t["task_id"] for t in plan["tasks"]})!=len(plan["tasks"]):
            raise AionTaskgraphError("DUPLICATE_TASK")
        _validate_history(plan)
        if plan["mission_state"] == "READY_FOR_GUARDED_HANDOFF" and not any(t["state"] == "RUNNABLE" and any(h["task_id"] == t["task_id"] for h in plan["handoffs"]) for t in plan["tasks"]):
            raise AionTaskgraphError("READY_WITHOUT_ACTIVE_HANDOFF")
    except (KeyError,TypeError,ValueError,OverflowError,RecursionError) as exc:
        if isinstance(exc,AionTaskgraphError): raise
        raise AionTaskgraphError("PLAN_MALFORMED") from None
    return {"valid":True,"external_action_executed":False,"execution_allowed":False}


def _validate_history(plan):
    tasks = {t["task_id"]:t for t in plan["tasks"]}
    states = {key:"PLANNED" for key in tasks}
    revisions = {key:0 for key in tasks}
    approvals = {key:"" for key in tasks}
    prepared = set()
    for sequence,row in enumerate(plan["audit"],1):
        _validate_stamp(row["created_at"])
        task = tasks[row["task_id"]]
        key = task["task_id"]
        if row["sequence"] != sequence or row["previous_state"] != states[key] or row["role"] != task["role"] or row["scope_digest"] != plan["scope_digest"] or row["payload_digest"] != task["payload_digest"] or any(row.get(k) is not v for k,v in INVARIANTS.items()):
            raise AionTaskgraphError("AUDIT_BINDING_INVALID")
        if row["action"] == "TASK_TRANSITION":
            if row["state"] not in TRANSITIONS[states[key]]:
                raise AionTaskgraphError("AUDIT_TRANSITION_INVALID")
            states[key] = row["state"]
        elif row["action"] == "APPROVAL_BOUND":
            approvals[key] = _digest(_approval_binding(plan,task))
            if row["state"] != states[key]:
                raise AionTaskgraphError("APPROVAL_CHANGED_STATE")
        elif row["action"] == "GUARDED_HANDOFF_PREPARED":
            if states[key] != "RUNNABLE" or row["state"] != states[key] or key in prepared:
                raise AionTaskgraphError("HANDOFF_HISTORY_INVALID")
            prepared.add(key)
        else:
            raise AionTaskgraphError("AUDIT_ACTION_INVALID")
        if row["approval_digest"] != approvals[key]:
            raise AionTaskgraphError("AUDIT_APPROVAL_INVALID")
        revisions[key] += 1
    for key,task in tasks.items():
        if task["state"] != states[key] or task["revision"] != revisions[key] or task["approval_digest"] != approvals[key]:
            raise AionTaskgraphError("TASK_HISTORY_MISMATCH")
    seen = set()
    for handoff in plan["handoffs"]:
        _validate_stamp(handoff["created_at"])
        task = tasks[handoff["task_id"]]
        key = task["task_id"]
        logical = _digest({"mission_id":plan["mission_id"],"task_id":key,"payload_digest":task["payload_digest"],"scope_digest":plan["scope_digest"]})
        expected = {"mission_id":plan["mission_id"],"capability":task["capability"],"role":task["role"],"payload_digest":task["payload_digest"],"scope_digest":plan["scope_digest"],"idempotency_key":logical,
            "approval_state":"APPROVED_BOUND" if task["approval_required"] else "NOT_REQUIRED",
            "budget_state":plan["budget"]["mode"],"risk_state":"SYSTEM_POLICY_CHECKED_PLAN_ONLY",
            "evidence_state":"SCOPED_CONFIRMED","requires_downstream_execution_gate":True,**INVARIANTS}
        if key in seen or key not in prepared or any(handoff.get(k) != v or (type(v) is bool and handoff.get(k) is not v) for k,v in expected.items()):
            raise AionTaskgraphError("HANDOFF_BINDING_INVALID")
        seen.add(key)
    if seen != prepared:
        raise AionTaskgraphError("HANDOFF_HISTORY_INVALID")


def _validate_stamp(value):
    try:
        parsed = datetime.fromisoformat(_text(value,80))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
    except (ValueError,TypeError):
        raise AionTaskgraphError("TIMESTAMP_INVALID") from None


def _mutable(plan, task_id, expected_revision):
    validate_taskgraph(plan)
    if type(expected_revision) is not int or expected_revision!=plan["revision"]:
        raise AionTaskgraphError("REVISION_CONFLICT")
    current = deepcopy(plan)
    for task in current["tasks"]:
        if task["task_id"]==task_id:
            return current,task
    raise AionTaskgraphError("TASK_NOT_FOUND")


def _record(plan, task, action, previous, now):
    if len(plan["audit"])>=MAX_AUDIT:
        raise AionTaskgraphError("AUDIT_CAPACITY")
    plan["revision"] += 1;task["revision"] += 1
    plan["audit"].append({"sequence":plan["revision"],"task_id":task["task_id"],"role":task["role"],
        "action":action,"previous_state":previous,"state":task["state"],"scope_digest":plan["scope_digest"],
        "payload_digest":task["payload_digest"],"approval_digest":task["approval_digest"],"created_at":_stamp(now),**INVARIANTS})
    _refresh_mission(plan)
    return _seal(plan)


def approve_task(plan, task_id, *, approved=False, approved_scope=None, expected_revision, now=None):
    validate_taskgraph(plan)
    if approved is not True:
        raise AionTaskgraphError("EXACT_APPROVAL_REQUIRED")
    if approved_scope!=plan["scope"]:
        raise AionTaskgraphError("APPROVED_SCOPE_MISMATCH")
    task = next((row for row in plan["tasks"] if row["task_id"]==task_id),None)
    if task is None:
        raise AionTaskgraphError("TASK_NOT_FOUND")
    if task["state"] in {"COMPLETED","FAILED","CANCELLED","SUPERSEDED"}:
        raise AionTaskgraphError("TERMINAL_TASK_APPROVAL")
    # A committed approval may be retried after the caller lost the response.
    # Recognize the already-bound receipt before CAS; this path is read-only.
    if _approval_valid(plan,task):
        return deepcopy(plan)
    current,task = _mutable(plan,task_id,expected_revision)
    task.update(approved=True,approved_scope=deepcopy(approved_scope),
                approval_digest=_digest(_approval_binding(current,task)))
    return _record(current,task,"APPROVAL_BOUND",task["state"],now)


def transition_task(plan, task_id, target, *, expected_revision, output=None, reason="", now=None):
    current,task = _mutable(plan,task_id,expected_revision)
    previous = task["state"]
    if target not in TASK_STATES or target not in TRANSITIONS[previous]:
        raise AionTaskgraphError("INVALID_TRANSITION")
    if previous in {"BLOCKED","FAILED"} and target=="QUEUED" and not _text(reason,300,empty=True):
        raise AionTaskgraphError("RECOVERY_REASON_REQUIRED")
    gates = _gate(current,task,now)
    if target == "WAITING_APPROVAL" and "WAITING_APPROVAL" not in gates:
        raise AionTaskgraphError("APPROVAL_WAIT_WITHOUT_GATE")
    if target == "WAITING_DEPENDENCY" and not any(b.startswith("WAITING_DEPENDENCY:") for b in gates):
        raise AionTaskgraphError("DEPENDENCY_WAIT_WITHOUT_GATE")
    if target in {"RUNNABLE","COMPLETED"} and gates:
        raise AionTaskgraphError("TASK_GATES_NOT_SATISFIED")
    if target=="COMPLETED":
        if task["feature_flag"]:
            raise AionTaskgraphError("EXTERNAL_COMPLETION_FORBIDDEN")
        if output is None:
            raise AionTaskgraphError("LOCAL_OUTPUT_REQUIRED")
        result = _bounded(output)
        if len(_canonical(result).encode())>MAX_PAYLOAD_BYTES:
            raise AionTaskgraphError("OUTPUT_BOUND")
        task["output"] = result
    if target in {"BLOCKED","FAILED"} and not _text(reason,300,empty=True):
        raise AionTaskgraphError("BLOCKER_REASON_REQUIRED")
    task["state"] = target
    task["blockers"] = [_text(reason,300)] if target in {"BLOCKED","FAILED"} else gates[:32]
    return _record(current,task,"TASK_TRANSITION",previous,now)


def prepare_guarded_task_handoff(plan, task_id, *, expected_revision, now=None):
    validate_taskgraph(plan)
    task = next((row for row in plan["tasks"] if row["task_id"]==task_id),None)
    if task is None:
        raise AionTaskgraphError("TASK_NOT_FOUND")
    if task["state"]!="RUNNABLE" or _gate(plan,task,now):
        raise AionTaskgraphError("HANDOFF_GATES_NOT_SATISFIED")
    logical_key = _digest({"mission_id":plan["mission_id"],"task_id":task["task_id"],
                           "payload_digest":task["payload_digest"],"scope_digest":plan["scope_digest"]})
    prior = next((h for h in plan["handoffs"] if h["task_id"]==task_id),None)
    if prior:
        if prior["idempotency_key"]!=logical_key:
            raise AionTaskgraphError("HANDOFF_PAYLOAD_MISMATCH")
        # Same committed handoff + same live gates is a safe replay even when
        # the caller retries with the pre-commit expected revision.
        return {"plan":deepcopy(plan),"handoff":deepcopy(prior),"replay":True,**INVARIANTS}
    current,task = _mutable(plan,task_id,expected_revision)
    handoff = {"mission_id":current["mission_id"],"task_id":task_id,"capability":task["capability"],
        "role":task["role"],"payload_digest":task["payload_digest"],"scope_digest":current["scope_digest"],
        "approval_state":"APPROVED_BOUND" if task["approval_required"] else "NOT_REQUIRED",
        "budget_state":current["budget"]["mode"],"risk_state":"SYSTEM_POLICY_CHECKED_PLAN_ONLY",
        "evidence_state":"SCOPED_CONFIRMED","created_at":_stamp(now),"idempotency_key":logical_key,
        "requires_downstream_execution_gate":True,**INVARIANTS}
    current["handoffs"].append(handoff)
    _record(current,task,"GUARDED_HANDOFF_PREPARED",task["state"],now)
    return {"plan":current,"handoff":handoff,"replay":False,**INVARIANTS}


def export_taskgraph(plan):
    validate_taskgraph(plan)
    return _canonical(plan)


def recover_taskgraph(serialized, request, *, ecosystem, expected_digest, access=None):
    if not isinstance(serialized,str) or len(serialized.encode())>MAX_DOCUMENT_BYTES:
        raise AionTaskgraphError("RECOVERY_BOUND")
    def pairs(values):
        result = {}
        for k,v in values:
            if k in result: raise AionTaskgraphError("DUPLICATE_JSON_KEY")
            result[k] = v
        return result
    try:
        plan = json.loads(serialized,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(AionTaskgraphError("INVALID_NUMBER")))
    except (ValueError,RecursionError) as exc:
        if isinstance(exc,AionTaskgraphError):raise
        raise AionTaskgraphError("RECOVERY_MALFORMED") from None
    validate_taskgraph(plan)
    if plan["plan_digest"]!=expected_digest:
        raise AionTaskgraphError("RECOVERY_DIGEST_MISMATCH")
    code = ecosystem_route(ecosystem)
    normalized = _normalized_request(request,code,access)
    scope = {"owner_id":normalized.owner_id,"tenant_id":normalized.tenant_id,
             "workspace_id":normalized.workspace_id,"ecosystem":code}
    if plan["scope"]!=scope or plan["request_id"]!=normalized.request_id or plan["conversation_id"]!=normalized.conversation_id or plan["objective"]!=normalized.user_message:
        raise AionTaskgraphError("RECOVERY_SCOPE_OR_REQUEST_MISMATCH")
    if plan["request_fingerprint"] != _request_fingerprint(normalized):
        raise AionTaskgraphError("RECOVERY_REQUEST_CHANGED")
    # No refresh, queue, RUNNABLE conversion, execution, approval or memory promotion.
    return deepcopy(plan)


def _request_fingerprint(request):
    return _digest({"request_id":request.request_id,"conversation_id":request.conversation_id,
        "objective":request.user_message,"action":request.requested_action,
        "attachments":list(request.attachments),"evidence":list(request.evidence),
        "mode":request.current_mode,"role":request.authorization_context["role"]})
