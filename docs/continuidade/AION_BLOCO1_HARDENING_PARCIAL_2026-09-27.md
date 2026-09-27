# AION Bloco 1 — entrega parcial consistente

Base: `b8f17e1d14ef7c07b5ac4bdca6c57a83dfcccb33`.
Branch: `checkpoint-ux-ecossistema-2026-09-27`.

## Implementado nesta parcela

- Tabelas centrais de transição de Durable Task e Step, terminais protegidos.
- Início/conclusão de steps consultam o Guardian existente. Nenhuma função
  executa o trabalho registrado ou ativa integrações externas.
- Cancelamento explícito preserva steps, evidências, artefatos e auditoria.
- Retry explícito somente para read/search/summarize/draft sem efeitos externos,
  com chave de idempotência estável, limite padrão de três tentativas, erro
  anterior preservado e nova aprovação quando exigida. Repetir a mesma chamada
  enquanto o step já está RUNNING não incrementa tentativas.
- Retomada valida revisão e digest, mantém WAITING_APPROVAL/BLOCKED e restaura
  contexto sem executar. Digest conhecido exige valor observado; divergência
  exige reconciliação explícita, nunca substituição silenciosa.
- Auditoria usa os eventos existentes, com correlation_id estável por tarefa,
  propagado aos steps e preservado no Checkpoint V17.
- Sanitização recursiva de metadados e redação de segredos curtos em texto.
- Relatório de coerência Mission/Task e rejeição de registros desatualizados
  no atualizador de tarefas do checkpoint. expected_checkpoint_digest permite
  checagem otimista no limite de escrita local; gravação remota continua usando
  SHA e readback existentes.

## Política e compatibilidade

PLANNED também admite PAUSED, WAITING_APPROVAL e BLOCKED para preparação e
restauração de contexto. PENDING/READY admitem RUNNING diretamente porque o
sistema registra trabalho local; não existe executor automático. DONE exige
RUNNING anterior no step. SKIPPED explícito pode avançar o cursor. O estado da
tarefa é derivado do step atual; alterações em steps futuros não o liberam.
Uma missão IN_PROGRESS pode conter tarefas em estados diferentes. Uma missão
terminal não pode ter tarefa ativa sem que o relatório sinalize divergência.

Campos novos não são inseridos ao normalizar registros antigos, preservando
seus digests quando o conteúdo não exige redação. Estados legados continuam
legíveis. Chamadas antigas sem expected_revision continuam suportadas; novos
chamadores devem informar a revisão observada. Evidências alteradas em um
step já no mesmo estado não são reaplicadas: a chamada é idempotente.

## Próximo passo exato — ainda dentro do Bloco 1

1. Aplicar regras explícitas a transition_mission sem migração destrutiva;
   atualizar seus chamadores e testes de conclusão direta legada.
2. Integrar mission_task_consistency também à atualização de Missions e ao
   preflight de recovery; hoje a validação bloqueante está na atualização das
   Durable Tasks, não em todos os pontos de entrada do Checkpoint.
3. Integrar SECURITY_BLOCK, CHECKPOINT_CREATED e RECOVERY_PREPARED à auditoria
   persistida existente e levar correlation_id ao relatório de recuperação.
4. Consolidar a reconciliação explícita de digest/revisão na interface, os
   limites de upsert e um teste completo Mission -> Task -> checkpoint ->
   recovery -> resume. Não considerar o Bloco 1 inteiro concluído antes disso.

Nenhum push, PR, merge, deploy, configuração de provedor ou alteração de secrets
faz parte desta entrega. Testes são locais; não confirmam runtime em produção.

## Validação desta parcela

- Base antes da mudança: 70 testes focados passaram.
- Implementação: 84 testes focados passaram.
- Suíte relacionada: 535 testes AION passaram em aproximadamente 18 segundos.
- Após ajustes finais de idempotência e seleção da tarefa na tela: 97 testes
  de hardening, Durable Tasks e administração passaram, incluindo duas novas
  regressões. A suíte completa não foi repetida após esses ajustes localizados.
- `git diff --check` passou. Nenhuma dependência nova.
