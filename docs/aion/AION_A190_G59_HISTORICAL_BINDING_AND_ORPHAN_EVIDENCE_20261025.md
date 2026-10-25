# AION A190 — G59 historical decision binding consistency (LAB)

**Data:** 2026-10-25. **Branch:** `lab/aion-a190-g59-historical-binding-orphan-deny-20261025`; **PR Draft:** [#1545](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1545), base G58 Draft #1544, **não main**.

## Pergunta verificável

A G58 verificava documentos históricos por tenant, rejeitando JSON malformado, campos sem tipo correto, reserva antiga ausente e mesma identidade declarada em outro intent. Porém o pré-flight aceitava **JSON semanticamente alterado**, com identificador de evento histórico mudado/removido, se ainda fosse JSON sintaticamente válido. Duas requisições poderiam então coexistir na Outbox local. Isso não é prova de dois efeitos financeiros externos.

## RED reproduzido, testes antes da correção

1. Novo arquivo `labs/a190/test_g59_historical_binding_orphan_lab.py` criado primeiro em `c71f14776d39d787782ea7c259edbecc48cef019`, sem alteração do motor. Inicialmente 10 testes: **5 falhas**. Ao auditar o resultado, uma era interpretação equivocada de erro: Outbox órfã já era recusada por `SQLiteChatStore.require_healthy()` via `foreign_key_check`. Outros dois testes inicialmente exigiam erro G59 onde a colisão G58 já bloqueava corretamente.
2. Corrigidas apenas as expectativas/fixtures em `7c85e36aac59e010d0bbda78e07efa39f873a2f9`: **10 testes, 6 PASS / 4 FAIL REAIS** antes do patch. (a) renomear evento no JSON; (b) remover o evento; (c) adulterar idempotency_key do documento; (d) alterar digest na coluna persistida; todos podiam passar sem verificação estrutural completa ao tentar evento independente.
3. Motor corrigido em `96425522bfab6e0bba1dcc9192b7fda12a7f0565`: vincula hash do payload, colunas persistidas e JSON histórico antes de aceitar ausência de colisão, sempre na mesma transação SQLite. **10/10 GREEN**, herdadas G58/G57/G47/G39 também GREEN.
4. Duas provas mais fortes acrescentadas **antes de uma segunda correção** em `8de41b1da2ad1a6ea4bf4f93e3f16d76e63d9673`: invasor sintético altera o evento e recalcula simultaneamente digest JSON/coluna, sem alterar inicialmente o semantic ID; depois altera também semantic ID. **10/12 PASS, 2 FAIL RED**. O digest local sozinho não bastava.
5. Correção adicional em `c16bcaac92c671dae00454cbace28abf3fae69ce`: exige vínculo exato entre `payload.business_event_id` e `semantic_event_id_lab` quando declarado, recompõe `key_material` histórico (escopo, ação, aggregate, digest, transaction, budget, risk, capability, semantic e reauth), confere SHA-256 da chave e a derivação do `decision_id`. **12/12 GREEN**, mantendo tenant isolation, idempotência real da mesma declaração e não reparando histórico corrompido.

## Matriz local / CI

- `labs/a190/test_g59_historical_binding_orphan_lab.py`: **12/12** Windows.
- Herdadas G58 16, G57 10, G47 18, G39 28 e demais regressões G30–G58: verdes no isolamento Windows.
- Workflow `.github/workflows/aion-a190-g59-historical-binding-lab.yml`, exato SHA de código e testes `0383ef41561a34f5a886b3ddaad822cfd19eb61c`, Ubuntu + Windows.
- **Windows local:** G30–G59 **529/529 PASS**, exit code 0, checkout limpo no SHA `0383ef41561a34f5a886b3ddaad822cfd19eb61c`.
- **CI multiplataforma VERIFICADO:** [GitHub Actions #40218291656](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40218291656) executou o exato SHA de código/workflow **`0383ef41561a34f5a886b3ddaad822cfd19eb61c`**. Ubuntu job `121244102534` **SUCCESS 529/529**; Windows job `121244102841` **SUCCESS 529/529**. Os logs foram lidos, contagens conferidas e marcadores de adulteração simples e coordenada encontrados em ambos. **1.058 execuções de 529 testes distintos**, além da bateria Windows local. O relatório foi escrito após o SHA testado; não substituir SHA de código pela revisão documental.

## Codex independente (real, somente leitura)

Codex CLI Windows v0.164.0-alpha.11.1, model gpt-6.1-sol, `-s read-only --ephemeral`, sessão `01a1742e-4df1-75c1-89db-fd4f79e1c9b9`, analisou o **patch real G59**, sem executar testes, editar ou usar rede. Confirmou estaticamente os dois guardrails coordenados e o bloqueio anterior de FK para Outbox órfã.

O Codex ressaltou **riscos remanescentes não resolvidos**:
- Compatibilidade de históricos de versão anterior não comprovada; o scan fail-closed pode bloquear inclusive novos eventos distintos em um tenant com registros antigos não conformes.
- Serialização canônica pode admitir `NaN` em algum payload, mas parser histórico estrito recusa; `1e999` em campo JSON auxiliar também pode converter para infinito. Requer testes e correção próprios em LAB antes de qualquer promessa de disponibilidade.
- O scan é acionado só para novas admissões com `semantic_event`; o fluxo legado sem `business_event_id` permanece fora desse controle.
- Reescrita coordenada de todos os arquivos, decisões, chaves e reservas por agente com acesso ao host não é combatida por hashes originados no mesmo banco. Também faltam fonte externa confiável e custódia monotônica.

## P0/H0 — nunca confundir proteção local com homologação

G59 não comprova HUMAN_OWNER genuíno, autenticidade de recibo externo, first-send remoto idempotente com resultado desconhecido, deduplicação de duas identidades distintas da mesma obrigação econômica, sobrevivência a rollback físico, custódia fora do host, disponibilidade H0 após reinício ou Security/Quality canônica. Achados anteriores em dependências merecem auditoria específica.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. Sem merge, deploy, Worker, fornecedor externo, dados de cliente, gastos, fundos ou segredos.**
