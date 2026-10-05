# AION B2B — Owner Renewal Persistence Plan V1

Status: **staging / patch-candidate only / no checkpoint write**.

## Objetivo

Preparar a persistência de uma decisão de renovação/continuidade já
criptograficamente verificada, sem salvar nada automaticamente.

## O que é validado

- schema e estado da verificação;
- assinatura e decisão marcadas como verificadas;
- decisão ainda não registrada/persistida;
- digest exato do decision record;
- owner/tenant/workspace/customer/pilot;
- pacote e tipo de revisão;
- digest do pacote de revisão;
- digest do ciclo;
- digest do contrato;
- digest da conversão value-bound;
- digest da solicitação de decisão;
- digest da solicitação de assinatura;
- ausência total de autoridade externa;
- integridade do Checkpoint Master atual.

## Pinning do checkpoint

O plano grava no candidato:

- `expected_revision`;
- `expected_state_digest`;
- `recommended_event_id`;
- `patch_digest`.

Assim, uma mudança concorrente no checkpoint invalida a expectativa usada pelo
plano em vez de ser silenciosamente ignorada.

## Saída

O estado máximo é:

`READY_FOR_EXPLICIT_CHECKPOINT_PERSISTENCE`

com um `PATCH_CANDIDATE`.

Ainda permanecem:

- `checkpoint_saved=false`;
- `automatic_checkpoint_write=false`;
- `owner_decision_recorded=false`;
- `decision_persisted=false`;
- `business_action_authorized=false`.

## Limite de autoridade

Persistir uma decisão não equivale a executá-la. Renovação, expansão, pausa,
encerramento, cobrança, repricing, quota, roles, integrações, contato,
provisionamento, CRM, provider, deploy e produção permanecem sem autorização.

A etapa seguinte deve comprovar uma persistência explícita e exata antes de
qualquer outro gate.
