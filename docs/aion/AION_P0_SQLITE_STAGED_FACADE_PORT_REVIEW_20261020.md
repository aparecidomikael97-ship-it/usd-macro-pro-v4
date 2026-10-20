# AION P0 — Port isolado da fachada SQLite STAGING entre threads (GO-LAB pendente de CI)

**Data: 20 de outubro de 2026.** **HARD NO-GO, 0/6 P0 homologados, Worker desligado, ZERO_AUTO_RESEND.**

## Defeito concreto e escopo

O [PR diagnóstico #1347](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1347) executou o **host real** em duas threads e mostrou que o chat STAGING mantinha `SQLiteChatStore` nativo em `session_state`; o rerun de outra thread era rejeitado com `SQLITE_STORE_CONNECTION_THREAD_MISMATCH`. Esta negação evita abuso do SQLite, mas deixa a sessão indisponível sem retorno à thread proprietária. O defeito havia sido reproduzido antes, em 10/10, no [PR #1195](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1195), cuja correção não havia sido integrada nesta branch. A linha AION atual possui guards mais recentes de owner-thread/backup e não pode copiar cegamente os arquivos antigos.

## Alterações candidatas (ainda **não integradas**)

1. **`aion_chat/staged_store.py`**: port da fachada `OperationScopedSQLiteChatStore` de [#1195, SHA exato](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/blob/e0e249db64c1bef32ff47f0048a9900542dd144a/aion_chat/staged_store.py): guarda caminho, RLock e revogação, **não armazena conexão nativa**; abre e fecha `SQLiteChatStore` na thread de **cada operação**, retorna apenas valores materializados; falha irrevogável após corrupção, erro de close ou substituição detectada do arquivo por `dev/ino`. O último é diagnóstico local sujeito a TOCTOU/rollback, não root de segurança contra um atacante com acesso ao filesystem.
2. **`atlasquant_aion_chat_host_staging.py`**: usa `connection_free=True` *exclusivamente dentro de `build_staged_host_binding`*, que mantém `TEST/STAGING/LOCAL`, `ADMIN AUTHENTICATED`, escopo owner/tenant/workspace e fingerprint original. A API low-level `get_or_create_staged_store` conserva `connection_free=False` por padrão, para manter a bateria original que prova que conexões NATIVAS cross-thread **continuam negadas**. O preflight de close verifica **TODAS as conexões nativas legadas** antes de remover qualquer holder, inclusive em sessão mista com fachada nova. Se a conexão legada não puder ser fechada na thread dona, a migração **nega e retém** o holder.
3. **`atlasquant_aion_chat_storage_resilience.py`**: aceita **apenas duas classes concretas** de store no backup: `SQLiteChatStore` e `OperationScopedSQLiteChatStore`; não abre `duck typing` nem modifica `SQLiteChatStore.restore_from_backup`.
4. **Nenhuma edição** no `aion_chat/store.py` (thread-check, restore de execução negado, WAL, native `check_same_thread=True`), ExecutionOutbox/Saga/Budget, Worker, regras de IAM, producer, FIDO, Quality canônica e provedores.

## Evidência / testes sem waiver

- **17 testes originais, copiados sem mudança** de `test_atlasquant_aion_chat_sqlite_lifecycle.py` do SHA #1195, executados no novo código (cross-thread real, tenant/fingerprint, rollback, session/logout, backup, close incerto, banco ausente/substituído, concorrência).
- **8 testes novos**: rerun entre threads com histórico persistido; low-level nativo rejeita cross-thread; legacy native em outra thread não pode ser silenciosamente removido; fachada não expõe API SQL/dispatch; backup STAGING chat-only funciona e tentativa de restore em ledger de execução permanece barrada; raw store thread owner não envenena health; modo PROD/PREVIEW continua negado; sessão mista com legado recebe preflight antes de qualquer revogação.
- **Testes canônicos existentes de host e storage resilience** são reexecutados **inalterados** no candidato, mais os **23 módulos raiz LAB** e matrizes IAM/S3/OneSignal/Twilio/Saga da linha.
- **O diagnóstico anterior #1347 permanece imutável** e deve continuar demonstrando a falha original; seu teste que explicitamente **espera a indisponibilidade** não é repetido na branch corretiva, onde passa a ser **substituído por testes de inversão**. Os contratos nativos dos 23 módulos permanecem, sem waiver/xfail/skip para alcançar verde. Histórico não é apagado.

## Limites de homologação

Este port **não confere identidade física, independência do produtor, ausência de efeito anterior, high-water externo ou restauração de executor após rollback**. Não acrescenta retry, processamento por Worker, interface comercial pública ou credenciais. Erro pós-commit exige reconciliação, nunca reenvio automático. Cabe aos revisores avaliar tempo/custo de criar e verificar uma conexão por chamada e possíveis problemas entre processos. A disponibilidade da UI de staging não significa H0 após reinício físico.

Antes de qualquer integração operacional, exigir revisão adversarial, CI Windows/Ubuntu, Quality/Security completas sem falsificação dos 32 ERROR Outbox/Saga, H0 físico e assinatura do proprietário.

**GO-LAB apenas após CI, HARD NO-GO sempre nesta etapa.**
