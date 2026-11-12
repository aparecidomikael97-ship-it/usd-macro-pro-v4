# AtlasQuant Trader — filtro seletivo de viés W1/D1 (LAB)

**Situação em 08/11/2026:** filtro experimental **isolado**, em
`atlasquant_trader_selective_bias_gate_lab.py`. Não substitui a matriz
operacional, não altera o Radar/Painel Mestre e não ativa avisos, MT5,
execução, worker, agendamento, deploy, merge nem novos custos. **Não existem
80% ou 90% de precisão de mercado comprovados.**

## Intenção

Mikael pediu que o sistema não anuncie compra/venda a toda hora. Atualizar as
fontes de dados não é o mesmo que divulgar uma nova direção. O resultado normal
e mais frequente deste filtro é **AGUARDAR**, inclusive quando o score parece
atraente. O objetivo é desenvolver, medir e eventualmente selecionar poucos
vieses D1 e W1 dos **28 pares G8** e, em estudo separado por ativo, **WIN,
WDO, US500, NAS100, US30**.

O score de 0 a 10 é uma **nota de classificação**. Não significa chance de
acerto e nunca é convertido em uma probabilidade por este módulo.

## Condições demonstradas apenas com testes sintéticos

| Condição | Comportamento no laboratório |
| --- | --- |
| Semana e dia | W1 e D1 devem apontar a mesma direção; neutralidade e conflito levam a `AGUARDAR`. |
| Nota | Nota inferior a 6/10 abstém; nota 10/10 não supera falta de documentos. O 6 é um parâmetro experimental, não limiar calibrado. |
| Confirmação | Dois snapshots diferentes separados por pelo menos 30 min para a primeira hipótese; três para uma possível inversão. Máximo de 3 h entre confirmações. |
| Notícias importantes | Bloqueio 30 min antes e depois. Se ocorreu evento entre a captura macro e agora, exige recapturar o contexto, mesmo depois da janela. Sem número real confirmado: `AGUARDAR`. |
| Frequência | Não reapresentar direção já hipoteticamente comunicada. Inversão exige catalisador macro alegado, 4 h de intervalo e confirmação extra. Não gera aviso real. |
| Fonte e frescor | Horários com fuso, sem futuro; observação com até 6 h e contexto macro com até 12 h; declaração de análise macro, geopolítica e direitos dos dados. Declarações não são autenticação independente. |
| Histórico | Exige pelo menos 3 janelas cronológicas não sobrepostas, 20 resultados por janela e 100 resultados por combinação de **ativo + período + direção**; resultados posteriores à decisão não podem entrar. |
| Meta de pesquisa | Limite inferior Wilson de 95% de pelo menos 0,80. **Não é taxa de acerto comprovada nem probabilidade calibrada**; observações de mercado são dependentes, e o cálculo binomial simples não valida essa independência. |

Mesmo quando o caso sintético cumpre todas essas condições, a função devolve
`state=LAB_INTERNAL_RESEARCH_CANDIDATE_NOT_LIVE`, com a hipótese interna em
`research_candidate_direction`, porém **`operational_bias=AGUARDAR`**,
`live_alert_allowed=False`, `publishable=False`,
`calibrated_direction_probability=None` e `trade_authorized=False`.

Os números históricos, os hashes e os booleanos são fornecidos pelo chamador,
**sem testemunho independente neste módulo**. Por isso, a aprovação artificial
dos testes não prova dados autênticos, metodologia sem vazamento, desempenho
fora da amostra ou aptidão para comercializar.

## Dependências e limites importantes

1. A matriz técnica existente e o comparador econômico das duas moedas ainda
   precisarão produzir entradas padronizadas, com documento original, horário
   da primeira disponibilidade pública, revisão e custódia.
2. Resultado de CPI, PCE, NFP ou decisão de juros deve ser tratado como um
   **evento econômico**, não como direção garantida do par ou índice. O estudo
   de previsão antes da notícia, em
   `TRADER_NEWS_PREVIOUS_CONTEXT_NOWCAST_LAB_20261108.md`, permanece independente.
3. Para índices, o piloto deverá verificar o instrumento exato (contrato,
   sessão, moeda, horário, rollover), sem transportar automaticamente a
   leitura do Forex.
4. Faltam resultados prospectivos com timestamp, procedimento de escolha de
   entradas e desfecho imutável, correção por dependência, avaliação por
   regime, custos de negociação e conjunto de validação realmente intocado.
5. Nenhum corte numérico foi otimizado ou validado com dados reais nesta etapa.
   Não habilitar emissão de recomendações ou operações com este filtro.

## Testes reproduzíveis

```bash
python -m unittest -q test_atlasquant_trader_selective_bias_gate_lab
```

**27/27 testes sintéticos** aprovados em 08/11/2026, incluindo não repetição,
conflito de W1/D1, rejeição de dados futuros, blackout, inversões, separação
de ativos/períodos/direções e impossibilidade de tornar o resultado real.

No conjunto com seis módulos selecionados da pesquisa anterior sobre CPI,
consenso, captura manual e custódia de juros, **118/118 testes aprovados**.
Não corresponde à suíte completa. Em tentativa adicional com três suítes
legadas, 10 testes de walk-forward executaram, mas os demais módulos tiveram
erros de carregamento por falta de `pytest` e `streamlit`; portanto, não há
aprovação da regressão completa.
