# AION Eight Role Router V1

## Objetivo

Escolher, dentro de um único AION, quais papéis internos precisam participar de
cada tarefa.

O router de domínio continua respondendo **onde** a tarefa pertence:
Trader, Business, Investments ou Core.

Este router responde **quem dentro do AION deve revisar a tarefa**.

## Oito papéis

1. Orchestrator
2. Architect
3. Guardian
4. Executor
5. Memory
6. FinOps
7. Reliability
8. Customer Success

## Economia

- Orquestrador sempre presente.
- Até três especialistas adicionais.
- Máximo de quatro papéis por tarefa.
- Nenhum modelo pago é chamado automaticamente.
- Papéis compartilham infraestrutura.
- Tarefas simples podem permanecer em `LOCAL_LIGHT`.
- Tarefas multiárea usam `SHARED_STANDARD`.
- Tarefas críticas usam `STRONG_REVIEW`.

Esses tiers são metadados de planejamento, não autorização de provider.

## Tarefas críticas

Intenções envolvendo deploy, merge, pagamento, cobrança, publicação, trading
real, secrets, exclusão, runtime ou transferência forçam revisão reforçada.

Mesmo assim:
- `physical_execution_authorized=false`;
- `permission_escalation_allowed=false`;
- `deploy_authorized=false`;
- `trade_authorized=false`.

## Checkpoint Mestre

O registry só é considerado válido quando os oito IDs do Checkpoint Mestre
validado coincidem exatamente com o contrato oficial.

Checkpoint adulterado ou incompleto bloqueia o roteamento.
