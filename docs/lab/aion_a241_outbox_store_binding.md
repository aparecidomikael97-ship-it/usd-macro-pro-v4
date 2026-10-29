# A241 — Vínculo do Outbox à integridade do store SQLite (somente LAB)

Continuação da A240 [PR #1691](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1691). **HARD NO-GO — 0/6 P0 homologadas.**

## Lacuna real da integração A240

A A240 adicionou comparação local de pathname no `SQLiteChatStore`, mas `ExecutionOutbox` armazenava `self.db = store.db` e continuava a usar esta referência diretamente. Algumas operações, especialmente `release_expired_claims`, podiam iniciar SQL antes de verificar o store original. Um gate no objeto de armazenamento não protege consumidores que não o consultam.

## Correção A241

- `ExecutionOutbox._require_bound_store()` verifica `store._require_open()` e que a conexão mantida pelo Outbox ainda é a mesma referência do store.
- `_scope_args()` exige o gate, cobrindo as queries escopadas de leitura/escrita e a máquina de estados.
- `release_expired_claims()` exige o gate **antes** de `BEGIN IMMEDIATE`.
- `dispatch_claimed()` exige a nova conferência imediatamente antes de chamar o adaptador; um caminho trocado não vira autorização para atravessar o limite do efeito.
- Se um envio sintético já ocorreu e a ligação falha após o callback, preserva a tentativa em `UNCERTAIN`; não marca `CONFIRMED` e não autoriza retry cego.

## Ensaios

8 novos testes sintéticos: operações normais, store fechado antes de leitura e início de transação, pathname mudado, impedimento de SEND antes da borda, mudança durante autorização, mudança depois de envio sintético com persistência `UNCERTAIN`, e `os.replace` real quando o SO permite.

Workflow Ubuntu/Windows com mais **1.130 testes A240** e 8 novos: **1.138 testes por SO previstos**, a confirmar nos logs.

## Limites indispensáveis

- A verificação de pathname é local e não autentica FD/VFS; o host pode alterar o arquivo no mesmo inode, trocar conteúdo após o check ou acessar `.db` diretamente.
- `ExecutionOutbox.dispatch_claimed` continua sem reserva independente obrigatória da primeira tentativa no stack atual. A [A180 #1470](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1470) tem um candidato LAB para essa reserva, **não integrado nem homologado** aqui; prioridade seguinte.
- Não há provedor real, recibo confiável, raiz externa, witness H0, antirollback físico, autorização HUMAN_OWNER independente ou prova de COMMIT.

**HARD NO-GO · P0 0/6 · UNCERTAIN=ZERO_AUTO_RESEND · sem merge/deploy/Worker/contratação/operação real.**
