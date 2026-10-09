"""Reference integration only: signature math -> atomic nonce, NEVER authorization."""
from atlasquant_aion_durable_dual_ed25519_challenge_registry_v1 import (
    ReferenceChallengeRegistry, ReferenceStoreError, _result,
)


def verify_and_consume_reference(*, registry, request, now_ts):
    """Only a real reference registry, not a caller receipt or verification claim.

    No enrollment pin, TPM operation, installer, worker, provider or execution.
    Both role signatures are mathematically verified again by the registry; a
    claim such as {"signature_mathematically_valid": True} cannot consume a nonce.
    """
    if type(registry) is not ReferenceChallengeRegistry:
        return _result("REFERENCE_REGISTRY_REQUIRED")
    try:
        return registry.consume(request=request, now_ts=now_ts)
    except (ReferenceStoreError, OSError):
        return _result("REFERENCE_STORAGE_UNAVAILABLE")


__all__ = ("verify_and_consume_reference",)
