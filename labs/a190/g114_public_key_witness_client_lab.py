"""G114 public-key-only witness protocol client, synthetic LAB ONLY.

The protocol client requires a callable transport and pinned Ed25519 PUBLIC
key. It has no private signer seed, keyfile parameter, or bootstrap authority
of its own. The injected same-host transport fixture may point to a key file,
so this is NOT a cryptographic/OS separation from a privileged host.
"""
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from labs.a190.g113_subprocess_witness_client_lab import (
    SubprocessWitnessClientLab, WitnessProcessUnavailableLab,
)


class G114PublicKeyWitnessClientLab(SubprocessWitnessClientLab):
    """Inherit the tested, exact signed wire verifier; remove secret input."""

    def __init__(self, *, pinned_public_key, transport):
        if type(pinned_public_key) is not bytes or len(pinned_public_key) != 32:
            raise ValueError("G114_PUBLIC_TRUST_PIN_REQUIRED")
        if not callable(transport):
            raise TypeError("G114_WITNESS_TRANSPORT_REQUIRED")
        # Deliberately DO NOT call G113's secret-carrying __init__.
        # No signing key, key path or seed is stored in this client.
        self._pin = Ed25519PublicKey.from_public_bytes(pinned_public_key)
        self._transport = transport

    def _invoke(self, action, request, *, drop_response=False):
        try:
            return self._transport(
                action, request, drop_response=drop_response,
            )
        except WitnessProcessUnavailableLab:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise WitnessProcessUnavailableLab(
                "G114_UNTRUSTED_TRANSPORT_UNAVAILABLE"
            ) from exc
