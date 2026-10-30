# A271 — Números gigantes no residente e força de moedas (LAB 30/10/2026)

**Base A270 #1721; somente branch experimental draft.** Sem merge, deploy, Worker, ordens, alertas, contas externas ou custo.

## Falha localizada
A268 ainda chamava `math.isfinite(n)` diretamente em:
- série M15 `atlasquant_validated_market_items[*].series`;
- scores opcionais de força relativa das oito moedas.

Em Python, um inteiro nativo como `10**1000` gera `OverflowError` em `math.isfinite`. Assim, um input malformado interrompia a construção do painel em vez de perder sua alegação de atualidade. Não comprova proveniência adversarial no ambiente real; é um caso negativo do contrato de leitura.

## Correção e testes
Função pura `_finite_native_number` valida tipos `int/float` (sem booleanos), recusa não finitos e captura `OverflowError/ValueError`. Reutilizada por `_closed_series` e `_strength_context`. O limite já existente de score permanece ±1.000.000.

Os testes A268 #25–26 verificam que qualquer posição da série M15 com `10**1000` não vira `FRESH_CLOSED_M15`; força positiva/negativa gigante não cria direção e fica `UNAVAILABLE_OR_STALE`; ordens continuam impossibilitadas. Regressões A268/A269/A270, risco, capabilities, Trader residente e scanner FX28 rodam na mesma CI Ubuntu/Windows. Conferir resultado real no HEAD.

**Limites:** validação local não certifica fonte de dados. Negócios congelada apenas no read model, Investimentos scaffold, Trader prioridade. **P0 0/6; HARD NO-GO; UNCERTAIN=ZERO_AUTO_RESEND.**
