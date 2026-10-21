# AION P0/H0 — falso recibo de adapter não é autorização de produtor (21/10/2026)

**LAB isolado · HARD NO-GO · 0/6 P0 homologados · ZERO_AUTO_RESEND · Worker OFF.**

## Ponto de partida
A Quality completa da [PR #1390, commit `1fb85413654d1427088dd5d28f3346146352b575`](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39595920015) registrou **6.895 testes; 50 FAIL + 27 ERROR**, incluindo 18 ocorrências de erro Outbox e 9 Saga. A recusa `INDEPENDENT_PRODUCER_NOT_ENROLLED` não é um defeito a remover: o executor não dispõe de vínculo autenticado com o produtor do efeito, prova de primeira tentativa nem histórico independente que atravesse rollback.

## Cinco contratos Outbox históricos corrigidos na suíte (e só nela)

Preservados os nomes originais, classes, métodos e as entradas históricas da matriz de 85 ocorrências e da auditoria de 32 casos. Nenhum código operacional foi editado.

| Método | Novo critério estrito |
| --- | --- |
| `test_unverified_positive_from_send_must_not_record_real_effect` | Adaptador com resposta `accepted=True/confirmed=True` **não pode sequer receber send** antes da matrícula independente |
| `test_unverified_positive_from_reconcile_must_not_record_real_effect` | Um estado `UNCERTAIN` montado em SQLite temporário não autoriza consulta de adapter, não valida recibo nem libera nova tentativa |
| `test_existing_unverified_negative_remains_quarantined` | Mesmo `accepted=False` não serve de fence; pré-envio retorna bloqueio de fornecedor e não chama callback |
| `test_private_confirm_is_closed_without_independent_producer_receipt` | `_confirm` negado em `CLAIMED` **e** `BLOCKED_PRODUCER`, antes/depois da tentativa de dispatch |
| `test_fake_positive_cannot_release_followup_same_aggregate` | Recibo falso não libera ação dependente da mesma sequência; primeiro fica `BLOCKED_PRODUCER`, segundo `PENDING` |

**Todos** exigem zero efeitos no ledger e zero chamadas de envio de adapter. O cenário de `UNCERTAIN` histórico usa somente SQL temporário de fixture, sem efeito externo e sem conferir autoridade. A correção destes contratos negativos **não substitui** testes futuros da recuperação positiva sob recibo genuíno de fornecedor.

## Limitações e riscos preservados

- Nenhuma prova independente de não efeito tardio, custódia de nonce, raiz de confiança do emissor ou revogação atual.
- `BLOCKED_PRODUCER` mantém a fila da mesma entidade sem reenvio automático, mas não prova durabilidade diante do rollback do SQLite inteiro.
- Um PASS na CI específica indica somente compatibilidade com a restrição atual e estabilidade do histórico; não comprova implantação, homologação ou disponibilidade H0.

## Evidência que precisa ser conferida

Workflow isolado Ubuntu/Windows `aion-p0-outbox-untrusted-adapter-hardstop-lab.yml` executa os 5 métodos migrados, 6 controles de recusa pré-adapter já existentes, inventário de 85 casos (12 testes), matriz de 32 erros (10 testes) e negação causal A79 (64 testes): **97 testes selecionados por SO**. A Quality canônica completa também é disparada na branch, sem filtros novos nem skip. Verificar no SHA final, comparar métodos individuais de FAIL/ERROR e reconhecer que reduções refletem migração de expectativas antigas, não eliminação da falta de fornecedor real.

**Sem merge, deploy, Writer, Worker, gastos novos ou fornecedor. Nenhum P0 fechado.**
