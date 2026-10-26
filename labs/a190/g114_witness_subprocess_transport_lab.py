"""G114 test transport to a same-host subprocess signer (NO network).

The transport fixture, not the public-key-only protocol client, configures
the keyfile path. The path remains visible to the same-host process owner;
this separation proves API non-exposure, NOT actual secret independence.
"""
import json
from pathlib import Path
import subprocess
import sys

from labs.a190.g113_subprocess_witness_client_lab import WitnessProcessUnavailableLab


class G114SubprocessTransportLab:
    def __init__(self, *, db_path, witness_test_key_file, timeout=8):
        if type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise ValueError("G114_TIMEOUT_REQUIRED")
        self._db = Path(db_path)
        self._witness_key_path = Path(witness_test_key_file)
        self._timeout = timeout

    def __call__(self, action, request, *, drop_response=False):
        # Neither the 32-byte private key nor its hex representation appears
        # in this argv list or the JSON protocol body. Only a test FILE PATH.
        cmd = [
            sys.executable, "-B", "-m",
            "labs.a190.g114_witness_keyfile_server_lab",
            action, "--db", str(self._db),
            "--synthetic-key-file", str(self._witness_key_path),
        ]
        try:
            result = subprocess.run(
                cmd,
                input=json.dumps(request, sort_keys=True, allow_nan=False) + "\n",
                text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False, shell=False, timeout=self._timeout,
                cwd=str(Path(__file__).resolve().parents[2]),
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            raise WitnessProcessUnavailableLab("G114_TRANSPORT_FAILED") from exc
        if result.returncode != 0:
            raise WitnessProcessUnavailableLab("G114_WITNESS_DENIED_OR_UNAVAILABLE")
        if drop_response:
            # The server command has already completed, including durable
            # commit if it was reserve. Never auto-replay a missing ACK.
            raise WitnessProcessUnavailableLab("G114_ACK_UNKNOWN_NO_RESEND")
        if len(result.stdout) > 8192:
            raise WitnessProcessUnavailableLab("G114_RESPONSE_TOO_LARGE")
        try:
            reply = json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise WitnessProcessUnavailableLab("G114_RESPONSE_NOT_JSON") from exc
        if type(reply) is not dict:
            raise WitnessProcessUnavailableLab("G114_RESPONSE_NOT_OBJECT")
        return reply
