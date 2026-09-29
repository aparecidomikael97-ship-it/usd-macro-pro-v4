# AION Core Hardening P2 V1

Data: 2026-09-29
Base: `cursor/aion-core-hardening-p1-v1` @ `273e28b30617f92fa2b09edf49ccd4090f3d2de2`
Issue: #325

## O que este bloco prova no contrato atual

`atlasquant_aion_durable_tasks.py` continua sendo o único motor de tarefa durável.

- Tarefa `DONE` ou `CANCELED` rejeita nova execução com `TASK_TERMINAL`.
- Retry com a mesma chave de idempotência, enquanto o passo já está `RUNNING`, não incrementa outra tentativa.
- Chave diferente no mesmo passo em retry conflita.
- Passo com efeito externo ou ação fora de leitura/rascunho não é elegível a retry automático.
- `"yes"`, `"true"` e `1` não contam como aprovação para sair de `WAITING_APPROVAL`.
- Passo fora de ordem e revisão velha falham fechados.
- Cada chave de retry entra em `consumed_idempotency_keys`, com limite de 32 chaves de até 128 caracteres.
- Uma chave já consumida é no-op depois de nova falha, pause, resume, normalize ou snapshot. Não incrementa `attempts` nem `revision`.
- Uma chave nova pode iniciar outra tentativa só se o passo estiver `FAILED`, a ação for retry-safe, a revisão for atual, `attempts` estiver abaixo de `max_attempts` e o histórico não estiver cheio.

O update continua sendo registro de estado. Não executa a ação do passo.

## O que continua fora

Workers concorrentes reais, fila externa, checkpoint parcialmente gravado em disco e restore operacional não foram exercidos.
