# A270 — Hardening de OHLC numérico gigante (LAB, 30/10/2026)

**Base:** A269 #1720, branch experimental isolada. **Sem merge, deploy, Worker, corretora, alertas, ordens, serviços pagos ou mudança de permissão.**

## Falha reproduzida

O verificador `_number` de `atlasquant_aion_trader_timeframes.py` chamava `math.isfinite(value)` em inteiros nativos arbitrariamente grandes. Em Python, `math.isfinite(10**1000)` lança `OverflowError` durante a conversão interna para float. Um candle malformado podia abortar a observação em vez de retornar `INVALID_OR_UNVERIFIED_TIMEFRAME_INPUT`.

## Correção

A270 verifica primeiro tipo numérico nativo e positividade; captura `OverflowError`/`ValueError` na verificação de finitude e rejeita o candle antes de qualquer promoção de cobertura. Não altera thresholds, rede, provedores, execução, UI nem contrato de 28 pares.

Dois testes adicionais (#26–27 em `labs/test_a269_trader_closed_mtf_evidence.py`): (1) inteiro `10**1000` em cada campo OHLC M5 recusa sem exceção nem cobertura; (2) M15 gigante não faz fallback ao M15 residente, mesmo quando este está fresco. Workflow A269 permanece responsável pelas regressões em Ubuntu/Windows; conferir o resultado do HEAD desta PR antes de afirmar PASS.

**Limites:** apenas uma classe de input adversarial foi endurecida. Candles suplementares continuam sem atestado externo, `mtf_coverage_is_external_attestation=False`. Nenhum dos 6 P0 foi homologado; **HARD NO-GO**, `UNCERTAIN=ZERO_AUTO_RESEND`. Negócios congelada apenas na visão read-only, Investimentos scaffold e Trader prioritário.
