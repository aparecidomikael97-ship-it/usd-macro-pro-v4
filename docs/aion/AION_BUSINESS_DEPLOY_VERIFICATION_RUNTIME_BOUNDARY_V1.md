# AION BUSINESS Deploy Verification & Runtime Boundary V1

Schema: `ATLASQUANT_AION_BUSINESS_DEPLOY_VERIFICATION_RUNTIME_BOUNDARY_V1`

## Objetivo

Definir o que precisa acontecer depois de uma futura decisão explícita de deploy
sem permitir que deploy seja confundido com ativação de runtime.

## Autorização de deploy

A decisão futura usa token exato:

`AUTHORIZE_BUSINESS_DEPLOY_ONLY`

Mensagens genéricas não servem.

O registro de autorização continua sem executar deploy.

## Preflight

Antes de qualquer execução externa futura, o preflight exige:

- autorização de deploy válida;
- main SHA igual ao SHA autorizado;
- rollback SHA válido;
- plano de deploy;
- plano de monitoramento;
- BUSINESS runtime OFF.

O estado máximo é `DEPLOY_EXECUTION_REVIEW_REQUIRED`.

## Verificação pós-deploy

Depois de um deploy executado por caminho separado, a verificação exige:

- SHA implantado igual ao SHA autorizado;
- ambiente igual ao alvo;
- application health = success;
- UI smoke = success;
- mobile DOM = success;
- observability = success;
- rollback ready = success;
- BUSINESS runtime ainda OFF;
- referência do recibo/evidência do deploy.

Estado verde:

`DEPLOY_VERIFIED_RUNTIME_DECISION_SEPARATE`

## Fronteira de runtime

Somente depois de deploy verificado pode existir um packet:

`EXPLICIT_RUNTIME_DECISION_REQUIRED`

Token reservado:

`AUTHORIZE_BUSINESS_RUNTIME_ACTIVATION`

Mesmo esse packet não autoriza runtime.

## Segurança

O módulo nunca:

- executa deploy;
- executa rollback;
- muda tráfego;
- publica;
- cobra;
- contata cliente;
- ativa runtime.
