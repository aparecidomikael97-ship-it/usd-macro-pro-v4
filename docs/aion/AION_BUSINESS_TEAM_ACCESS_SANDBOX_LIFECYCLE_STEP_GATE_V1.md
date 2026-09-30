# AION BUSINESS — Equipe & Acessos · Step Gate do Lifecycle V1

## Objetivo

Garantir que o lifecycle sandbox avance um único passo por vez.

## Antes de cada step

O preflight confirma:
- plano e autorização corretos;
- ledger na posição esperada;
- baseline sem drift;
- sandbox saudável;
- OIDC e registry íntegros;
- secrets locais;
- nenhum target de produção;
- cleanup pronto.

Se tudo passar, o sistema chega apenas a:

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_DECISION

## Token por step

O token é derivado da ordem e do step id, por exemplo:

AUTHORIZE_SANDBOX_LIFECYCLE_STEP_1_CREATE_INDIVIDUAL_SANDBOX_ACCOUNT

Ele não é preenchido automaticamente e não habilita executor.

## Depois do step

O receipt é revisado contra:
- step esperado;
- chain head anterior;
- receipt digest recalculado;
- ausência de raw evidence;
- executor OFF;
- produção OFF.

O máximo é:

READY_FOR_MANUAL_LEDGER_APPEND_REVIEW

O append continua separado e manual.
