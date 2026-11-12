# AtlasQuant Trader — shortlist USD/EUR de futuros de juros, pesquisa 2026-11-10

**LAB apenas: sem cotações autenticadas, sem compra de acesso, sem integração ativa, sem viés.** Complementa `TRADER_EURUSD_FUTURES_30D_VS_3M_BASIS_PILOT_20261110.md`.

## Novo achado: selecionar bases mais próximas antes de qualquer normalização

| Alternativa | EUA | EUR | Melhor aspecto | Bloqueio |
|---|---|---|---|---|
| Piloto inicial | [CME ZQ: Fed Funds mensal](https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund/specs) | [Eurex FST3: €STR 3 meses](https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures) | Contratos bem definidos | **30 dias aritméticos versus 3 meses compostos; vetar comparação direta** |
| Alternativa A: janela de 1 mês | [CME ZQ](https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund/specs) | [ICE EON: One-Month €STR](https://www.ice.com/products/37650328/One-Month-ESTR-Index-Futures) | Ambos têm **média aritmética diária no mês** e índice 100-taxa; períodos mais próximos | Fixings distintos (EFFR vs €STR), calendário, horários, licença, preços e **liquidez ICE EON não demonstrada** |
| Alternativa B: janela de 3 meses | [CME SR3: SOFR 3M](https://www.cmegroup.com/markets/interest-rates/stirs/three-month-sofr/specs) | [CME ESR: €STR 3M](https://www.cmegroup.com/markets/interest-rates/european-overnight-index-futures.html) | Ambos **juros overnight compostos trimestrais**, negociação na mesma CME e vencimentos IMM; possível alinhamento temporal melhor | SOFR é taxa repo garantida, €STR é empréstimo sem garantia; basis/correções/visibilidade, liquidez ESR e direitos ainda não demonstrados |

**Atenção:** a página pública da [ICE EON](https://www.ice.com/products/37650328/One-Month-ESTR-Index-Futures/data?marketId=6852792&span=1) exibiu contratos sem últimos preços e **volume 0** no quadro datado de 04/11/2026. Isso não comprova ausência universal de mercado, mas **bloqueia** usar essa tabela como snapshot negociado.

A [CME](https://www.cmegroup.com/markets/interest-rates/european-overnight-index-futures.html) lista o contrato EUR como **ESR**; [SR3](https://www.cmegroup.com/markets/interest-rates/stirs/three-month-sofr/specs) como futuro americano sobre SOFR. Mesmo com janelas próximas, **diferença entre taxas de referência e bases econômicas** impede subtrair os dois valores como previsão de alta/baixa do EURUSD.

## Critérios mínimos para próximo passo — não ampliar só por ter contrato

- Autenticar **duas observações reais** de cada contrato escolhido, mesmas datas de corte e vencimento/janela de referência compatíveis, com contract ID, preços, moeda, unidade, timezone, volume e hora da primeira divulgação/captura.
- Verificar *permissões de coleta e reutilização*, atraso/latência, valor de spreads e qualidade de bid/ask; nenhum cadastro pago ou custo novo sem autorização.
- Calcular variação **dentro de cada contrato** somente se não houve mudança/rolagem; não dar nota direcional transmoeda sem ajuste de basis, efeito dos fixings já conhecidos e validação retrospectiva point-in-time.
- Comparar 1 mês e 3 meses por disponibilidade/liquidez verdadeira. Não presumir que ESR seja líquido a partir da descrição de marketing.
- Rodar pesquisa apenas com dados que o agente poderia conhecer naquele instante, com corte conservador. **Resultados históricos conhecidos hoje não podem ser usados como se estivessem disponíveis ontem.**
- Se nenhuma fonte passar, manter `AGUARDAR` e focar sinais macro verificáveis, sem custos.

## Estado
**Nenhuma nova série de preços recebida. Nenhum contrato considerado comparável para operar.** O guardião `atlasquant_trader_eurusd_futures_basis_guard_lab.py` continua bloqueando USD ZQ versus EUR FST3. Pesquisa registra alternativas para teste **futuro**, não altera sinal nem sistema vivo.
