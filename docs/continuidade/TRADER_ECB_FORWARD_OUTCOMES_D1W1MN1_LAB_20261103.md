# Trader LAB — rótulos históricos de resultado BCE, D1/W1/MN1 (03/11/2026)

Escopo: **PR #1803 DRAFT; LAB/HARD NO-GO.** Nenhuma alteração em UI, deploy,
Worker, agendador, ordens, corretoras ou custos.

## O que foi implementado

`atlasquant_trader_ecb_reference_forward_outcomes_lab.py` recebe **somente**
bytes e manifesto do arquivo EXR do BCE já versionado em
`docs/continuidade/ecb_exr_g8_20261026_20261102_raw.csv`.
O arquivo é validado por `atlasquant_trader_ecb_sdmx_archive_lab.py` antes de
qualquer cálculo. O algoritmo emite **84 linhas retrospectivas** (28 pares ×
D1, W1, MN1) para uma data âncora *publicada*, com:

- **D1:** primeira observação original no dia seguinte ou depois, até quatro dias
  corridos após a âncora (fim de semana/feriado não são inventados).
- **W1:** primeira observação original a partir de sete dias corridos, limitada
  a dez dias corridos; nunca adiantada para forçar um resultado.
- **MN1:** primeira observação original a partir de 30 dias corridos, limitada a
  42 dias corridos. Essa regra de pesquisa não representa o calendário de
  vencimento/rolagem de uma operação real.
- **Direção realizada:** alta, baixa ou neutro, com banda *fixa* de 5 pontos-base
  sobre retorno cambial matemático da taxa de referência. Saltos acima de 2.500
  pontos-base são marcados para revisão, não automaticamente rotulados.
- Cotação de BASE/QUOTE = (moeda de cotação por EUR) ÷
  (moeda base por EUR), com EUR = 1; retornos são sempre *ex-post*.
- Data/horizonte sem cotação futura original produz
  `AGUARDANDO_HISTORICO`, `realized_side=null` e retorno nulo.
  Não há interpolação, extrapolação, substituição por candle, média ou sinal.

## Resultado do curto histórico atual

O CSV contém **seis datas**, sete taxas EUR-base por data e 21 cruzamentos
derivados. Para a âncora 26/10/2026:

| Horizonte | Pares com resultado retrospectivo | Pares aguardando histórico |
| --- | ---: | ---: |
| D1 (primeira taxa 27/10) | 28 | 0 |
| W1 (primeira taxa 02/11) | 28 | 0 |
| MN1 (alvo a partir de 25/11) | 0 | 28 |

Essas linhas **não são 56 previsões realizadas**: são apenas *resultados*
históricos calculados depois do fato. Não houve emissão verificável de viés
antes dessas datas neste módulo. O hash do arquivo garante apenas consistência
do arquivo/manifesto, não uma assinatura BCE ou prova da disponibilidade
na hora original.

## Limites mandatórios

- Taxas ECB são **referências informativas**, não ticks, candles,
  spreads, taxas negociáveis ou 28 feeds independentes.
- Captura retrospectiva não prova que o dado existia no instante histórico
  reivindicado, nem certifica OOS.
- D1, W1 e MN1 aqui são rótulos de **resultado**, não a força preditiva
  do viés macro, nem confiança/probabilidade de acerto.
- Não há confirmação macro/micro/geopolítica ponto-no-tempo, histórico
  independente de expectativas ou evidência de 90% de acerto.
- Nenhuma linha fica elegível para produção, ordens, painel ao vivo,
  métricas OOS reais, ranking operacional ou ligação com a interface.

## Para avançar sem extrapolar

1. Capturar **mais histórico** em fonte oficial com método/arquivos e
   proveniência rastreáveis, sem adulterar observações.
2. Manter separados os futuros **vieses emitidos antes dos eventos** e os
   **resultados observados depois**, com cortes de informação verificáveis.
3. Só então medir resultado direcional fora da amostra, contra *baselines*,
   coberturas, eventos macro e neutralidades. Testar revisões, custos, regimes,
   e proibir afirmações de 90% sem amostra auditada e estável.
4. Pesquisar uma fonte licenciada de spot FX/índices com granularidade e
   qualidade compatíveis com D1/W1/MN1, sem contratação agora.

Comando de teste offline no repositório:
`python -m unittest -q test_atlasquant_trader_ecb_reference_forward_outcomes_lab.py`.

Fontes primárias:
- https://data.ecb.europa.eu/help/api/data-examples
- https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html

**HARD NO-GO permanece obrigatório.**
