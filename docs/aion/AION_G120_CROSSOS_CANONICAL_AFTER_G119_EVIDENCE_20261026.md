# AION G120 — Verificação canônica original em Windows e Ubuntu após G119

**Data:** 2026-10-26. **PR Draft:** #1614, sobre G119 Draft #1613. **Escopo:** workflow de validação apenas; nenhum código de produção, teste original ou filtro de Security alterado. **0/6 P0 HOMOLOGADAS, HARD NO-GO.**

## Fonte

Código G119 testado: `cb646dd59ee1f97342ca5bdb24e0b9fa640e365d`. G120 workflow-only commit: `a066997c150eb93ca36b6162a153505703917cd1`.

Usou `scripts/run_a183_canonical_lab.py`, que extrai os seletores Quality e Security dos workflows canônicos originais. Dependências fixadas em `requirements.txt`, auditadas com pip-audit sem supressão de advisories e Bandit original. Os testes G119 com 12 novos cenários já haviam passado nas matrizes Windows/Ubuntu em [G119 run 40410645669](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40410645669).

## CI objetivo: seis jobs SUCCESS

[GitHub Actions G120 40411001756](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40411001756):

| Verificação | Ubuntu | Windows |
| --- | ---: | ---: |
| Quality canônica | **6449/6449 PASS**, 74,667 s (job `121881363350`) | **6449/6449 PASS**, 159,384 s (job `121881363203`) |
| Security unittest | **368/368 PASS** (job `121881363218`) | **368/368 PASS** (job `121881362873`) |
| Security pytest | **2825 PASS** (job `121881363218`) | **2824 PASS + 1 SKIP histórico** (job `121881362873`) |
| pip-audit + Bandit | **SUCCESS; No known vulnerabilities found** (job `121881363200`) | **SUCCESS; No known vulnerabilities found** (job `121881363265`) |

Todos os jobs também informaram `No broken requirements found`. Os avisos ausentes são o resultado pontual do banco de vulnerabilidades e pins no dia da execução, não uma garantia permanente. O teste ignorado em Windows **não deve** ser contado como teste aprovado.

## O que o teste demonstra — e o que NÃO demonstra

G119 estabelece duas categorias de evidência sintética diferentes: uma assinatura de reserva pelo testemunho local e outra assinatura de claim do 'provedor' de TESTE. Os dois domínios, as duas chaves, o nonce de uso único e o vínculo de identidade da operação foram validados nos testes G119. Um claim `EXECUTED` que passe na assinatura de teste NÃO é um recibo de execução externa. O modelo devolve sempre `verified_real_provider=False`, `provider_outcome=UNKNOWN`, `allow_send=False`, `allow_retry=False` e `may_mark_provider_confirmed=False`.

A proteção não resiste a administração privilegiada do host: a mesma máquina controla as duas chaves sintéticas, o ledger SQLite e a origem do evento. O teste herdado `G115_HOST_CONTROLLED_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0` continua deliberadamente demonstrando que rollback da própria custódia reabre a reserva. Nenhuma evidência de autoridade externa, native SQLite VFS, aprovação HUMAN_OWNER, garantia de first SEND ou operação com fundos foi obtida. Os cinco requisitos reais A184 continuam pendentes; não foram reexecutados/dispensados nesta PR.

**0/6 P0 HOMOLOGADAS · HARD NO-GO · PR Draft · sem merge/deploy/Worker/SEND real/fundos.**
