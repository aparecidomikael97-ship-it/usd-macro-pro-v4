# ADR-0043 — Toda expansão verificada volta a congelar o escopo

- Título: Toda expansão verificada volta a congelar o escopo
- Data: 2026-09-30
- Status: ACCEPTED

## Contexto

ADR-0042 valida e registra uma decisão explícita para expansão limitada, mas a
execução física continua separada.

## Problema

Depois de uma futura expansão real, o sistema precisa comprovar que o runtime
observado corresponde exatamente ao escopo e aos tenants autorizados. O sucesso
da expansão não pode criar uma permissão contínua de crescimento.

## Decisão

Criar uma verificação pós-expansão read-only que exige:

1. execution review packet válido;
2. escopo observado idêntico ao proposto;
3. conjunto de tenants observado idêntico ao proposto;
4. limite de tenants preservado;
5. application health, observability, tenant isolation, privacy, support,
   capacity, billing guardrail e rollback verdes;
6. referência de evidência;
7. confirmação de que o runtime corresponde somente à expansão autorizada.

O estado verde é SCOPE_EXPANSION_VERIFIED_AND_FROZEN.

Depois dele, pode ser produzido apenas um novo
EXPLICIT_EXPANSION_DECISION_REQUIRED, compatível com o mesmo preflight de
ADR-0042.

## Consequências

Cada expansão conclui um ciclo e congela novamente o escopo. Para crescer de
novo, é obrigatório reiniciar a cadeia de preflight, autorização e revisão.

## Segurança

Nenhuma função executa expansão, altera runtime, muda tráfego, faz deploy ou
rollback, publica, cobra ou contata clientes.

## Compatibilidade

O boundary packet renovado usa o mesmo schema esperado pelo preflight de
ADR-0042.

## Rollback

Read-only/administrativo; sem efeito externo a compensar.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
