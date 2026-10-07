# AION Chat — Production Postgres Adapter Contract V1

## Purpose

Define the exact composition order for a future production AION Chat host that
uses attested Postgres storage and may optionally use a paid external model.

This contract does not connect to Postgres or call a model. It defines the
implementation boundary only.

## Required turn order

1. validate authenticated product binding against trusted Scope;
2. verify production database health, schema and scope policy;
3. resume bounded scoped durable context;
4. persist the user turn and confirm durability;
5. route intelligence provider-neutrally without calling a provider;
6. enforce privacy, feature flag, per-turn approval and budget;
7. optionally call the provider at most once for that turn;
8. persist assistant output with provider response/idempotency evidence;
9. return a truthful durability state.

## Paid provider ordering

A paid/external provider call is forbidden before the user turn is durably
confirmed.

This avoids spending money for a turn that the system already knows it cannot
preserve.

## Persistence outcome unknown

If a provider call succeeds but assistant persistence becomes uncertain:

- state becomes `PERSISTENCE_OUTCOME_UNKNOWN`;
- UI must not claim the response was saved;
- the system must not automatically call the provider again;
- persistence reconciliation must use a separate idempotent path keyed by the
  original turn/provider response evidence.

This prevents duplicate paid calls and duplicate assistant messages.

## Existing components reused

The implementation should reuse rather than replace:

- `atlasquant_aion_chat_product_bridge.py` for authenticated scope binding;
- existing `aion_chat` store abstractions where compatible;
- `atlasquant_aion_model_router.py` for provider-neutral eligibility planning;
- `atlasquant_aion_provider.py` for privacy/approval/budget-gated provider use;
- local READ/SEARCH Golden Path for verified local capabilities.

## Authority boundary

Model approval is not external-action authority.

Even if a paid model request is individually approved:

- no trade;
- no payment;
- no message send;
- no deploy;
- no Worker activation;
- no Core write;
- no automatic memory promotion.

Those remain separate governed actions.

## Maximum state

`READY_FOR_PRODUCTION_POSTGRES_ADAPTER_IMPLEMENTATION_REVIEW`

## Next allowed step

`IMPLEMENT_PRODUCTION_POSTGRES_STORE_ADAPTER_IN_SEPARATE_PR`

That implementation must still be non-deployed until separately authorized.
