# AION BUSINESS — Equipe & Acessos · Step 1 Provider Runner V1

## Objetivo

Executar futuramente e de forma manual a única mutação física do Step 1 no
Keycloak sandbox, mantendo PLAN ONLY como padrão.

## PLAN ONLY

    .\Invoke-TeamAccessStep1Provider.ps1

O modo padrão:
- valida execution envelope;
- valida apply plan;
- valida source binding;
- exige localhost;
- exige sandbox;
- verifica freshness;
- mostra o token físico exigido;
- não solicita access token;
- não chama o endpoint de criação.

## APPLY

Somente depois de revisão administrativa explícita:

    .\Invoke-TeamAccessStep1Provider.ps1 -Apply -AuthorizationToken <token-exato>

O token precisa ser exatamente o emitido no PLAN ONLY e contém o
apply_plan_digest completo.

## Fluxo físico

1. preflight Python;
2. token efêmero do master/admin-cli;
3. GET exato do username;
4. hard stop se já existir;
5. POST de UserRepresentation;
6. status 201 obrigatório;
7. GET exato pós-write;
8. conferência de username/enabled/session/tenant/step;
9. receipt sanitizado;
10. nenhum append automático no ledger.

## Caminhos locais

Env, envelope, apply plan, preflight e receipt permanecem sob:

    %LOCALAPPDATA%\AtlasQuant\team-access-sandbox

e fora da árvore do repositório.

## Receipt

O receipt fica em:

    %LOCALAPPDATA%\AtlasQuant\team-access-sandbox\operator\step1-provider-execution-receipt.json

Ele registra evidência da mutação, mas não autoriza o ledger.

## Produção

Não existe target de produção nesta camada.
