"""A190 G17: fetch ONLY pinned official SQLite headers for transient LAB builds.

No arbitrary archive extraction or mutable latest URL. This script is for
sandbox/CI experiments, not runtime, packaging or automatic updates.
"""
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import urllib.request
import zipfile

URL = "https://www.sqlite.org/2026/sqlite-amalgamation-3540100.zip"
EXPECTED_SHA3_256 = "92281c86e2957f9b9305890f9ac04204caa7b677cc868dc326d942689df28e30"
MAX_DOWNLOAD_BYTES = 6 * 1024 * 1024


def extract_verified_headers(directory):
    target = Path(directory).resolve()
    # Parent caller chooses an isolated non-production directory.
    request = urllib.request.Request(URL, headers={"User-Agent": "AION-G17-LAB/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        archive = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(archive) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("G17_OFFICIAL_SDK_DOWNLOAD_SIZE_DENIED")
    sha3 = hashlib.sha3_256(archive).hexdigest()
    if sha3 != EXPECTED_SHA3_256:
        raise RuntimeError("G17_OFFICIAL_SDK_SHA3_MISMATCH_DENY")
    with zipfile.ZipFile(BytesIO(archive)) as bundle:
        wanted = {}
        for header in ("sqlite3.h", "sqlite3ext.h"):
            entries = [item for item in bundle.namelist() if item.endswith("/" + header)]
            if len(entries) != 1:
                raise RuntimeError("G17_REQUIRED_OFFICIAL_HEADER_MISSING")
            wanted[header] = bundle.read(entries[0])
    target.mkdir(parents=True, exist_ok=False)
    for name, payload in wanted.items():
        (target / name).write_bytes(payload)
        print(f"G17_HEADER_VERIFIED={name}:{len(payload)}")
    print("G17_OFFICIAL_AMALGAMATION_SHA3_VERIFIED=" + sha3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", required=True)
    args = parser.parse_args()
    extract_verified_headers(args.dest)
