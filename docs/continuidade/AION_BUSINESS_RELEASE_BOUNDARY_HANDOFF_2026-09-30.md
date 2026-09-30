# BUSINESS Release Boundary Handoff V1 — 2026-09-30

## Missão

Separar formalmente a consolidação técnica da futura decisão de deploy e da
futura decisão de runtime.

## Estados

- `TECHNICAL_ACKNOWLEDGEMENT_REQUIRED`
- `HANDOFF_BLOCKED`
- `READY_FOR_SEPARATE_DEPLOY_DECISION`
- `EXPLICIT_DEPLOY_DECISION_REQUIRED`

## Token reservado

`AUTHORIZE_BUSINESS_DEPLOY_ONLY`

## Regras

- acknowledgement técnico é pré-condição;
- main SHA fica vinculado;
- ambiente alvo precisa ser nomeado;
- deploy plan precisa existir;
- rollback SHA precisa existir;
- monitoring plan precisa existir;
- BUSINESS runtime precisa estar OFF;
- runtime decision precisa ficar separada;
- handoff não executa deploy.

## Segurança

Sem merge, deploy, rollback, runtime, piloto, cliente real, publicação ou
cobrança.

## Próximo passo

Depois de CI verde, o próximo bloco pode ser **Deploy Verification / Runtime
Boundary V1**, ainda read-only: verificar recibo de deploy e saúde do ambiente
sem permitir ativação de runtime.
