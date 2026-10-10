# AION — consolidação de segurança e reconciliação V2

## Resultado

**PARTIALLY_CLOSED / #1117 HARD NO-GO.** Consolidação local validada; nenhuma
nova PR/commit/push. Bloqueio do Autopilot preservado sem bypass. A correção dos
consumidores continua RAM por sessão; journal/CAS externo, reconciliação real e
isolamento autenticado multiempresa não foram implementados nem comprovados.

## Identidade, ancestralidade e preservação

Repositório: aparecidomikael97-ship-it/usd-macro-pro-v4; origin confirmado.
Worktree de integração: .codex-aion-consolidation-v2-20261009.
Branch: codex/aion-consolidation-reconciliation-v2.
HEAD inicial/final e base de aplicação: 5a064ca4b0a6cdc28d62d5e1ccf9a1383a5a4473.
Base comum das linhas remotas: ded414b10e393f1ff7dd6cdba57fc6062c247c5e.

GET das três PRs confirmou OPEN/DRAFT, merged=false e os HEADs solicitados:

| Linha | HEAD | Parent/base efetivamente confirmado |
|---|---|---|
| #1156 | 5a064ca4b0a6cdc28d62d5e1ccf9a1383a5a4473 | ded414b10e393f1ff7dd6cdba57fc6062c247c5e |
| #1161 | 141c609d021cca7625395b4748342a9a51cfa555 | ded414b10e393f1ff7dd6cdba57fc6062c247c5e |
| #1162 | e4f931444efb923eede08c416fadd7f6e02f4aa9 | 141c609d021cca7625395b4748342a9a51cfa555 |

Não presumimos que #1162 inclui #1156: merge-base local comprovou ded414b.
Não fizemos merge/cherry-pick/commit. Aplicamos os sete arquivos staged locais
sobre #1156 e os deltas de #1162 sobre a base comum; workflow reconciliado por
união de paths/compile/tests, preservando os checks anteriores.

Worktree original codex/aion-unknown-outcome-consumers: sete staged, zero
unstaged, HEAD 5a064ca. Hash do diff staged antes/depois:
145927c5e5adea3124ac0db5e751a8feecbb44182864899cf1c9fe0a47a39908.
O clone anterior codex/aion-1155-closure-audit também foi preservado: árvore staged
6509b339715f529818a9e25d9dde9ffec6ef99d1. Sem reset/clean/stash/force-push.
Core V1 e cadeia Developer/Security congelados não receberam alterações.
O novo contrato lê Context; não modifica nenhum arquivo do Core.

## Inventário das linhas e conflitos

- #1156: 11 arquivos — decoder/readback, três stores JSONL, Budget, dois testes
  raiz, novos testes de fechamento, runner offline, workflow e relatório.
  F1 conteúdo ausente; F2 binding de bytes raw/SHA; F3 retry409/422 continuam intactos.
- #1161: workflow, guard por processo, caller Autopilot, teste e documentação.
- #1162: substitui o guard e seu teste por negação incondicional, adiciona relatório
  de admissão durável. O runtime antigo de #1161 é SUPERSEDED; não foi reintroduzido.
- Local: sete arquivos listados abaixo foram copiados integralmente antes dos
  acréscimos de integração. Relatório anterior preservado como histórico.
- Sobreposição: workflow de CI. Não houve conflito nos stores/captures ou Core.
  Nenhum arquivo atual foi substituído por sua versão mais antiga.

## Correções consolidadas

1. UNKNOWN_OUTCOME/reconciliation_required permanecem em PENDING_KEY separado;
   duplicação local, nova captura, persist=False, batch, hidratação e alteração
   do status/retorno não apagam a pendência conhecida. Captura local continua possível.
2. LOCAL_ALREADY_PRESENT/source=session/persistence_confirmed=false distinguem
   memória local; confirmação SAVED requer flags de SHA/readback e scope de lote.
3. Admin informa a pendência e bloqueia o botão; chamada direta ao serviço também
   bloqueia. Presença remota por ID não é confirmação integral.
4. Autopilot usa guard #1162 para Shadow e Flight separadamente. HARD_DENY em
   qualquer processo; nenhum writer, builder ou callback executado após negação.
   Payloads são construídos dentro do callback negado, não antes do gate.
   Exceções expõem somente a classe, nunca detalhe/token/conteúdo. Sem flag de bypass.
5. Contrato puro de referência vincula conteúdo exato a operação/semantic_id,
   scope fechado e geração. Mesmo match mantém PENDING_RECONCILIATION. Nenhum
   journal novo, serviço, CAS concorrente, infraestrutura ou autorização real.
6. Fixture histórica Shadow corrigida com SHA Git calculado e GET readback
   válido; exige verified, readback correspondente, dois GET e um PUT. Não há skip
   nem aceitação de bare201. Nova regressão de isolamento usa duas sessões locais.

Projeto técnico completo: AION_EVIDENCE_DURABLE_RECONCILIATION_V2_DESIGN.md.
Ele especifica intenção antes do send, CAS/fence global, high-watermark independente,
crash/rollback, read-only reconcile, prova causal de resultado, aprovação distinta,
revogação e isolamento. Reutiliza as referências reais já presentes no repositório.

## Testes executados

`python -B scripts/aion1155_closure_audit.py`: **341 testes PASS**, 17,873s.
Os 190 testes anteriores foram preservados. Incluídos: novo isolamento de sessão,
16 testes do guard #1162, 20 testes de integração/contrato/processos, 85 testes
das quatro referências journal/dual-witness/reconciliation/SQLite-CAS, dez testes
Shadow Persistence e 19 Shadow Mode. Flight/store/Research permanecem nos testes
herdados, com funções reais dos stores e transporte sintético.

Cobertura: timeout depois de PUT, 201 sem SHA/readback, SHA incorreto, duplicate,
nova captura, persist=False, reidratação/cache vazio, batch, troca de scope,
reinício do guard em processo Python novo, reinício do journal após UNKNOWN,
dois processos reais disputando um claim SQLite de fixture, threads/callers
concorrentes, reexecução do Autopilot, corrupção/rollback, ausência de testemunha,
falha de comunicação e impossibilidade de autorização implícita.

A suíte histórica Shadow agora tem **10/10 PASS**. Antes da correção de fixture,
1/10 falhava igualmente na base #1156 e no patch local; o decoder não foi afrouxado.
Os testes de rollback incluem controles negativos: restaurar journal e heads
antigos juntos pode passar matemática; SQLite e assinatura não viram autoridade.

Cinco auditores CLI também passaram, sem tráfego:
- 21/21 status de writes, 14 arquivos, zero findings;
- 28/28 status de GET, 12 arquivos, zero findings;
- 28/28 URL/no-redirect de GET, zero findings;
- 21/21 destinos/no-redirect de write, zero destinos desconhecidos;
- 587 Python de produção: dois POSTs pagos hard-denied, zero violações reconhecidas.

Compilação em memória dos Python do diff e git diff --cached --check: PASS.
Runner bloqueia HTTP/socket não mockados e retira credenciais herdadas. As chaves
Ed25519 são descartáveis das fixtures; subprocessos Python testam somente código
puro/SQLite temporário, sem probe físico ou serviço operacional.

Não executado: UI Streamlit completa; suites amplas com pandas/Streamlit ausentes;
root test_autopilot_v107.py (exige pandas e contém expectativas antigas de writes
bem-sucedidos, agora incompatíveis com HARD_DENY; nenhuma proteção foi afrouxada
para atendê-las); loopback HTTP/TLS; rede de provider; máquinas remotas; hardware,
TPM/FIDO2/antirollback físico; CI remoto deste patch. Nenhuma dependência instalada.
O novo teste AST executa o caller real do Autopilot sem importar/iniciar o Worker.

## Riscos e classificação

- HIGH: pendência dos captures não é persistente; outra sessão/processo pode
  perder o marcador. Store direto fora do Autopilot não possui admissão durável.
- HIGH: não há matrícula/recibo causal/head fresco independente, CAS protegido
  multi-host ou protocolo atômico de recuperação. Operações antigas não foram resolvidas.
- HIGH: consumidores legados usam repo/branch e chaves de sessão comuns, sem
  Context autenticado por tenant/task. Duas sessões são isoladas no teste; troca
  de empresa/contexto dentro da mesma sessão ou repo multiempresa não foi validada.
  Binding de referência rejeita swap, mas ainda não integra a fronteira autenticada.
- HIGH: check/write dos captures não é claim atômico global. Concorrência do
  Autopilot é segura por negação total, não por admissão durável.
- MEDIUM: ID-only dedup dos stores não compara corpo integral; source SHA/readback
  não prova origem independente/durabilidade/causalidade de uma operação antiga.
- MEDIUM: captura fica em quarentena sem API válida para retomada; disponibilidade
  limitada é deliberada. Não liberar limpando sessão/config ou usando receipt antigo.
- Limite estático: nenhuma prova de resistência a monkeypatch/dependência maliciosa,
  JS/TS/shell ou egress dinâmico arbitrário. Não confundir AST verde com isolamento físico.

Portanto **PARTIALLY_CLOSED**. Corrigimos perda sequencial conhecida e consolidamos
negação do Autopilot; produção durável e reconciliação comprovada permanecem abertas.
#1117 continua HARD NO-GO. Sem merge/deploy/Worker/instalação/credenciais reais,
am12/Windows físico, provider pago, despesas, publicação de código ou alteração de main.

## Arquivos do diff relativo à #1156 (17)

- .github/workflows/aion-v2-github-write-explicit-status.yml
- atlasquant_admin_research_panel.py
- atlasquant_aion_v2_autopilot_evidence_guard.py
- atlasquant_aion_v2_evidence_reconciliation_contract.py
- atlasquant_research_evidence_capture.py
- atlasquant_shadow_capture.py
- autopilot_v107.py
- docs/aion/AION_CAPTURE_RECONCILIATION_AUDIT_2026-10-09.md
- docs/aion/AION_V2_AUTOPILOT_DURABLE_ADMISSION_REQUIRED_V1.md
- docs/aion/AION_V2_AUTOPILOT_EVIDENCE_QUARANTINE_V1.md
- docs/aion/AION_EVIDENCE_DURABLE_RECONCILIATION_V2_DESIGN.md
- docs/aion/AION_SECURITY_CONSOLIDATION_V2_AUDIT_2026-10-09.md
- scripts/aion1155_closure_audit.py
- test_atlasquant_shadow_persistence.py
- tests/test_atlasquant_aion_v2_autopilot_evidence_guard.py
- tests/test_atlasquant_aion_v2_evidence_consolidation.py
- tests/test_atlasquant_capture_reconciliation.py

Patch incremental: ../AION_SECURITY_CONSOLIDATION_V2_FROM_1156_2026-10-09.patch.
Patch completo desde base comum (inclui #1156):
../AION_SECURITY_CONSOLIDATION_V2_FROM_1155_2026-10-09.patch.
Nenhum commit ou PR de consolidação foi criado. O HEAD é a base, não a árvore com patch.
