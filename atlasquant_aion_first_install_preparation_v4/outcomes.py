"""Uniform protected negative trust flags, including malformed/missing inputs."""
from atlasquant_aion_first_install_preparation.contracts import result as _result
NO_TRUST={name:False for name in (
    'root_trust_verified','external_anchor_verified','latest_head_independently_verified',
    'rollback_protection_production_verified','trusted_clock_verified',
    'durable_nonce_consumption_verified','independent_administrative_domains_verified',
    'institutional_identity_verified','witness_key_enrollment_verified',
    'witness_custody_verified','safe_to_resume','source_trust_production_verified',
    'coordinator_custody_verified','anchor_custody_verified','freshness_independently_verified',
    'automatic_retry_allowed','deployment_authorized','installer_authorized',
    'billing_authorized','model_invocation_authorized','provider_called')}

def result(state='BLOCKED',*reasons,**details):
    return _result(state,*reasons,**{**details,**NO_TRUST})
