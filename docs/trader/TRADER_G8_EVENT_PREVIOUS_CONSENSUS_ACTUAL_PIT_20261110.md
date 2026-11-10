# AtlasQuant Trader — calendário G8: anterior, consenso, realizado (LAB)

## Objetivo

Separar os três conceitos indispensáveis para interpretar indicadores
econômicos, sem inventar um efeito direcional no Forex:

- **Anterior:** último valor de período imediatamente anterior, com
  publicação e captura alegadas **anteriores** à divulgação corrente.
- **Consenso:** previsão do mercado capturada antes da divulgação corrente.
- **Realizado:** resultado alegadamente publicado e capturado após o horário
  agendado de divulgação, sem reescrever o passado.

O roteador `atlasquant_trader_g8_event_relevance_lab.py` já ligava o
consenso/realizado aos 28 pares G8 apenas para relevância documental.
A extensão acrescenta `previous_value`, `previous_reference_period`,
`previous_published_at` e `previous_captured_at`, todos opcionais em
conjunto. Esses campos não alteram o comportamento de eventos antigos.

## Travas

1. O valor anterior deve pertencer ao **mês imediatamente anterior** para
   CPI/PCE/emprego ou ao **trimestre imediatamente anterior** para GDP,
   incluindo mudanças de ano. Para taxa básica, reuniões são irregulares:
   exige período mais antigo com mesma precisão, sem fingir identificação
   da reunião anterior.
2. A captura anterior deve ter acontecido antes do anúncio corrente e não
   pode estar no futuro em relação ao instante analisado.
3. O valor anterior precisa ter data de publicação anterior ou igual à sua
   própria captura; campos parciais ou números inválidos são rejeitados.
4. `actual_minus_consensus_documentary` (surpresa) e
   `actual_minus_previous_documentary` (mudança do valor anterior) são
   **quantidades diferentes**. Nenhuma delas é automaticamente força da
   moeda, sinal de compra, previsão, probabilidade ou alerta.
5. Revisionamentos do valor anterior divulgados *junto* do evento corrente
   não podem se passar por valores conhecidos antes da notícia. Precisam
   de tratamento de revisão próprio no futuro.

## Validação

**195/195 testes locais aprovados** (`python -m unittest discover -q -p
'test_atlasquant*.py'`). Oito testes novos cobrem anterior pré-divulgação,
diferença pós-evento, captura após divulgação/instante consultado, mês
errado/antigo, metadados incompletos, invalidade numérica e mudanças de ano
mensal e trimestral. Todos os dados de teste são **sintéticos**.

## Limites preservados

Nenhum calendário de mercado real, consenso de provedor ou vintage do
resultado foi autenticado nesta mudança. `source_original_bytes_authenticated`,
`pre_event_consensus_independently_attested` e
`post_event_actual_independently_attested` continuam `false`.

Sem viés D1/W1/M1, score de 0 a 10, acurácia alegada, ordem Pepperstone,
HTTP, publicação, worker, cobrança, deploy ou merge. Tudo `AGUARDAR`.
