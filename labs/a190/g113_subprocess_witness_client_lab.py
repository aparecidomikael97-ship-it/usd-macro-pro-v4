"""G113 LAB only: subprocess IPC boundary for a same-host witness emulator.

No socket/network transport, secret provisioning, remote trusted hardware,
real provider, or production authorization. The synthetic private key seed is
deliberately supplied by this test client so the trust root is NOT independent.
Never call a verified G113 emulator signature a P0-authorized SEND receipt.
"""
from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
import secrets
import subprocess
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_chat.signed_receipt_lab import canonical_bytes
from labs.a190.g113_subprocess_witness_lab import DOMAIN, ISSUER, SCHEMA


_FIELDS = frozenset({
    "schema", "issuer", "status", "challenge", "event_id",
    "original_sha256", "owner_id", "tenant_id", "workspace_id",
    "effect_digest", "idempotency_key", "sequence", "high_water", "count",
})


class WitnessProcessUnavailableLab(RuntimeError):
    """No authorization from an unavailable or malformed subprocess."""


class SubprocessWitnessClientLab:
    """Never read the trust key from the witness response itself."""

    def __init__(self, *, db, synthetic_seed, pinned_public_key, timeout=10):
        if type(synthetic_seed) is not bytes or len(synthetic_seed) != 32:
            raise ValueError("G113_TEST_SEED_REQUIRED")
        if type(pinned_public_key) is not bytes or len(pinned_public_key) != 32:
            raise ValueError("G113_PINNED_PUBLIC_KEY_REQUIRED")
        if type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise ValueError("G113_STRICT_IPC_TIMEOUT_REQUIRED")
        self._db = Path(db)
        self._seed = synthetic_seed.hex()
        self._pin = Ed25519PublicKey.from_public_bytes(pinned_public_key)
        self._timeout = timeout

    def _invoke(self, action, request, *, drop_response=False):
        cmd = [
            sys.executable, "-B", "-m",
            "labs.a190.g113_subprocess_witness_lab", action,
            "--db", str(self._db), "--synthetic-seed", self._seed,
        ]
        try:
            process = subprocess.run(
                cmd, input=json.dumps(request, allow_nan=False) + "\n",
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=str(Path(__file__).resolve().parents[2]),
                timeout=self._timeout, check=False, shell=False,
            )
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            raise WitnessProcessUnavailableLab("G113_IPC_UNAVAILABLE") from exc
        if process.returncode != 0:
            raise WitnessProcessUnavailableLab("G113_IPC_DENIED_OR_UNAVAILABLE")
        if drop_response:
            # An externally committed reservation could have succeeded. A
            # missing ACK means UNCERTAIN; never treat the effect as zero.
            raise WitnessProcessUnavailableLab("G113_LOST_RESPONSE_AFTER_COMMIT")
        if len(process.stdout) > 8192:
            raise WitnessProcessUnavailableLab("G113_OVERSIZED_RESPONSE_DENIED")
        try:
            output = json.loads(process.stdout)
        except (ValueError, TypeError) as exc:
            raise WitnessProcessUnavailableLab("G113_MALFORMED_RESPONSE") from exc
        if type(output) is not dict:
            raise WitnessProcessUnavailableLab("G113_RESPONSE_SHAPE_DENIED")
        return output

    def bootstrap_synthetic_only(self):
        """Explicit, unsafe test-only enrollment on a fresh filename."""
        response = self._invoke("bootstrap", {})
        if response != {"status": "BOOTSTRAPPED_SYNTHETIC_ONLY"}:
            raise WitnessProcessUnavailableLab("G113_BOOTSTRAP_ACK_DENIED")
        return response

    def enroll_synthetic_only(self, *, event_id, original_sha256,
                              owner_id, tenant_id, workspace_id):
        response = self._invoke("enroll", {
            "event_id": event_id, "original_sha256": original_sha256,
            "owner_id": owner_id, "tenant_id": tenant_id,
            "workspace_id": workspace_id,
        })
        if response not in (
            {"status": "ENROLLED"}, {"status": "ALREADY_ENROLLED"},
            {"status": "ENROLLMENT_CONFLICT"},
        ):
            raise WitnessProcessUnavailableLab("G113_ENROLLMENT_RESPONSE_DENIED")
        return response["status"]

    def _verified(self, response, *, challenge, event_id):
        try:
            if type(response) is not dict or set(response) != {"payload", "signature"}:
                return False
            payload = response["payload"]
            if type(payload) is not dict or set(payload) != _FIELDS:
                return False
            if (payload["schema"] != SCHEMA or payload["issuer"] != ISSUER
                    or payload["challenge"] != challenge
                    or payload["event_id"] != event_id):
                return False
            if any(type(payload[k]) is not str for k in (
                "status", "original_sha256", "owner_id", "tenant_id",
                "workspace_id", "effect_digest", "idempotency_key",
            )):
                return False
            if (type(payload["sequence"]) is not int
                    or type(payload["high_water"]) is not int
                    or type(payload["count"]) is not int
                    or payload["sequence"] < 0
                    or payload["high_water"] < 0
                    or payload["count"] < 0
                    or payload["high_water"] != payload["count"]
                    or payload["sequence"] > payload["high_water"]):
                return False
            if payload["status"] not in {
                "RESERVED", "ALREADY_RESERVED", "ENROLLED",
                "UNKNOWN_EVENT_DENIED", "ORIGINAL_IDENTITY_DENIED", "NOT_FOUND",
            }:
                return False
            if (payload["status"] in ("RESERVED", "ALREADY_RESERVED")
                    and (payload["sequence"] <= 0
                         or not payload["effect_digest"]
                         or not payload["idempotency_key"])):
                return False
            if type(response["signature"]) is not str:
                return False
            sig = base64.b64decode(response["signature"], validate=True)
            if len(sig) != 64:
                return False
            self._pin.verify(sig, DOMAIN + canonical_bytes(payload))
            return True
        except (ValueError, TypeError, KeyError, InvalidSignature,
                binascii.Error):
            return False

    @staticmethod
    def _challenge():
        return secrets.token_hex(32)

    def reserve(self, *, event_id, original_sha256, effect_digest,
                idempotency_key, owner_id, tenant_id, workspace_id,
                lost_response=False):
        challenge = self._challenge()
        reply = self._invoke("reserve", {
            "challenge": challenge, "event_id": event_id,
            "original_sha256": original_sha256,
            "effect_digest": effect_digest,
            "idempotency_key": idempotency_key,
            "owner_id": owner_id,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
        }, drop_response=lost_response)
        if not self._verified(reply, challenge=challenge, event_id=event_id):
            raise WitnessProcessUnavailableLab("G113_SIGNED_RESERVATION_INVALID")
        payload = reply["payload"]
        # A valid signature on ALREADY_RESERVED is a signed DENIAL, not a
        # second permission. Only the unique first COMMIT is a candidate.
        if payload["status"] != "RESERVED":
            raise WitnessProcessUnavailableLab("G113_DUPLICATE_OR_DENIED_NO_SEND")
        if any(
            payload[k] != value for k, value in (
                ("original_sha256", original_sha256),
                ("effect_digest", effect_digest),
                ("idempotency_key", idempotency_key),
                ("owner_id", owner_id), ("tenant_id", tenant_id),
                ("workspace_id", workspace_id),
            )
        ):
            raise WitnessProcessUnavailableLab("G113_RESERVATION_IDENTITY_MISMATCH")
        return payload

    def status(self, event_id):
        challenge = self._challenge()
        reply = self._invoke(
            "status", {"challenge": challenge, "event_id": event_id}
        )
        if not self._verified(reply, challenge=challenge, event_id=event_id):
            raise WitnessProcessUnavailableLab("G113_SIGNED_STATUS_INVALID")
        return reply["payload"]

    def verify_forged_or_replayed(self, envelope, *, challenge, event_id):
        """Adversarial test helper; must never authorize a provider SEND."""
        return self._verified(envelope, challenge=challenge, event_id=event_id)
