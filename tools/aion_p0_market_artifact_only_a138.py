"""A138: offline, artifact-only packaging of two existing public market snapshots.

NO provider fetch; NO writes to repository; NO GitHub write token; NO runtime
restore; NO Global Worker; NO independent trust evidence is produced.

The bundle contains copies of already-versioned market JSON (possibly stale).
The source SHA comes from CI and is NOT a witness, signature or freshness proof.
A file allowlist, strict parser, size caps, symlink rejection and manifest
minimize accidental packaging of AION checkpoint or credentials. They do not
certify all privacy risks in untrusted data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile

SCHEMA="AION_P0_OFFLINE_MARKET_SNAPSHOT_ARTIFACT_V1"
ALLOWLIST=(
    "dados/master_market_map_v102.json",
    "dados/currency_news_current_v107.json",
)
MAX_FILE_BYTES=2_000_000
MAX_TOTAL_BYTES=4_000_000
SENSITIVE_KEYS=frozenset({
    "token","password","api_key","secret","authorization","private_key",
    "client_secret","access_key","github_token_historico","gh_token_app",
})
MANIFEST_NAME="manifest.json"


def _deny_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key in market file.")
        result[key]=value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant: "+str(value))


def _no_secret_keys(value):
    if isinstance(value,dict):
        for key,child in value.items():
            if key.lower() in SENSITIVE_KEYS:
                raise ValueError("Credential-named field cannot be packaged.")
            _no_secret_keys(child)
    elif isinstance(value,list):
        for child in value:
            _no_secret_keys(child)


def _strict_load(payload:bytes):
    try:
        text=payload.decode("utf-8")
        obj=json.loads(
            text,
            object_pairs_hook=_deny_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError("Invalid public market JSON.") from exc
    if not isinstance(obj,dict):
        raise ValueError("Expected top-level market mapping.")
    _no_secret_keys(obj)
    return obj


def _normal_inputs(requested_paths):
    if requested_paths is None:
        return list(ALLOWLIST)
    if not isinstance(requested_paths,(tuple,list)):
        raise TypeError("Only a positional list of allowlisted files is accepted.")
    if len(requested_paths)!=len(ALLOWLIST):
        raise ValueError("Exactly the two public snapshots are required.")
    if any(type(p) is not str for p in requested_paths):
        raise TypeError("Market paths must be literal strings.")
    if list(requested_paths)!=list(ALLOWLIST):
        raise ValueError("Unexpected market snapshot path; deny by exact allowlist.")
    return list(ALLOWLIST)


def _zip_entry(name:str,content:bytes,archive:zipfile.ZipFile):
    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
    info.compress_type=zipfile.ZIP_DEFLATED
    info.external_attr=0o600 << 16
    archive.writestr(info,content,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)


def build_market_bundle(*,source_root,output_path,source_sha,requested_paths=None):
    if type(source_sha) is not str or re.fullmatch(r"[0-9a-fA-F]{40}",source_sha) is None:
        raise ValueError("Source SHA must be exactly 40 hexadecimal chars.")
    paths=_normal_inputs(requested_paths)
    root=Path(source_root).resolve(strict=True)
    out=Path(output_path).resolve(strict=False)
    if not root.is_dir():
        raise ValueError("Source root must be a directory.")
    if out==root or out.is_relative_to(root):
        raise ValueError("Artifact cannot be written inside checked-out repository.")
    if out.exists() or out.is_symlink():
        raise FileExistsError("Do not overwrite an existing artifact.")
    files=[]
    total=0
    payloads={}
    for name in paths:
        file=root/name
        if file.is_symlink() or not file.is_file():
            raise FileNotFoundError("Required regular public market file unavailable.")
        resolved=file.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("Market file cannot escape the source root.")
        size=file.stat().st_size
        if size>MAX_FILE_BYTES:
            raise ValueError("Market file exceeds size limit.")
        content=file.read_bytes()
        if len(content)!=size or len(content)>MAX_FILE_BYTES:
            raise ValueError("Market file changed or exceeded size budget.")
        _strict_load(content)
        total+=len(content)
        if total>MAX_TOTAL_BYTES:
            raise ValueError("Aggregate market artifact exceeds size budget.")
        files.append({
            "path":name,
            "sha256":hashlib.sha256(content).hexdigest(),
            "size_bytes":len(content),
        })
        payloads[name]=content
    manifest={
        "schema":SCHEMA,
        "status":"OFFLINE_ARTIFACT_ONLY",
        "source_commit":source_sha.lower(),
        "source_sha_authority":"SELF_REPORTED_REPOSITORY_SHA_NOT_INDEPENDENT",
        "freshness_status":"NOT_VERIFIED_STORED_REPOSITORY_COPY",
        "provider_fetch_performed":False,
        "runtime_write_authorized":False,
        "independent_witness_enrolled":False,
        "human_owner_verified":False,
        "worker_executed":False,
        "historical_restore_performed":False,
        "destination_kind":"GITHUB_ACTIONS_SHORT_LIVED_ARTIFACT_ONLY",
        "files":files,
    }
    manifest_bytes=(json.dumps(manifest,ensure_ascii=False,
                               sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
    out.parent.mkdir(parents=True,exist_ok=True)
    # All validations finish BEFORE the archive can be created.
    with zipfile.ZipFile(out,mode="x",compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        _zip_entry(MANIFEST_NAME,manifest_bytes,archive)
        for name in paths:
            _zip_entry(name,payloads[name],archive)
    return manifest


def inspect_bundle(path):
    bundle=Path(path)
    if not bundle.is_file() or bundle.is_symlink():
        raise ValueError("Missing ordinary artifact file.")
    with zipfile.ZipFile(bundle,mode="r") as archive:
        names=archive.namelist()
        expected=[MANIFEST_NAME,*ALLOWLIST]
        if names!=expected:
            raise ValueError("Unexpected, missing, duplicated or reordered ZIP entry.")
        if any(archive.getinfo(n).file_size>MAX_FILE_BYTES for n in ALLOWLIST):
            raise ValueError("Oversized ZIP content.")
        raw_manifest=archive.read(MANIFEST_NAME)
        manifest=_strict_load(raw_manifest)
        if (
            manifest.get("schema")!=SCHEMA
            or manifest.get("status")!="OFFLINE_ARTIFACT_ONLY"
            or manifest.get("provider_fetch_performed") is not False
            or manifest.get("runtime_write_authorized") is not False
            or manifest.get("independent_witness_enrolled") is not False
            or manifest.get("worker_executed") is not False
        ):
            raise ValueError("Artifact manifest claims unauthorized authority.")
        files=manifest.get("files")
        if not isinstance(files,list) or len(files)!=len(ALLOWLIST):
            raise ValueError("Malformed market file list.")
        for n,item in zip(ALLOWLIST,files):
            if not isinstance(item,dict) or item.get("path")!=n:
                raise ValueError("Market file path mismatch.")
            raw=archive.read(n)
            _strict_load(raw)
            if (
                hashlib.sha256(raw).hexdigest()!=item.get("sha256")
                or len(raw)!=item.get("size_bytes")
            ):
                raise ValueError("Artifact file digest or byte length mismatch.")
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-root",default=".")
    p.add_argument("--out")
    p.add_argument("--source-sha")
    p.add_argument("--inspect")
    a=p.parse_args()
    try:
        if a.inspect:
            if a.out or a.source_sha:
                raise ValueError("Inspect mode does not create new snapshots.")
            result=inspect_bundle(a.inspect)
        else:
            if not a.out or not a.source_sha:
                raise ValueError("Explicit output and commit required.")
            result=build_market_bundle(
                source_root=a.source_root,
                output_path=a.out,
                source_sha=a.source_sha,
            )
    except (OSError,ValueError,TypeError,zipfile.BadZipFile) as exc:
        print(json.dumps({"status":"BLOCKED","error":type(exc).__name__},
                         sort_keys=True))
        return 1
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0


if __name__=="__main__":
    sys.exit(main())
