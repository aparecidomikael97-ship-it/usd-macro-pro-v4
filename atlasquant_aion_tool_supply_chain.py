"""Closed AION tool supply-chain registry.

The Tool Hub remains the runtime catalog. This module pins the authority-relevant
contract for every tool currently approved to exist in that catalog. Runtime
injection of a new tool does not make it approved: a tool id must be reviewed
into DEFAULT_TOOL_CONTRACTS and its contract hash pin must be updated explicitly.

Hashes are integrity fingerprints, not signatures.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

SCHEMA = "ATLASQUANT_AION_TOOL_SUPPLY_CHAIN_V1"
REGISTRY_VERSION = "1.0.0"
PINNED_REGISTRY_DIGEST = "16c52804014523b126d4ed30377bc86002fe7211d22a2ff8cea3a7c523766486"
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$")
_SAFE_OWNER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,95}$")

_EMPTY_INPUT = {
    "type": "object",
    "additionalProperties": False,
    "properties": {},
}

DEFAULT_TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "aion.memory.search": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"query": {"type": "string", "maxLength": 500}},
        },
        "output_schema": {
            "type": "object",
            "required": ["canonical", "canonical_count"],
        },
        "implementation_ref": "atlasquant_aion_local_executor._memory_search",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.memory.recall": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "persona": {"type": "string"},
                "domain": {"type": "string"},
                "include_expired": {"type": "boolean"},
                "include_superseded": {"type": "boolean"},
            },
        },
        "output_schema": {
            "type": "object",
            "required": ["layered", "layered_count"],
        },
        "implementation_ref": "atlasquant_aion_local_executor._memory_recall",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.checkpoint.inspect": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": _EMPTY_INPUT,
        "output_schema": {
            "type": "object",
            "required": ["integrity", "counts"],
        },
        "implementation_ref": "atlasquant_aion_local_executor._checkpoint_inspect",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.status.read": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": _EMPTY_INPUT,
        "output_schema": {"type": "object"},
        "implementation_ref": "atlasquant_aion_local_executor._status_read",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.tasks.summary": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": {
            "type": "object",
            "additionalProperties": True,
            "properties": {"tasks": {"type": "array"}},
        },
        "output_schema": {"type": "object"},
        "implementation_ref": "atlasquant_aion_local_executor._tasks",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.missions.summary": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": {
            "type": "object",
            "additionalProperties": True,
            "properties": {"missions": {"type": "array"}},
        },
        "output_schema": {"type": "object"},
        "implementation_ref": "atlasquant_aion_local_executor._missions",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.durable.summary": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "durable_tasks": {"type": ["array", "object"]},
            },
        },
        "output_schema": {"type": "object"},
        "implementation_ref": "atlasquant_aion_local_executor._durable",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.approvals.summary": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": _EMPTY_INPUT,
        "output_schema": {"type": "object"},
        "implementation_ref": "atlasquant_aion_local_executor._approvals",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.events.summary": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": _EMPTY_INPUT,
        "output_schema": {"type": "object"},
        "implementation_ref": "atlasquant_aion_local_executor._events_summary",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.specialists.snapshot": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": {
            "type": "object",
            "additionalProperties": True,
            "properties": {"specialist": {"type": "string"}},
        },
        "output_schema": {"type": "object"},
        "implementation_ref": "atlasquant_aion_local_executor._specialists",
        "eval_profile": "local-read-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.secretary.draft_brief": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": _EMPTY_INPUT,
        "output_schema": {"type": "object"},
        "implementation_ref": "atlasquant_aion_local_executor._secretary",
        "eval_profile": "local-draft-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
    "aion.staging.credential_probe": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        "output_schema": {"type": "object"},
        "implementation_ref": "external-adapter:credential_probe",
        "eval_profile": "staging-egress-v1",
        "credential_ref": "staging-probe-secret",
        "credential_scopes": ["probe:read"],
        "sandbox_profile": "THIRD_PARTY_EGRESS_PROXY",
        "egress_allowlist": ["api.example.com"],
        "third_party": True,
    },
    "aion.checkpoint.prepare_save": {
        "owner": "atlasquant-core",
        "version": "1.0.0",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "implementation_ref": "planner-only:aion.checkpoint.prepare_save",
        "eval_profile": "local-write-plan-v1",
        "credential_ref": "",
        "credential_scopes": [],
        "sandbox_profile": "LOCAL_NO_EGRESS",
        "egress_allowlist": [],
        "third_party": False,
    },
}

PINNED_CONTRACT_HASHES = {
    "aion.approvals.summary": "7a2f296ec1eda616de00e5dce505a06eb9e1cb475147305f55ffd1c31d843bd6",
    "aion.checkpoint.inspect": "07243ff50146649ede280a1355029c79b2809ad4d4f6334622aa31506d09e985",
    "aion.checkpoint.prepare_save": "5c9878baab8711c9cf8f53c9a21e0ff451a28e3ee955e7768812c34e2894e792",
    "aion.durable.summary": "eeb64ff1e8e31a7020b2ed356628074d4ca3059ce2bd3a691f438965b00798ac",
    "aion.events.summary": "9d7df5d50a7c76041dbfd865066fa538913188a963bba08e5afc5e4b64d98b13",
    "aion.memory.recall": "673814d0f1b0f4312c576b228abd447d99fba903c5928dc16663634a71794649",
    "aion.memory.search": "0f948a49c705c364c90059da4a8b7115d613ad4a073fcbbd6f4bdf6595134b32",
    "aion.missions.summary": "0c4c2947351fca249cc645cd86e3546d3dcd0d1b48dbba289e28a762ea41c9ea",
    "aion.secretary.draft_brief": "363583c938e604aa000b68469f7b4dedd4e8eed76e00ff7c14490858a6a6209e",
    "aion.specialists.snapshot": "91fe1a51b20f4a91259e201cf8f215d1421e9d79c8061c94d6d590848da752e6",
    "aion.staging.credential_probe": "d2bb6b021017e1e6c66390fb289754b55ec4525f37b4ed0af96de1e660dc53d3",
    "aion.status.read": "5dd059893bdb5db407d215e1451bfde15fa454685a3fc4b37d1ed37291603446",
    "aion.tasks.summary": "1df074cb57d79ffd4da62c5e33181f563332c571103aec2a23527a2c1f6279e4",
}

_CONTRACT_FIELDS = (
    "owner",
    "version",
    "input_schema",
    "output_schema",
    "implementation_ref",
    "eval_profile",
    "credential_ref",
    "credential_scopes",
    "sandbox_profile",
    "egress_allowlist",
    "third_party",
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for raw in value[:100]:
        text = str(raw or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def schema_hash(tool: Mapping[str, Any]) -> str:
    return _sha({
        "input_schema": tool.get("input_schema") or {},
        "output_schema": tool.get("output_schema") or {},
    })


def contract_payload(tool: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "tool_id": str(tool.get("tool_id") or ""),
        "workspace_id": str(tool.get("workspace_id") or ""),
        "connector_id": str(tool.get("connector_id") or ""),
        "kind": str(tool.get("kind") or ""),
        "guardian_action": str(tool.get("guardian_action") or ""),
        "required_scopes": sorted(_list(tool.get("required_scopes"))),
        "external_side_effects": tool.get("external_side_effects") is True,
        "owner": str(tool.get("owner") or ""),
        "version": str(tool.get("version") or ""),
        "input_schema": tool.get("input_schema") or {},
        "output_schema": tool.get("output_schema") or {},
        "implementation_ref": str(tool.get("implementation_ref") or ""),
        "eval_profile": str(tool.get("eval_profile") or ""),
        "credential_ref": str(tool.get("credential_ref") or ""),
        "credential_scopes": sorted(_list(tool.get("credential_scopes"))),
        "sandbox_profile": str(tool.get("sandbox_profile") or ""),
        "egress_allowlist": sorted(_list(tool.get("egress_allowlist"))),
        "third_party": tool.get("third_party") is True,
    }


def contract_hash(tool: Mapping[str, Any]) -> str:
    return _sha(contract_payload(tool))


def _metadata_for(tool_id: str, incoming: Mapping[str, Any]) -> dict[str, Any]:
    expected = DEFAULT_TOOL_CONTRACTS.get(tool_id)
    if expected is None:
        return {
            key: incoming.get(key)
            for key in _CONTRACT_FIELDS
        }
    out = {}
    for key in _CONTRACT_FIELDS:
        out[key] = incoming[key] if key in incoming else expected[key]
    return out


def tool_contract_issues(tool: Mapping[str, Any]) -> list[str]:
    tool_id = str(tool.get("tool_id") or "")
    if tool_id not in DEFAULT_TOOL_CONTRACTS:
        return ["TOOL_NOT_IN_CLOSED_REGISTRY"]

    issues = []
    owner = str(tool.get("owner") or "")
    version = str(tool.get("version") or "")
    if not _SAFE_OWNER.fullmatch(owner):
        issues.append("TOOL_OWNER_INVALID")
    if not _SEMVER.fullmatch(version):
        issues.append("TOOL_VERSION_UNPINNED")
    if not str(tool.get("eval_profile") or ""):
        issues.append("TOOL_EVAL_PROFILE_MISSING")
    if not isinstance(tool.get("input_schema"), Mapping):
        issues.append("TOOL_INPUT_SCHEMA_INVALID")
    if not isinstance(tool.get("output_schema"), Mapping):
        issues.append("TOOL_OUTPUT_SCHEMA_INVALID")
    if tool.get("sandbox_profile") not in {
        "LOCAL_NO_EGRESS",
        "THIRD_PARTY_EGRESS_PROXY",
    }:
        issues.append("TOOL_SANDBOX_PROFILE_INVALID")

    expected_hash = PINNED_CONTRACT_HASHES.get(tool_id, "")
    actual_hash = contract_hash(tool)
    if actual_hash != expected_hash:
        issues.append("TOOL_CONTRACT_DRIFT")
    declared = str(tool.get("declared_schema_hash") or "")
    actual_schema = schema_hash(tool)
    if declared and declared != actual_schema:
        issues.append("TOOL_DECLARED_SCHEMA_HASH_MISMATCH")
    if str(tool.get("schema_hash") or "") not in {"", actual_schema}:
        issues.append("TOOL_SCHEMA_HASH_TAMPERED")
    return list(dict.fromkeys(issues))


def enrich_tool_contract(
    base_tool: Mapping[str, Any],
    incoming: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = dict(base_tool or {})
    raw = dict(incoming or {})
    tool_id = str(base.get("tool_id") or "")
    base.update(_metadata_for(tool_id, raw))
    base["credential_scopes"] = _list(base.get("credential_scopes"))
    base["egress_allowlist"] = _list(base.get("egress_allowlist"))
    base["schema_hash"] = schema_hash(base)
    base["contract_hash"] = contract_hash(base)
    base["pinned_contract_hash"] = PINNED_CONTRACT_HASHES.get(tool_id, "")
    issues = tool_contract_issues(base)
    base["supply_chain_issues"] = issues
    base["supply_chain_state"] = "VERIFIED" if not issues else "BLOCK"
    base["registry_approved"] = not issues
    base["schema_change_requires_review"] = True
    base["tool_output_is_authority"] = False
    return base


def registry_integrity_report() -> dict[str, Any]:
    manifest = [
        {
            "tool_id": tool_id,
            "schema_hash": schema_hash({
                **DEFAULT_TOOL_CONTRACTS[tool_id],
            }),
            "contract_hash": PINNED_CONTRACT_HASHES.get(tool_id, ""),
        }
        for tool_id in sorted(DEFAULT_TOOL_CONTRACTS)
    ]
    digest = _sha(manifest)
    keys_match = set(DEFAULT_TOOL_CONTRACTS) == set(PINNED_CONTRACT_HASHES)
    return {
        "schema": SCHEMA,
        "registry_version": REGISTRY_VERSION,
        "tool_count": len(manifest),
        "digest": digest,
        "pinned_digest": PINNED_REGISTRY_DIGEST,
        "keys_match": keys_match,
        "state": "VERIFIED"
        if keys_match and digest == PINNED_REGISTRY_DIGEST
        else "BLOCK",
        "requires_code_review_for_change": True,
        "automatic_tool_registration": False,
    }


def registry_digest_for_tools(tools: Sequence[Mapping[str, Any]] | None) -> str:
    rows = []
    for raw in list(tools or [])[:500]:
        if not isinstance(raw, Mapping):
            continue
        rows.append({
            "tool_id": str(raw.get("tool_id") or ""),
            "schema_hash": schema_hash(raw),
            "contract_hash": contract_hash(raw),
            "state": str(raw.get("supply_chain_state") or ""),
        })
    rows.sort(key=lambda item: item["tool_id"])
    return _sha(rows)


__all__ = [
    "SCHEMA",
    "REGISTRY_VERSION",
    "PINNED_REGISTRY_DIGEST",
    "DEFAULT_TOOL_CONTRACTS",
    "PINNED_CONTRACT_HASHES",
    "schema_hash",
    "contract_payload",
    "contract_hash",
    "tool_contract_issues",
    "enrich_tool_contract",
    "registry_integrity_report",
    "registry_digest_for_tools",
]
