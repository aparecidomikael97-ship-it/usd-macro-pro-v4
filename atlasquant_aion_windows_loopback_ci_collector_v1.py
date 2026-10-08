"""CI-only TCP IPv4 loopback observer (normal child, NEVER an AppContainer).

This process binds an ephemeral listener on 127.0.0.1, independently sees a
positive control and a child-sent challenge, then cross-checks child stdout.
All work is offline loopback, inside temporary CI runtime. No profile,
Windows Firewall / WFP change, app install, owner-PC physical attestation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any

from atlasquant_aion_windows_loopback_observer_classifier_v1 import (
    SCHEMA, ENDPOINT, PROTOCOL, TOKEN_MODE, classify_localhost_receipt,
)

CHILD_SOURCE = r"""
import json
import socket
import sys
port = int(sys.argv[1])
nonce = sys.argv[2]
status = "START_ERROR"
code = None
try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2.5)
        s.connect(("127.0.0.1", port))
        s.sendall(nonce.encode("ascii"))
    status = "CONNECTED"
except OSError as exc:
    status = "OS_ERROR"
    code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
print(json.dumps({"status": status, "error_code": code, "nonce": nonce}, sort_keys=True))
"""


def run_ci_localhost_observation() -> tuple[dict[str, Any], dict[str, Any]]:
    """No arbitrary address/port/shell input: 127.0.0.1 and ephemeral port."""
    nonce = secrets.token_hex(16)
    start = time.monotonic()
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "probe_run_id": nonce,
        "endpoint": ENDPOINT,
        "protocol": PROTOCOL,
        "port": 0,
        "normal_control_reachable": False,
        "server_received_child_nonce": False,
        "child_started": False,
        "child_completed": False,
        "child_exit_code": None,
        "child_reported_status": "START_ERROR",
        "child_reported_error_code": None,
        "child_nonce_matches": False,
        "child_token_mode": TOKEN_MODE,
        "elapsed_ms": 0,
    }
    with tempfile.TemporaryDirectory(prefix="AION_LOOPBACK_CI_") as scratch:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((ENDPOINT, 0))
            listener.listen(3)
            listener.settimeout(3)
            receipt["port"] = listener.getsockname()[1]
            control_value = ("control-" + nonce).encode("ascii")
            try:
                with socket.create_connection((ENDPOINT, receipt["port"]), timeout=2) as client:
                    client.sendall(control_value)
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(2)
                    receipt["normal_control_reachable"] = connection.recv(64) == control_value
            except (OSError, ValueError):
                receipt["normal_control_reachable"] = False

            # The normal child represents a reachable control, NOT isolated
            # Windows/AppContainer execution. The executor is pinned to the
            # interpreter already executing this exact local test suite.
            env = {
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            if os.name == "nt":
                env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
                env["WINDIR"] = os.environ.get("WINDIR", r"C:\Windows")
            cmd = [
                sys.executable, "-I", "-B", "-S", "-c", CHILD_SOURCE,
                str(receipt["port"]), nonce,
            ]
            try:
                child = subprocess.run(
                    cmd, shell=False, env=env, cwd=scratch,
                    capture_output=True, text=True, timeout=6, check=False,
                )
                receipt["child_started"] = True
                receipt["child_completed"] = True
                receipt["child_exit_code"] = child.returncode
                if len(child.stdout) <= 600:
                    try:
                        data = json.loads(child.stdout)
                        if type(data) is dict and set(data) == {"status", "error_code", "nonce"}:
                            if (
                                type(data["nonce"]) is str
                                and data["nonce"] == nonce
                                and type(data["status"]) is str
                                and data["status"] in ("CONNECTED", "OS_ERROR")
                            ):
                                receipt["child_nonce_matches"] = True
                                receipt["child_reported_status"] = data["status"]
                                receipt["child_reported_error_code"] = data["error_code"]
                    except (ValueError, TypeError):
                        pass
            except subprocess.TimeoutExpired:
                receipt["child_started"] = True
                receipt["child_completed"] = False
                receipt["child_reported_status"] = "TIMEOUT"
            except OSError:
                receipt["child_reported_status"] = "START_ERROR"

            if receipt["child_started"] and receipt["child_completed"]:
                # The listener is the parent-side independent observation. A
                # malicious child cannot turn a self-reported denial into
                # evidence if its nonce reached this listener.
                try:
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(2)
                        receipt["server_received_child_nonce"] = (
                            connection.recv(64) == nonce.encode("ascii")
                        )
                except OSError:
                    pass
    receipt["elapsed_ms"] = round((time.monotonic() - start) * 1000)
    return receipt, classify_localhost_receipt(receipt)


if __name__ == "__main__":
    raw, conclusion = run_ci_localhost_observation()
    print(json.dumps({
        "receipt": raw,
        "classification": conclusion,
        "loopback_only": True,
        "physical_owner_windows_attestation": False,
        "appcontainer_created": False,
        "windows_firewall_changed": False,
    }, sort_keys=True))
