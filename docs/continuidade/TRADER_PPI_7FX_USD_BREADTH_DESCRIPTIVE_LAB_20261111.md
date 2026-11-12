# AtlasQuant Trader — amplitude da reação do USD nos sete pares após o PPI (LAB)

**Data do protocolo:** 11/11/2026. **Evento futuro:** PPI dos EUA, referente a outubro/2026, publicação programada para 13/11/2026 às 13h30 UTC (09h30 Mato Grosso).

## Objetivo

O estudo já mede a variação de cada um dos sete pares Forex em relação ao candle-base anterior ao PPI, normalizando a direção do preço para **movimento relativo favorável ao USD**. Ainda faltava resumir **quais pares apontam na mesma direção e quais discordam**, sem transformar um estudo posterior em previsão.

Criado `atlasquant_trader_ppi_fx_breadth_lab.py` e integrado à etapa consolidada `atlasquant_trader_ppi_one_event_study_join_lab.py`. O módulo recebe **somente o relatório já validado de variações M15/H1/H4**: ele não faz I/O, não lê preços ou comprovantes diretamente, não acessa MT5 e não autentica o fornecedor. Por isso é invocado pelo estudo consolidado **somente depois** da conferência dos documentos originais, manifesto do MT5, sete CSV M15 e contexto de spread.

## Métricas descritivas

Para cada janela fechada **+15, +60 e +240 minutos**, calcula com `Decimal`:

- Contagem exata de pares cujo preço normalizado indica variação favorável ao USD, desfavorável ao USD ou valor arredondado a **0,00 pontos-base**;
- Identificação explícita dos símbolos em cada grupo, sem ranking de probabilidade;
- Mediana entre sete variações normalizadas e amplitude `max - min`, ambas em pontos-base reportados;
- Padrão documental de unanimidade positiva, unanimidade negativa, todos zeros arredondados, sinais mistos ou combinação de sinal e zero;
- Lista de pares cujo **sinal no fechamento +15 minutos difere do sinal no fechamento +4 horas** (excluindo zeros arredondados).

As sete observações vêm do **mesmo evento econômico** e das **mesmas janelas**. Elas não equivalem a sete previsões independentes, sete oportunidades nem sete acertos. Contagens de sinais não são um estimador causal de um fator USD, nem uma probabilidade.

`0,00` é arredondamento da variação reportada a duas casas decimais em pontos-base; não significa ausência de variação intrabar ou bid/ask executável. Uma reversão entre dois endpoints não comprova trajetória contínua, drawdown ou reversão intrabar.

## Integração e bloqueios

O estudo consolidado passa a exigir o estado `LAB_PPI_7FX_CROSS_PAIR_BREADTH_DOCUMENTARY_NO_GO`, sete símbolos exatos, três janelas e **uma única raiz econômica**. Caso falhe, retorna `FULL_SEVEN_PAIR_DESCRIPTIVE_BREADTH_INVALID` e `one_event_study=null`.

Quando passa, adiciona ao relatório:

- `usd_normalized_breadth_descriptive_not_forecast`;
- `m15_to_h4_opposing_spot_sign_pairs_documentary`;
- `seven_spot_observations_not_seven_independent_trials=true`.

Esses campos não alteram o protocolo congelado: **`pre_event_research_direction=ABSTAIN`**, `pre_event_directional_forecasts_registered=0`. Nenhuma classificação retorna compra, venda, probabilidade calibrada ou ROI.

## Testes

`test_atlasquant_trader_ppi_fx_breadth_lab.py`: 12 cenários sintéticos para unanimidade, divergência, mediana, reversão, zeros arredondados, par extra/ausente, janela extra/ausente, números inválidos, falsas afirmações de independência, autenticidade ou previsão e imutabilidade dos dados de entrada.

`test_atlasquant_trader_ppi_one_event_study_join_lab.py`: relatórios completos com sete pares fictícios, inversão USDJPY entre M15 e H4 e falha deliberada do novo estágio. Nenhum teste usa resultados futuros reais.

**Estado:** apenas LAB, sem merge, deploy, emissão de vieses reais, entrada no mercado ou despesas. O estudo completo dependerá de registros verdadeiros do BLS e dos candles após o fechamento da janela de 4h, mais autenticação e revisão independentes.
