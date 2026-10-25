# AtlasQuant / AION A190 G52 — reconciliação com snapshot local incondicional

**Data:** 2026-10-25. **Branch:** `lab/aion-a190-g52-reconcile-default-snapshot-cas-20261025`. **PR Draft:** [#1540](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1540), empilhada sobre G51 Draft #1539. **HARD NO-GO, 0/6 P0 homologados.**

## Limite de confiança

O trabalho corrige consistência **local e sintética** entre o estado `UNCERTAIN`/`SENT` e um callback de reconciliação. **Não prova** identidade HUMAN_OWNER externa, assinatura/autenticidade de recibo de fornecedor, testemunha externa monotônica, recuperação resistente a rollback físico, disponibilidade H0 após reinício ou execução única garantida pelo fornecedor. Nenhum Worker, deploy, merge na `main`, operação financeira real, cliente, segredo ou custo externo foi utilizado.

## Duas revisões reais do Codex

- Primeiro: Codex CLI no Windows, modo `read-only` e `--ephemeral`, identificou por inspeção estática que `strict_reconcile_snapshot_cas_lab=False` deixava `snapshot_lab=None`, permitindo retornar resultados defasados e admitir certas confirmações locais após mudanças reentrantes.
- Segundo: Codex CLI v0.164.0-alpha.11.1, session `01a173de-48e8-7141-a4a4-5ef150a78a08`, no checkout G52 em modo somente leitura, confirmou que a quarentena padrão continua bloqueando consulta ao adapter, autorização e verificador. Observou três lacunas ainda **não resolvidas**: cobertura isolada de callback de autorização/verificador que não deve executar, exceções por falha de armazenamento na releitura `get()`, e `_confirm()` chamado **diretamente** com ambos os flags estritos desligados. Codex não editou arquivos nem executou testes em nenhuma dessas revisões.

## RED reproduzido antes da correção

1. Arquivo `labs/a190/test_g52_reconcile_default_cas_lab.py` criado primeiro no SHA `391c9fcb429c1c84d3b4863894fb5e3548323e66`.
2. A primeira execução tinha um erro **no teste**, sem campos ordinários `policy_version` e `authorization_ref`. Os 10 casos paravam na autorização: **isso não é prova da vulnerabilidade**. Corrigido somente o fixture no SHA `4a3fa13ed0c7471b191cb0c84ad8df483cf9d59f`.
3. Nova execução Windows sobre código ainda sem correção: **10 testes, 2 PASS / 8 FAIL**. Falhas reais incluíam retorno obsoleto `UNCERTAIN` após confirmação, confirmação local de operação revogada, mudança de geração/lease não detectada e sobrescrita sintética da data de confirmação.

## GREEN e testes históricos

- SHA de código `b6fe38456c2ed79e60d6d76dbe612c765dd8f1fb`: `reconcile()` captura e verifica snapshot local mesmo com o opt-in CAS histórico desligado; passa snapshot à validação transacional `_confirm()`; após autorização negada por callback reentrante, não retorna a fotografia antiga caso o estado tenha mudado.
- G42 teste 18, anteriormente `G42_LEGACY_STALE_RED` intencional, atualizado em `cef7d880a54dd12a0c853ea718e0334aad17cfc6` para exigir `G42_STALE_REPLY_NO_WRITE`, registro CONFIRMED preservado e único ledger.
- No checkout Windows isolado `C:\Users\apare\AtlasQuant-G52-Reconcile-LAB-20261025`: **G52 10/10 GREEN**, bateria herdada G30–G50 **442/442 GREEN**, total **452/452**; `git status` limpo.

## CI verificado em dois sistemas

O código + workflow foram executados no exato commit **`b887e8d38f58e8e691cc91f2ddc20009423215d4`**. [GitHub Actions #40211276956](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40211276956):
- Ubuntu job `121222823085`: **SUCCESS**, 452 testes.
- Windows job `121222822892`: **SUCCESS**, 452 testes.
- Total **904 execuções**, mas apenas **452 casos distintos**, com suíte herdada. Marcadores de revogação, negativa obsoleta, timestamp imutável, reentrância na autorização e regressão G42 confirmados nos logs de ambos.

O documento de evidências será acrescentado **após** o commit testado; seu SHA posterior **não** deve ser usado como prova de execução de novo código. A184 Security e `pip-audit` (vulnerabilidades históricas em pypdf/Pillow) não foram rehomologadas por estes checks específicos.

## Próximas lacunas objetivas — sem homologação

- **G53 candidato:** auditar `_confirm()` direto quando flags de integridade/CAS estão desligados, recusando alteração de `CONFIRMED`/`REVOKED` e mantendo timestamp original.
- Testar indisponibilidade de armazenamento durante releituras de `reconcile`, com tratamento fail-closed sem afirmar ausência de efeito externo.
- Resolver testemunha independente, autenticidade de recibos e proteção física/antirollback dos seis P0. Testes locais não substituem esses requisitos.

**0/6 P0 · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. Sem merge, deploy ou operações reais.**
