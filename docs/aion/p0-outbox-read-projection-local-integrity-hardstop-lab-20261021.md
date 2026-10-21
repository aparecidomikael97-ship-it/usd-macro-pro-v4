# AION P0/H0 — leitura do Outbox bloqueia decisões SQLite adulteradas (LAB)

**Data:** 21/10/2026. **HARD NO-GO · Worker OFF · ZERO_AUTO_RESEND · 0/6 P0 homologados.** PR Draft empilhada sobre #1399, não integrada à main.

## Problema confirmado

Em `atlasquant_aion_execution_outbox.py`, a função `claim_next()` já possuía verificação de JSON canônico, SHA-256 do material de idempotência e coerência de `action_decisions` com `action_outbox`. Entretanto, as projeções **`get()` e `list()`** executavam `json.loads(row["decision_data"])` e retornavam o objeto sem aplicar essas verificações. Um usuário/código com acesso à base SQLite local poderia modificar apenas a string JSON de `action_decisions.data` ou colunas de metadados e fazer consultas retornarem campos falsificados como se ainda representassem a decisão enfileirada.

Casos observados no LAB antes da correção incluem `grants_authority:true`, payload alterado, `authorization_ref` e `valid_until` adulterados, `decision_id` divergente, owner/tenant/workspace no JSON alterados, JSON não canônico, chave JSON duplicada e JSON inválido. O leitor original publicava o objeto adulterado ou lançava diretamente exceção de parser. Isso **não** prova que um envio externo ou aprovação ocorreu, nem exploração remota, mas cria dados locais não confiáveis para diagnóstico, recuperação e demais orquestradores.

### RED-first verificável

Os **24 cenários** de `tests/test_aion_p0_outbox_read_integrity_hardstop_lab.py` usam `SQLiteChatStore` e `ExecutionOutbox` reais, em arquivo temporário, sem adapter/Worker/provider. Antes do patch, no SHA `00ff2e4db31a1305e4e8753a6602ed1d36263f26`, [CI #39621970698](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39621970698) registrou no primeiro runner **19 FAIL + 1 ERROR em 24 testes**. Esse RED resulta de publicar campos adulterados ou vazar erros brutos de JSON.

## Correção em código de produto (ainda sem merge)

`_outbox_row()` e `list()` leem as mesmas colunas de decisão necessárias para comparar as projeções: `stored_decision_id`, `payload_digest`, `intent_ref`, `action`, `policy_version`, `authorization_ref`, `valid_until` e `created_at`. `_view()`:

1. Aplica o validador local existente `_local_decision_raw_integrity(row, scope)`: JSON canônico sem chaves duplicadas, `grants_authority=False`, schema/owner/tenant/workspace, cálculo de payload digest, digest da chave de idempotência e ID de decisão derivado da chave.
2. Verifica que os campos persistidos nas colunas SQLite correspondem à decisão interpretada pelo Python, e que o ID referenciado em `action_outbox` é exatamente o ID do documento.
3. Qualquer divergência, JSON inválido ou representação ambígua devolve explicitamente `PermissionError("OUTBOX_LOCAL_DECISION_INTEGRITY_MISMATCH")`.
4. **Não** omite silenciosamente uma linha corrompida de `list()`. Uma lista vazia poderia ser confundida com ausência de operação, insegura especialmente para H0; uma linha corrompida impede emitir uma listagem aparentemente confiável.
5. Leituras normais permanecem read-only; `claim_next` continua com sua lógica independente de CAS; `_confirm` e `reconcile` continuam bloqueados sem recibos reais de produtor. Nenhuma rotina concede autoridade a partir de JSON local.

## Limites

Este filtro só comprova **consistência local**, e apenas perante adulteração parcial: um atacante com controle total sobre SQLite, todos os campos de decisão e o estado histórico pode alterar dados e respectivos hashes coerentemente, reconstruir outras intenções ou reverter todo o banco. Validação de hash sem chave externa não autentica a origem, não fornece antirrollback, latest head, nonce externo, identity proof ou idempotência com fornecedor. A leitura normal devolve dados coerentes mas **não certificados externamente**.

A CI read-only específica executa **24 cenários novos + 165 testes anteriores por SO = 189 por SO, 378 execuções em Windows e Ubuntu** caso concluam PASS. Quality canônica original de 588 módulos/6.895 testes e Security A74 365 são reexecutadas no HEAD final **sem waivers, skips ou mudança de critério**. Histórico prévio: 6.810 PASS, 51 FAIL e 34 ERROR; a correção não deve ser contada como redução desses bloqueios sem evidência dos jobs.

**Sem merge, deploy, Worker, conta de provedor, APIs reais, efeito externo ou gasto adicional.**
