# AtlasQuant Trader — DFR trimestral do SPF/BCE, com cronologia PIT (LAB)

**Data de pesquisa:** 05/11/2026 UTC. **Objetivo:** permitir leitura verificável
do contexto de expectativas monetárias da moeda EUR, sem antecipar uma pesquisa
que ainda não havia sido divulgada e sem confundir o horizonte trimestral com
consenso para uma reunião específica. Nenhum dado alimenta o Radar.

## Documentos oficiais, referência temporal

- Índice oficial de publicações SPF:
  <https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/all-releases.en.html>.
  O catálogo **data** o relatório Q3 2026 em **24/07/2026** e o Q4 em
  **30/10/2026**. Data editorial de divulgação não equivale a um horário UTC
  independente testemunhado nem comprova que o conteúdo não foi revisado.
- Q3: <https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/ecb.spf2026q3.en.html>.
  O percentual modal **para o próprio Q3 2026** era `2,25%` (61% das respostas).
  Os entrevistados projetavam **`2,50%` de DFR para Q4 2026 e Q1 2027**.
  O valor de `2,25%` do Q3 **não é** a previsão para a reunião do BCE em
  29/10, e `2,50%` é uma projeção para um *trimestre*, não uma probabilidade de
  uma decisão exata.
- Q4: <https://www.ecb.europa.eu/stats/ecb_surveys/survey_of_professional_forecasters/html/ecb.spf2026q4.en.html>.
  A expectativa modal para Q4 reportada após a reunião era `2,50%` (48% das
  respostas). Publicada **30/10**, portanto impossível tratá-la como
  informação conhecida antes da decisão de **29/10**.

## Arquivos reais privados no AM12

Capturadas duas páginas HTML em 05/11/2026, somente para pesquisa local,
sem credenciais, plano pago ou upload de HTML bruto ao GitHub:

| Fonte | Bytes | SHA-256 | Arquivo local privado |
| --- | ---: | --- | --- |
| SPF Q3 | 161.377 | `8566e7a6fef3d3a5bc7c2b6028eb91695fb63007ae82686bdce600aab7a8b770` | `evidence\ecb_spf_2026q3_private_lab.html` |
| SPF Q4 | 155.791 | `a020a4bfc4afac599fc6462aa282e5526b913353dd3978d97520c3545e6c4187` | `evidence\ecb_spf_2026q4_private_lab.html` |

Base dos caminhos privados:
`C:\Users\apare\AtlasQuant_Trader_G8_LAB_20261104`. Os hashes
vinculam **bytes recebidos no dia do teste**, não a autenticidade da cópia
histórica disponível aos participantes do mercado em julho/outubro.

O parser `atlasquant_trader_ecb_spf_dfr_context_lab.py`:

1. Lê somente HTML local, sem rede, cron, Worker ou broker; limita tamanho,
   exige UTF-8, título único da pesquisa e frases esperadas de DFR sem
   duplicação. Rejeita valores fora das faixas e metadados incompatíveis.
2. Usa datas de publicação **catalogadas separadamente** como limites de
   cronologia, nunca hora presumida do anúncio do BCE.
3. Distingue `survey_quarter_modal_dfr_pct` do campo específico
   `q4_2026_modal_dfr_forecast_from_q3_pct`, evitando trocar Q3 por Q4.
4. Para evento 29/10/2026, aceita Q3 apenas como
   `LAB_QUARTERLY_CONTEXT_DATE_PRECEDES_EVENT_UNVERIFIED`; barra Q4 com
   `SPF_RELEASE_DATED_AFTER_EVENT`.
5. Mesmo com cronologia plausível, preserva
   `immutable_historical_vintage_verified=false`,
   `historical_point_in_time_eligible=false`,
   `pre_event_meeting_consensus_verified=false`, `fx_bias=null`,
   `market_surprise_bps=null`, `operational_bias=AGUARDAR`,
   `trade_authorized=false`.

## Testes e limites

- **14 testes sintéticos** novos PASS localmente e **14 PASS no AM12 Windows**.
- Replay do leitor sobre os **dois HTML reais**: Q3 reconheceu modal do próprio
  trimestre `2,25%`/61% e expectativa Q4 `2,50%`, sem viés; Q4 reconheceu
  `2,50%`/48% e foi bloqueado por divulgação posterior ao evento.
- **177 testes focados** PASS no ambiente de desenvolvimento, nos dez módulos
  econômico-PIT da etapa. Quality CI recebe o novo teste.
- Ainda falta: testemunho independente do instante de divulgação, vintage
  imutável, consenso de evento, documento USD comparável em horizonte e
  instante, preço independente EUR/USD e direitos de uso futuro em produto
  comercial. Uma previsão do euro **não** vira automaticamente direção do par.

**HARD NO-GO:** sem merge, deploy, custos novos, publicação, Worker, sinais,
ordens ou backtest com look-ahead. PR #1815 DRAFT e #1816 preservada.
