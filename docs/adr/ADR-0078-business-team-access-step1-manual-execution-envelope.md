# ADR-0078 — Business Team Access Step 1 Manual Execution Envelope

- Status: ACCEPTED
- Data: 2026-09-30
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

Um Step 1 Decision Record válido autoriza somente execução manual futura. Antes
de qualquer apply físico, o estado do sandbox pode ter mudado.

É necessário revalidar o ambiente após a decisão.

## Decisão

Adicionar um Execution Envelope read-only para Step 1.

O envelope exige:

- materialization íntegro;
- Step 1 preflight packet íntegro;
- Step 1 decision record íntegro;
- decisão com no máximo 120 segundos;
- nova observação com no máximo 120 segundos;
- nova observação coletada depois da decisão;
- mesma operator session;
- mesmo baseline digest;
- mesmo username sandbox;
- target account ainda ausente;
- lookup read-only no identity provider confirmado;
- tenant scope confirmado;
- health/OIDC/registry válidos;
- secrets locais;
- produção ausente;
- cleanup pronto;
- nenhuma mutação externa durante a observação.

## Estado máximo

READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY

Esse estado significa somente que um operador humano pode revisar um apply
manual.

## Segurança

Mesmo no estado máximo:

- provider_command_generated = false;
- physical_execution_performed = false;
- step_execution_receipt_present = false;
- ledger_append_authorized = false;
- automatic_execution_authorized = false;
- automatic_ledger_append = false;
- executor_enabled = false;
- production/deploy/runtime = false.

O envelope não contém comando de criação e não acessa Keycloak.

## Compatibilidade

Complementa ADR-0075, ADR-0076 e ADR-0077.
