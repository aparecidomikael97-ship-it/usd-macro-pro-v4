"""Bounded V2 semantic input guards; closed artifact schemas remain mandatory.

Cloning reuses the legacy bounded JSON utility, but V2 semantic types and
transport/material guards are checked before producers, hashing or lookups.
"""
from atlasquant_aion_b2b_owner_renewal_action_adapter_plan import safe_copy

_MATERIAL_KEYS = frozenset((
    'api_base', 'webhook', 'callback', 'invoke', 'transport', 'provider_config',
    'connection', 'secret_ref',
))
_STRING_KEYS = frozenset((
    'schema', 'state', 'status', 'package', 'review_type', 'requested_choice',
    'action_family', 'operation_kind', 'execution_decision', 'adapter_kind',
    'provider_class', 'target_domain', 'scope_source', 'operation_kind_source',
    'as_of', 'expires_at', 'timestamp', 'observed_at', 'persisted_at',
    'writer_ref', 'provider_state', 'rollback_state', 'contract_state', 'service_state',
    'command_plan_schema', 'adapter_contract_version',
))
_INTEGER_KEYS = frozenset((
    'finops_monthly_cents', 'finops_cap_cents', 'staging_revision',
    'checkpoint_revision', 'writer_key_version', 'rollback_timeout_seconds',
))
_BINDING_KEYS = frozenset((
    'scope', 'customer_id', 'pilot_id', 'package', 'review_type', 'requested_choice',
    'action_family', 'operation_kind', 'action_parameters_digest',
    'execution_preflight_digest', 'execution_record_digest',
    'execution_intent_writer_request_digest', 'execution_request_digest', 'command_plan_digest',
))


def safe_input_v2(value):
    copied = safe_copy(value)

    def walk(item, key=''):
        if key.lower() in _MATERIAL_KEYS:
            raise ValueError('V2_TRANSPORT_MATERIAL_FORBIDDEN')
        if key in _STRING_KEYS or key.endswith(('_id', '_digest', '_ref')):
            if type(item) is not str:
                raise ValueError('V2_STRING_TYPE_REQUIRED')
        if key in _INTEGER_KEYS and type(item) is not int:
            raise ValueError('V2_INTEGER_TYPE_REQUIRED')
        if type(item) is int and key not in _INTEGER_KEYS:
            raise ValueError('V2_UNDECLARED_INTEGER')
        if key == 'scope':
            if type(item) is not dict or set(item) != {'owner_id', 'tenant_id', 'workspace_id'}:
                raise ValueError('V2_SCOPE_SCHEMA_INVALID')
        if key == 'binding':
            if type(item) is not dict or set(item) != _BINDING_KEYS:
                raise ValueError('V2_BINDING_SCHEMA_INVALID')
        if type(item) is dict:
            for name, child in item.items():
                walk(child, name)
        elif type(item) is list:
            for child in item:
                walk(child)

    walk(copied)
    return copied


__all__ = ['safe_input_v2']
