# ADR-0013 — Efeito externo ambíguo nunca recebe retry automático

- Título: Efeito externo ambíguo nunca recebe retry automático
- Data: 2026-10-04
- Status: ACCEPTED

## Contexto

O AION terá integrações reais em múltiplos domínios. Em execução distribuída, um
processo pode cair depois de enviar uma requisição externa e antes de persistir a
resposta.

## Problema

Reexecutar automaticamente uma ação cujo resultado é desconhecido pode duplicar
pagamento, mensagem, publicação, mutação de CRM, ordem ou outro efeito externo.

## Alternativas consideradas

Foram rejeitados:
- retry cego após timeout;
- assumir que timeout significa ausência de efeito;
- confiar apenas em memória do processo;
- marcar a tarefa como FAILED e deixar scheduler tentar novamente.

## Decisão

Antes do handoff de um efeito externo, o AION registra durablemente
`DISPATCH_RECORDED`.

Se o resultado ficar ambíguo após esse ponto, o estado é
`OUTCOME_UNKNOWN` e `automatic_retry_allowed=False`.

Apenas reconciliação explícita, autorizada e com evidence digest pode concluir:
- CONFIRMED_EFFECT -> COMPLETED;
- CONFIRMED_NO_EFFECT -> RETRY_WAIT.

## Consequências

O sistema pode preferir esperar por reconciliação em vez de maximizar disponibilidade.
Isso é intencional para evitar duplicação de efeitos.

## Componentes afetados

Durable Tasks, Global Worker, future Execution Plane, providers, action receipts,
incident center e audit journal.

## Segurança

- replay não cria segunda execução;
- effect_key é único;
- lease é exclusiva;
- resultado ambíguo não é tratado como falha retryable;
- approval e authority continuam separados da mecânica de execução.

## Compatibilidade

O V2.14 reaproveita task_id/checkpoint/resume já existentes. Não ativa runtime externo.

## Rollback/migração

Remover OUTCOME_UNKNOWN ou habilitar retry automático pós-dispatch exige ADR sucessor
e nova certificação de segurança.

## PR/commit relacionado

Branch `integration/aion-v214-durable-execution-kernel-20261004`.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
