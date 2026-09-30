# Continuidade — Step 1 Manual Execution Envelope — 30/09/2026

## Estado

Implementado / em validação sobre a Draft PR #465.

## Entrega

- revalidação da materialização;
- revalidação do Step 1 packet;
- revalidação do Step 1 decision record;
- observação pós-decisão obrigatória;
- decision age máximo 120 s;
- execution observation age máximo 120 s;
- target account absence gate;
- identity-provider lookup gate;
- tenant scope gate;
- health/OIDC/registry/secrets/production/cleanup gates;
- execution envelope digest;
- CLI read-only;
- template de observação;
- ADR-0078.

## Estado máximo

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY

## Não executado

- nenhum provider command;
- nenhuma conta criada;
- nenhum Step 1 físico;
- nenhum receipt;
- nenhum ledger append;
- executor/produção/deploy/runtime OFF.

## Próximo limite

A execução física do Step 1 continua fora desta camada e exige um operador
explicitamente autorizado, com receipt obrigatório após o apply.
