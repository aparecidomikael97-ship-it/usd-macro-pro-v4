# AtlasQuant Trader — roteamento documental de CPI do USD para 28 pares (LAB)

**Objetivo:** aproximar os registros prospectivos do Fed de Cleveland da Matriz dos 28 pares, sem converter uma previsão de inflação unilateral em viés cambial.

## Fonte e origem no projeto

- Universo canônico: `atlasquant_fx_universe.OFFICIAL_PAIRS`: 8 moedas G8, 28 cruzamentos únicos.
- Fontes prospectivas da pesquisa de 06/11/2026: Fed de Cleveland (CPI headline YoY NSA de outubro **3,74%**, novembro **3,88%**) e calendários BLS, guardados em recibos distintos e hashados em #1836.
- Auditoria macro anterior: `atlasquant_trader_g8_pair_comparability_gate_lab.py`, que verifica apenas período e disponibilidade documental das 8 moedas. Não atesta comparabilidade de metodologias nem gera direção.

## Roteamento correto

| Grupos | Pares | Contexto Fed Cleveland | Viés D1 e W1 |
| --- | ---: | --- | --- |
| Pares que contêm USD | **7**: EUR/USD, GBP/USD, AUD/USD, NZD/USD, USD/JPY, USD/CHF, USD/CAD | Apenas documentos do lado USD, distinguindo as competências outubro e novembro | **AGUARDAR** |
| Demais pares sem USD | **21** | **Nenhum** recibo de CPI do USD é atribuído | **AGUARDAR** |

O sistema marca se o dólar é a moeda base ou a cotada, mas **não** inverte automaticamente o sinal: uma previsão de inflação dos EUA não prova força relativa de qualquer moeda nem permite decidir comprar ou vender o par.

## Limites da entrega

- A leitura existe **somente em módulo independente de laboratório**; não foi conectada ao aplicativo público, nem alterou as três abas aprovadas (Inicial, Radar e Painel Mestre).
- Antes de 07/11/2026 00:00 UTC, ambas as previsões permanecem invisíveis em simulação cronológica conservadora.
- No prazo de divulgação previsto em 10/11, outubro muda para `AFTER_SCHEDULED_RELEASE_NO_AUTHENTICATED_ACTUAL`, mas a previsão de novembro continua pendente até 10/12. Nenhum dado oficial é inventado.
- A falta de projeção macro comparável das outras sete moedas, consenso pré-evento e resultados prospectivos D1/W1 impede cálculo de ranking, melhor par ou score de força.
- Todos os 28 pares conservam `AGUARDAR`, zero operações, zero chamadas HTTP, zero cobrança e nenhuma autorização de worker/deploy.

## Próximo passo de pesquisa

Após a divulgação BLS de 10/11, verificar a primeira versão oficial da inflação de outubro e calcular apenas o erro daquele modelo, sem preenchimento retroativo nem surpresa de mercado. Em paralelo, continuar a busca por fonte comparável para cada uma das sete outras moedas. Não confundir evidência macro com sinal de trade.
