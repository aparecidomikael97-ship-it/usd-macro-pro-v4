# BUSINESS Deploy Verification & Runtime Boundary V1 — 2026-09-30

## Missão

Adicionar a barreira entre um futuro deploy e qualquer futura ativação do
BUSINESS runtime.

## Fluxo

acknowledgement técnico → handoff → decisão explícita deploy-only →
preflight → execução externa futura → recibo do deploy → verificação →
decisão explícita de runtime separada.

## Tokens

Deploy-only:
`AUTHORIZE_BUSINESS_DEPLOY_ONLY`

Runtime futuro:
`AUTHORIZE_BUSINESS_RUNTIME_ACTIVATION`

## Checks pós-deploy

- application_health
- ui_smoke
- mobile_dom
- observability
- rollback_ready

## Regras

- deploy authorization record não executa deploy;
- preflight não executa deploy;
- receipt ruim bloqueia;
- SHA implantado precisa bater;
- runtime precisa continuar OFF depois do deploy;
- packet de runtime não autoriza runtime;
- "vamos lá" não é autorização.

## Segurança

Sem deploy, rollback, runtime, piloto, cliente real, publicação ou cobrança.

## Próximo passo

Depois de CI verde, o próximo bloco pode ser **Runtime Activation Review V1**,
definindo escopo mínimo, kill switch, observabilidade, piloto permitido e
rollback antes de qualquer futura ativação real.
