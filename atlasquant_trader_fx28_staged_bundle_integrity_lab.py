"""Read-only staged FX28 Motor A bundle integrity audit (DRAFT LAB ONLY).

Pins FOUR coordinated staged modules, SIX legacy support modules and two
untouched scheduled executables to exact AM12-observed SHA256 bytes.
This is NOT a rollout tool, not a source of macro predictions, and not
permission to modify the frozen preflight or first-M15 collector.
Only local source bytes are read. No import side effects or deployment.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from typing import Any,Mapping
import json

SCHEMA="ATLASQUANT_FX28_MOTOR_A_STAGED_MIGRATION_INTEGRITY_LAB_V1"
STAGE_PINS={
    "atlasquant_trader_fx28_single_readiness_panel_lab.py":"dbf8d0226a04c15008b11d434acbd4347c44949b0877f97a5868d0a0f4252bac",
    "atlasquant_trader_fx28_policy_local_archive_replay_lab.py":"e45e972ec4d1a3336953de60cd389e467c8cc43df92189809f608085434c6f8c",
    "atlasquant_trader_fx28_eight_policy_raw_source_join_lab.py":"d440310a47b054c0b76a9d7f261b18067a32e87ebb8042e5bb19b981cca170f2",
    "atlasquant_trader_nzd_rbnz_policy_source_variant_lab.py":"deadbda2306e6d408026ea3b467b9ee520305dd57c36b6ebeecd5d79544532c9",
}
LEGACY_PINS={
    "atlasquant_trader_fx28_single_readiness_panel_lab.py":"8b497b4cab6b3f2313510db63fba6313a925088c8a3737c77daa9ca319426684",
    "atlasquant_trader_fx28_policy_local_archive_replay_lab.py":"d3a87fc8d64d5a000cff13e787a159f24286bbf6bd582547f042860f6c31d647",
    "atlasquant_trader_fx28_eight_policy_raw_source_join_lab.py":"1f45fa7fe227a2e94255a5cce815e07333fd487bf07115b8ccb65070954063dc",
    "atlasquant_trader_fx28_32_factor_source_admission_lab.py":"ad26bec3ac75de27437505bbfc807e0ec661b029250c4e43e806a3ae81247c2f",
    "atlasquant_trader_fx28_policy_ppi_unified_readiness_lab.py":"6bace2df26c1228b003c8c0a01ba8830b126e27d7c240624f495267699b1eb93",
    "atlasquant_trader_fx28_ny17_672_slot_issuance_ledger_lab.py":"9533af586ef524acee91f27fdbc50e6d512704699b655ba01623d7cfe6375929",
}
WRAPPER_SHA="c0be94bb03a1b5e41e444442caebe95e43788e5b4c8e43e43554885b8cce00d2"
COLLECTOR_SHA="9b2d1eaf1d5bc7075bc7924f0676052f1878113288deaf1dd88b58ae4e8c9af9"
_WIRING=(
    ("atlasquant_trader_fx28_single_readiness_panel_lab.py",
     "from atlasquant_trader_fx28_policy_local_archive_replay_lab import"),
    ("atlasquant_trader_fx28_policy_local_archive_replay_lab.py",
     "from atlasquant_trader_fx28_eight_policy_raw_source_join_lab import"),
    ("atlasquant_trader_fx28_eight_policy_raw_source_join_lab.py",
     "from atlasquant_trader_nzd_rbnz_policy_source_variant_lab import"),
)

def _base(reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "state":"LAB_FX28_STAGED_MIGRATION_INTEGRITY_BLOCKED_NO_GO",
        "reason":reason,
        "total_files_required":12,
        "total_files_matched":0,
        "staged_modules_checked":[],
        "legacy_dependencies_checked":[],
        "file_mismatches":[],
        "all_stage_files_match_pinned_versions":False,
        "all_legacy_dependencies_match_pinned_versions":False,
        "scheduled_wrapper_byte_hash_unchanged":False,
        "scheduled_m15_collector_byte_hash_unchanged":False,
        "four_module_import_wiring_matches":False,
        "staged_mode_is_not_scheduled_runner":True,
        "explicit_rollout_or_merge_approved":False,
        "production_or_scheduled_files_modified_by_this_gate":False,
        "safe_to_change_automations":False,
        "deployed_to_main":False,
        "frozen_campaign_slots":672,
        "validated_directional_accuracy":None,
        "calibrated_fx_probability":None,
        "operational_bias":"AGUARDAR",
        "trade_authorized":False,
        "http_requests":0,"mt5_calls":0,"file_writes":0,
    }

def _safe(path:Any)->bool:
    if not isinstance(path,Path) or not path.is_absolute():
        return False
    try:
        return not any(item.is_symlink() for item in (path,*path.parents))
    except (OSError,RuntimeError,ValueError,TypeError):
        return False

def _read_exact(file:Path, expected_sha:str)->tuple[bool,str,bytes|None]:
    if not _safe(file) or not isinstance(expected_sha,str) or len(expected_sha)!=64:
        return False,"UNSAFE_FILE_OR_PIN",None
    try:
        if not file.is_file() or file.stat().st_size not in range(1,200001):
            return False,"MISSING_NOT_FILE_OR_SIZE_INVALID",None
        data=file.read_bytes()
        if sha256(data).hexdigest()!=expected_sha:
            return False,"SHA256_NOT_MATCHING_FROZEN_BUNDLE",None
        return True,"PIN_VERIFIED",data
    except (OSError,RuntimeError,ValueError,TypeError):
        return False,"FILE_READ_FAILED",None

def _evaluate(*,stage_dir:Any,legacy_dir:Any,
              scheduled_wrapper_path:Any,scheduled_collector_path:Any,
              stage_pins:Mapping[str,str],
              legacy_pins:Mapping[str,str],
              wrapper_sha:str,collector_sha:str)->dict[str,Any]:
    out=_base("INVALID_OR_UNSAFE_INPUT_ROOT")
    if (not all(_safe(p) for p in (
            stage_dir,legacy_dir,scheduled_wrapper_path,scheduled_collector_path))
            or stage_dir==legacy_dir
            or scheduled_wrapper_path.parent in (stage_dir,legacy_dir)
            or scheduled_collector_path.parent in (stage_dir,legacy_dir)):
        return out
    if (set(stage_pins)!=set(STAGE_PINS)
            or set(legacy_pins)!=set(LEGACY_PINS)):
        out["reason"]="FOUR_MODULE_OR_SIX_LEGACY_MODULE_MANIFEST_DRIFT"
        return out
    if not stage_dir.is_dir() or not legacy_dir.is_dir():
        out["reason"]="STAGE_OR_LEGACY_DIRECTORY_NOT_FOUND"
        return out
    matching={}
    failed=[]
    for role,base,pins in (("stage",stage_dir,stage_pins),
                            ("legacy",legacy_dir,legacy_pins)):
        for filename,expected in pins.items():
            success,why,payload=_read_exact(base/filename,expected)
            matching[(role,filename)]=payload
            if success:
                out["total_files_matched"]+=1
                out["staged_modules_checked" if role=="stage"
                    else "legacy_dependencies_checked"].append(filename)
            else:
                failed.append({"role":role,"filename":filename,"reason":why})
    for role,path,pin in (
        ("scheduled_wrapper",scheduled_wrapper_path,wrapper_sha),
        ("scheduled_collector",scheduled_collector_path,collector_sha)
    ):
        success,why,payload=_read_exact(path,pin)
        if success:
            out["total_files_matched"]+=1
            out["scheduled_wrapper_byte_hash_unchanged"
                if role=="scheduled_wrapper"
                else "scheduled_m15_collector_byte_hash_unchanged"]=True
        else:
            failed.append({"role":role,"filename":path.name,"reason":why})
        matching[(role,path.name)]=payload
    out["file_mismatches"]=failed
    out["all_stage_files_match_pinned_versions"]=len(out["staged_modules_checked"])==4
    out["all_legacy_dependencies_match_pinned_versions"]=len(out["legacy_dependencies_checked"])==6
    if failed:
        out["reason"]="PINNED_FILE_MISSING_TAMPERED_OR_CHANGED_NO_ROLLOUT"
        return out
    if any(STAGE_PINS.get(name) == LEGACY_PINS.get(name)
           for name in set(STAGE_PINS) & set(LEGACY_PINS)):
        out["reason"]="STAGED_DIFF_NOT_IN_MANIFEST_NO_ROLLOUT"
        return out
    try:
        wiring=all(marker.encode("utf-8") in matching[("stage",name)]
                   for name,marker in _WIRING)
        wrapper=matching[("scheduled_wrapper",scheduled_wrapper_path.name)]
        old_anchor=(b"FX28_Single_Readiness_20261114" in wrapper
                    and b"NZD_Policy_Variant_Staged_20261115" not in wrapper)
    except (TypeError,ValueError,KeyError):
        return _base("MODULE_IMPORT_WIRING_OR_WRAPPER_NOT_ATTESTABLE")
    out["four_module_import_wiring_matches"]=wiring
    if not wiring or not old_anchor:
        out["reason"]="STAGE_IMPORT_GRAPH_OR_FROZEN_WRAPPER_CHANGED"
        return out
    out["state"]="LAB_FX28_STAGED_MIGRATION_BUNDLE_BYTES_VERIFIED_NOT_DEPLOYED_NO_GO"
    out["reason"]="STAGE_LEGACY_AND_SCHEDULED_BYTES_MATCH_PINNED_LAB_V1"
    return out

def inspect_fx28_staged_migration_bundle_lab(
        *,stage_dir:Any,legacy_dir:Any,
        scheduled_wrapper_path:Any,scheduled_collector_path:Any)->dict[str,Any]:
    """Read only: a green report explicitly does NOT authorize deployment."""
    return _evaluate(
        stage_dir=stage_dir,legacy_dir=legacy_dir,
        scheduled_wrapper_path=scheduled_wrapper_path,
        scheduled_collector_path=scheduled_collector_path,
        stage_pins=STAGE_PINS,legacy_pins=LEGACY_PINS,
        wrapper_sha=WRAPPER_SHA,collector_sha=COLLECTOR_SHA
    )

__all__=("SCHEMA","inspect_fx28_staged_migration_bundle_lab")
