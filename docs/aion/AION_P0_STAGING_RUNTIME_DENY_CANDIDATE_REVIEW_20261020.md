# AION P0 — Contrato fail-closed para contexto de execução STAGING

**20/10/2026 — SOMENTE LAB / HARD NO-GO / 0/6 P0 homologados.**

## Relação com a auditoria anterior

O [PR Draft diagnóstico #1352](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1352) reproduziu sete limites de confiança na revisão pós-#1350: um fingerprint antigo pode voltar a ser apresentado, outra sessão/processo conserva seu handle independente, o lock do host é global por interpretador, e o `runtime_context` aceita flags positivas contraditórias. **GREEN nesses sete testes significa LACUNA OBSERVADA, não fechamento de P0.**

A correção deste candidato resolve **somente o problema local de flags de runtime**. Não tenta simular revogação, epoch, IAM, autoridade do HUMAN_OWNER ou recibo de fornecedor.

## Mudança mínima em STAGING

Em `atlasquant_aion_chat_host_staging.build_staged_host_binding`, antes de criar/reutilizar a conexão ou holder:

- Contexto explicitamente fornecido que não seja um `Mapping` agora é recusado com `TypeError`, em vez de trocar silenciosamente por defaults.
- Chaves `provider_enabled`, `network_enabled` ou `production_persistence`, se presentes, devem ser exatamente o booleano `False`; `True`, `None`, `0`, strings `"false"` e objetos hostis são todos recusados com `PermissionError`. Um campo ausente mantém a compatibilidade do host STAGING existente.
- Contextos legítimos podem preservar metadados de diagnóstico `lab_reference`, `checkpoint` e outros dados não relacionados a efeito.
- Nenhum novo token, segredo, chamada a provedor, envio, Worker ou autoridade é introduzido. O resultado continua `provider_called=False`, `network_called=False`, `external_action_executed=False`.
- Não altera `aion_chat/store.py`, `aion_chat/staged_store.py`, Saga/Outbox, asserções canônicas nem a correção de lock #1350.

## Evidência que conta / não conta

`tests/test_aion_p0_staging_runtime_context_denial_candidate_lab.py`: **12 testes normativos** de recusa antes de abertura do SQLite, flags falsas explícitas e default local, tipos malformados, sessão já existente preservada após tentativa proibida, negação de usuário/previews e disponibilidade normal de chat cross-thread. Esses testes **não substituem** os sete diagnósticos originais de #1352, porque um deles foi desenhado para **esperar a falha antiga**: roda apenas na branch anterior, não é apagado/xfail/waived.

A nova workflow branch-only executa Ubuntu+Windows com 12 novos, 12 normativos de atomicidade #1350, 17 testes históricos #1195, oito hardstops de guarda SQLite, 23 módulos LAB raiz e suites originais de chat/redteam + subconjunto original de segurança/isolation. A execução canônica completa da Quality (último baseline 51 FAIL+34 ERROR) e Security full **não** está incluída nem pode ser declarada GREEN.

## Limites inegociáveis

O patch **não prova revogação de fingerprint/epoch**, não impede logout de outro processo nem coordena custódia externa. Isso exige autenticação do emissor e high-water monotônico independentes (questão [#1351](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1351)); não fingir prova com relógio local ou hash da sessão. A serialização global ainda demanda avaliação de capacidade, e o P0 H0 exige ensaio real de power loss/WAL no Windows físico.

**32 ERROR Outbox/Saga `OPEN_NOT_WAIVED` permanecem; 0/6 P0 homologados, HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND. Sem merge, deploy, gasto, chaves ou envio externo.**
