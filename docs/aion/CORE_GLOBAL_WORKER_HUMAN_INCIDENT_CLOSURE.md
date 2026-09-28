# AION Global Worker Human Incident Closure Ceremony V1

## Purpose

This block adds the explicit human ceremony that follows
`CLOSURE_REVIEW_READY`.

Its job is to record an ADMIN's human closure decision **without** pretending
that a shared authoritative incident record has been persisted or changed.

V1 is intentionally session-only.

## Required upstream state

The ceremony can be prepared only when Recovery Evidence / Incident Closure V1
returns:

- `status=CLOSURE_REVIEW_READY`;
- `closure_review_ready=true`;
- closure package digest;
- original incident evidence digest;
- remediation digest;
- assessment timestamp.

If any binding is missing, the ceremony is blocked.

## Exact confirmation phrase

`ENCERRAR INCIDENTE WORKER GLOBAL`

The phrase applies only to the human incident-closure decision.

It does **not** authorize:

- Global Worker reactivation;
- feature-flag mutation;
- runtime Checkpoint mutation;
- worker tick;
- workflow dispatch;
- deploy;
- merge;
- real trading;
- provider or business action.

## Human acknowledgements

All three acknowledgements are required:

1. the human explicitly confirms the closure decision;
2. the human acknowledges the bound incident/remediation/current-evidence package;
3. the human acknowledges that reactivation is a separate future ceremony.

Missing any one of them leaves the ceremony at
`CONFIRMATION_REQUIRED`.

## Successful V1 result

A valid ceremony produces:

`HUMAN_CLOSURE_DECISION_RECORDED_SESSION_ONLY`

and an evidence-derived:

- `closure_record_id`;
- `closure_record_digest`;
- `human_closure_decision=APPROVED`.

It also preserves:

- `authoritative_incident_closed=false`;
- `shared_incident_record_modified=false`;
- `persistent=false`;
- `session_only=true`;
- `reactivation_authorized=false`;
- `reactivation_separate_ceremony_required=true`;
- `feature_flag_modified=false`;
- `runtime_modified=false`;
- `global_worker_tick_executed=false`;
- `real_trading_enabled=false`;
- `executes_action=false`.

## Why session-only first

This separates the human governance decision from persistence.

Before any future shared Incident Center or Checkpoint mutation, the project can
audit:

- exact input binding;
- confirmation semantics;
- UI wording;
- record digest stability;
- reactivation separation;
- absence of hidden mutation paths.

A future persistence block, if approved, must consume this record explicitly
and remain separate from reactivation.

## Central AION

The Central shows:

`✅ Cerimônia humana de fechamento do incidente`

Only a `CLOSURE_REVIEW_READY` assessment unlocks the ceremony.

The operator must:

- acknowledge the evidence package;
- confirm the human closure decision;
- acknowledge that reactivation remains separate;
- type the exact phrase.

After success, the UI must say:

- decisão humana registrada: SIM;
- fechamento autoritativo persistido: NÃO;
- reativação autorizada: NÃO;
- flag alterada: NÃO;
- runtime alterado: NÃO;
- trading real: NÃO.

## No new mutation authority

The module contains no:

- repository-variable write;
- runtime Checkpoint write;
- worker tick;
- workflow dispatch;
- subprocess/shell;
- provider/payment/publication/deploy/merge/trading action.

## CI audit

The Draft PR may be retargeted temporarily to `main` to run standard PR
workflows, then returned to its stacked base.

This audit operation grants no operational authority.
