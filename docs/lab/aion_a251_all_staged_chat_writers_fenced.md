# A251 — Proteção de todas as seis rotas públicas de escrita do SQLiteChatStore (LAB)

**Status: HARD NO-GO · 0/6 P0 homologadas · sem Worker, merge, deploy, contratação ou efeitos reais.**

## Diagnóstico

A250 protegia `create_conversation` e `append_message`, porém outras rotas públicas alteravam o SQLite com `with self.db:` e sem marcador pré-COMMIT: `archive_conversation`, `add_attachment_metadata`, `save_checkpoint` e `save_context_summary`. Uma confirmação perdida poderia permitir nova gravação, duplicação de registros ou divergência de histórico.

## Mudança A251

- As quatro rotas passam por `@_local_commit_gate`: serialização por RLock de processo e trava consultiva de kernel entre processos cooperantes (A248/A249).
- Dentro de `_fenced_chat_transaction`, iniciam com `BEGIN IMMEDIATE`, mantêm as validações e alterações originais e concluem pelo `_commit_fenced_chat_write()` da A250, que prepara o marcador local *antes* do COMMIT e o remove somente após confirmação.
- Erro após a tentativa de COMMIT é `StoreCommitOutcomeUncertainError`; a instância fica FAILED. O marcador impede reabrir automaticamente enquanto permanecer.
- Erros de validação anteriores ao COMMIT fazem rollback sem publicar marcador e não geram falsa confirmação de gravação.
- A XFAIL de arquivamento descoberta na A250 virou teste positivo (com chamada real da preparação do marcador e checagem de estado).
- Nenhuma mudança em contratos externos ou habilitação de envio.

## Testes novos

1. Fluxo íntegro de criação/mensagem/anexo/checkpoint/resumo/arquivamento, com reabertura do SQLite.
2. Cada uma das quatro novas rotas com COMMIT SQLite verdadeiro, seguido de perda sintética do ACK: efeito persistido, FAILED, veto local, sem retry.
3. Validação inválida e escopo incorreto antes da confirmação, sem efeitos parciais.
4. Subprocesso real encerrado entre COMMIT de arquivamento e limpeza do marcador.
5. Três processos cooperantes gravando doze resumos, sem perda/duplicação.
6. Inventário explícito dos seis métodos públicos de escrita do SQLiteChatStore e confirmação de que não utilizam `with self.db:`.
7. **XFAIL honesta:** host apaga marcador local de uma operação incerta e reabre o banco.

Regressões A250–A233 e testes do runtime de chat serão executados em Ubuntu e Windows, incluindo baterias longas de backup/restore.

## Limites e seguimento

Esta PR cobre as seis rotas públicas de escrita do **SQLiteChatStore**. Não transforma `self.db` em API selada: chamadores com acesso direto à conexão, rotas internas de backup/restore, `ExecutionOutbox` e demais SQL externos têm limites próprios. A trava e o marcador são **locais, consultivos, adulteráveis e sem raiz de confiança independente**. Testes não provam durabilidade sob falta física de energia, identidade VFS/FD atestada, antirrollback persistente externo, recibo de provedor nem homologação P0.

**HARD NO-GO operacional · 0/6 P0 · UNCERTAIN=ZERO_AUTO_RESEND**. Trader prioritário; motor econômico compartilhado com Investimentos; Negócios congelada e preservada. Nenhuma despesa nova.
