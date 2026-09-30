# AION BUSINESS — Equipe & Acessos · Aceitação do Baseline Real V1

## Objetivo

Separar baseline tecnicamente válido de baseline oficialmente aceito para
planejamento do lifecycle.

## Entrada

O contrato recebe um handoff no estado:

READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW

## Registro de aceitação

O template fica em:

deploy/sandbox/team-access/real-baseline-acceptance-record.template.json

O registro precisa conter:

- token exato;
- handoff digest;
- baseline digest;
- operator session id;
- accepted_by;
- accepted_at;
- acknowledgements completos.

## Estado máximo

REAL_SANDBOX_BASELINE_ACCEPTED_FOR_LIFECYCLE_PLANNING

Mesmo nesse estado:
- lifecycle execution = false;
- sandbox step execution = false;
- production = false;
- deploy = false;
- runtime = false.

## Próximo gate

Somente um baseline aceito poderá ser usado pelo próximo contrato de criação de
plano real de lifecycle. Esse plano ainda terá autorização própria separada.
