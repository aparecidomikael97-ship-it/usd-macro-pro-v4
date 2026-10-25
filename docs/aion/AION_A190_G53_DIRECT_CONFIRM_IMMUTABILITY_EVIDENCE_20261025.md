# AtlasQuant / AION A190 — G53: confirmação direta local imutável e transição de fase segura

**Data:** 2026-10-25. **Status:** somente LAB, branch `lab/aion-a190-g53-direct-confirm-terminal-immutability-20261025`, [PR Draft #1541](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1541) empilhada sobre G52 Draft #1540. **NÃO** houve merge na main, deploy, Worker, interação com fornecedor financeiro, operações reais, credenciais, dados de cliente ou custo externo.

## Achado verificável e risco concreto

O método `ExecutionOutbox._confirm` só aplicava a validação local de fases e integridade do recibo quando `strict_reconcile_snapshot_cas_lab` ou `strict_binding_integrity_lab` estava habilitado. Se ambos os flags fossem falsos e não houvesse `fence_lab`/`reconcile_snapshot_lab`, era possível, em SQLite sintético:
- repetir confirmação de mesmo efeito e alterar `action_outbox.confirmed_at` enquanto o ledger mantinha o horário original;
- confirmar artificialmente estados `PENDING`, `CLAIMED`, `RETRY`, `FAILED`, `REVOKED` ou `BLOCKED_REAPPROVAL`;
- tentar reconstituir confirmação local sem ledger ou com timestamps contraditórios;
- aceitar ledger local presente em linha não confirmada, mascarando contradição histórica.

Não é prova de ocorrência real no mercado nem de autoria de fornecedor.

## Codex independente: somente leitura

No Windows autorizado, Codex CLI v0.164.0-alpha.11.1, modelo gpt-6.1-sol, sessão `01a173e2-6741-7af2-a9a7-c03eaff7efc0`, sandbox `read-only` e execução `--ephemeral`, confirmou estaticamente os caminhos com flags desativados e os riscos de compatibilidade com G41. Ele recomendou explicitamente **não** retornar sucesso idempotente antes de verificar `fence_lab` ou `reconcile_snapshot_lab`, pois isso enfraqueceria mecanismos já existentes. **Codex não escreveu código, não usou rede e não executou os testes.**

## Evidência RED → GREEN

1. Arquivo `labs/a190/test_g53_direct_confirm_terminal_immutability_lab.py` criado **antes** de qualquer correção do Outbox no SHA `52b8e445796df63903951840a52bd111dbf01232`. Execução real Windows no código anterior: **5/11 métodos aprovados, 6/11 falharam**; os subtestes por fase geraram **11 ocorrências de FAIL**.
2. Patch `atlasquant_aion_execution_outbox.py` no SHA `3b3064b2cc1d600718e3c870cd19484e421ddbd7`: o preflight de confirmação **direta sem fence/snapshot** passa a ser obrigatório independentemente das flags. `CONFIRMED` compatível retorna inalterado; recibo ausente/divergente causa `G42_CONFIRMED_LEDGER_INVARIANT_DENY`; estados fora de `UNCERTAIN`/`SENT` causam `G42_UNSAFE_PRECONFIRM_PHASE_DENY`; linha não confirmada com ledger causa `G53_NONCONFIRMED_HAS_EFFECT_DENY`. O gerenciamento de rollback continua transacional.
3. Com a mesma bateria: **11/11 GREEN**. A lógica especial para fence e snapshot continua separada, mantendo sua precedência de erro e transação.
4. A regressão histórica revelou que **seis arquivos de testes** preparavam recibos falsos diretamente de `PENDING` ou `CLAIMED`. Foram ajustados somente os fixtures/testes de G31, G33, G41, G44, G45 e G46 para transitar a `UNCERTAIN` antes da criação de um recibo local sintético. Os objetivos/asserts de idempotência, rollback, efeito órfão, escopo e predecessores foram preservados; nenhum comportamento inseguro foi reintroduzido para fazê-los passar.
5. Nova execução Windows de G30–G53 (G51 reunido na suíte G50) passou **463/463** em worktree isolado e limpo.

## CI reproduzível nos dois sistemas

**SHA exato do código+workflow testado:** `ab7c02705011a1090c4e4e213368d183175e30fd`.

[GitHub Actions #40212541223](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40212541223):
- Windows `121226686452` — **SUCCESS**, **463/463**.
- Ubuntu `121226686646` — **SUCCESS**, **463/463**.
- **926 execuções de 463 testes distintos**. Os logs de ambos os jobs contêm os marcadores `G53_RECONFIRM_GREEN`, `G53_TERMINAL_GREEN`, `G53_MISSING_LEDGER_GREEN`, `G53_CONTRADICTORY_LEDGER_GREEN`, `G53_ORPHAN_LEDGER_GREEN` e a regressão `G52_G42_LEGACY_STALE_GREEN`.

Este arquivo de relatório será adicionado **depois** do commit testado. O SHA novo do relatório não significa que a nova HEAD tenha sido retestada.

## Não comprovado / próximos requisitos

As correções G30–G53 continuam apenas verificações locais de estados e SQL com callbacks sintéticos. Ainda faltam identidade externa independente do HUMAN_OWNER, autenticidade/proveniência externa de recibos assinados, reserva da primeira tentativa com testemunha monotônica independente e proteção contra rollback de host, recuperação real H0 após reinício, proteção de identidade física SQLite e teste Security/Quality canônico completo. O histórico A184 Security e alertas de dependências não foi limpo por esta bateria.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**
