# AtlasQuant Trader — auditoria de fontes Forex intradiárias (LAB)

Data: 02/11/2026. PR #1803 DRAFT. HARD NO-GO. Sem deploy, merge, ordens, cron, Worker ou serviços pagos.

## Resultado da pesquisa

O BCE é uma fonte oficial para **referências diárias**, não fornece OHLC Forex M15/H1/H4. Para o estudo técnico dos 28 pares G8, as fontes abaixo foram consultadas em páginas dos próprios fornecedores:

| Fonte | Possibilidade técnica | Limite confirmado ou não comprovado |
|---|---|---|
| FXCM MarketData CandleData | Amostra pública com candles M1, H1 e D1 e timestamps descritos em UTC | Catálogo de amostras lista **21 pares**, insuficiente para 28; página indica uso pessoal e dados indicativos |
| FXCM MarketData TickData | Download histórico de ticks, lista de instrumentos mais ampla | Não presumir cobertura total G8/28 nem direito de redistribuição |
| Dukascopy Historical Data Export | Exportação CSV gratuita de tick a vários timeframes | Permissão comercial/republicação do **CSV** ainda não comprovada; contrato XML disponível é específico de outro produto |
| Twelve Data Basic | Histórico intradiário gratuito de Forex para avaliação | Termos do plano gratuito não autorizam assumir uso comercial/publicação |
| MetaTrader 5, via corretora | `copy_rates_range` obtém barras do terminal; M15/H1/H4 possíveis | Histórico limitado ao disponível no terminal/broker e ao máximo de barras; confirmar horário UTC, sessões e licenciamento |
| TrueFX | Oferta pública de histórico de ticks sem custo declarado | Contato oficial informa oferta somente para instituições e termos limitam disseminação; não contar com acesso pessoal |

## Links primários consultados

- FXCM CandleData: https://github.com/fxcm/MarketData/blob/master/CandleData/README.md
- FXCM TickData: https://github.com/fxcm/MarketData/blob/master/TickData/README.md
- FXCM termos: https://www.fxcm.com/uk/legal/website-terms-and-conditions/
- Dukascopy histórico: https://www.dukascopy.com/swiss/english/marketwatch/historical/
- Dukascopy licença XML específica: https://www.dukascopy.com/plugins/cont.php?ref_id=1273
- Twelve Data uso pessoal/comercial: https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage
- Twelve Data termos: https://twelvedata.com/terms
- MetaTrader 5 Python: https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py
- TrueFX disponibilidade: https://www.truefx.com/contact-truefx/
- TrueFX termos: https://www.truefx.com/truefx-terms-and-conditions/

## Decisão

Para pesquisa **pessoal e local**, a opção inicial é estudar exportações de candles M15 do terminal da própria corretora (inclusive MT5, se o proprietário o utilizar). Pode-se calcular H1 por 4 candles M15 e H4 por 16 candles M15, desde que fechem a mesma janela, com horário/broker de origem declarado; isso **não garante** equivalência ao H4 nativo de brokers com outro fuso/sessão.

Antes de usar uma amostra real, exigir:
1. Identidade e direitos do provedor, autorização para o tipo de uso; nunca copiar dados proprietários para repositório público sem licença.
2. Lista real dos 28 pares/símbolos, sem inventar cruzamentos ausentes.
3. OHLC, hora de abertura UTC, estado fechado da barra, timezone/DST e ausência de lacunas.
4. Spread/BID/ASK e definição do preço, se o objetivo futuro for backtest com custos.
5. Original local com SHA-256 e horário **efetivo** de coleta, sem alegar prova ex-ante a partir de captura posterior.
6. Separação cronológica treino/teste e verificação independente de disponibilidade antes da previsão.

## Situação

**Pesquisa concluída; fornecedor spot para os 28 pares ainda NÃO homologado.**
Nenhum CSV proprietário foi descarregado ou redistribuído neste commit.
Não existe gatilho intradiário validado, OOS real, taxa de acerto nem integração ao Radar.
UI aprovada preservada; projeto continua em LAB/HARD NO-GO.
