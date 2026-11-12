# AtlasQuant Trader — trava de período econômico futuro no calendário G8 (LAB)

**09/11/2026 — PR #1851 em rascunho.** Sem merge, publicação, custo adicional, operação, sinal ou medição de acerto.

## Lacuna corrigida

O roteador de eventos `atlasquant_trader_g8_event_relevance_lab.py` verificava se o período de referência de CPI/PCE/emprego/PIB tinha um formato aceitável, mas não exigia coerência mínima entre **período econômico** e **data de divulgação alegada**. Por isso, uma entrada sintética de CPI de `2026-12` com divulgação indicada para `2026-11-10` podia ser aceita como contexto documental de sete pares USD. Isso não gerava um sinal, mas poderia contaminar auditorias de calendário e posteriores análises.

Foi acrescentado `_economic_period_not_after_release`:

- CPI mensal/anual, PCE mensal, NFP e desemprego: mês de referência não pode ser posterior ao mês da divulgação indicada.
- PIB trimestral: trimestre de referência não pode terminar após o mês da divulgação indicada.
- Política monetária: preservada fora desta regra, pois datas de reunião, decisão e vigência de taxas têm semânticas próprias que exigem evidência do banco central.
- Divulgação *flash* do próprio mês ainda pode aparecer como **contexto não atestado**, sem implicar autenticidade, metodologia equivalente ou viés.

A regra é uma condição temporal mínima. **Não autentica** a fonte, o horário real da publicação, o consenso pré-evento, o dado realizado ou sua causalidade no Forex. Continua a rejeição de eventos incompletos e a propagação bilateral para somente os pares que contêm a moeda afetada.

## Evidência de teste

`python -m unittest -v test_atlasquant_trader_g8_event_relevance_lab`

**23/23 PASS local** (20 testes anteriores e 3 novos). Os testes incluem CPI/PCE/NFP/desemprego com mês futuro, PIB de trimestre ainda não encerrado, mudança de ano, um caso *flash* permitido apenas como contexto e manutenção dos bloqueios de sinais.

**Gates preservados:** `operational_bias=AGUARDAR`, `fx_bias=None`, `publishable=False`, `trade_authorized=False`, `validated_directional_accuracy=None`, nenhum Worker/cron e sem acesso a MetaTrader, conta ou Internet pelo módulo.

**Próximo P0:** levantar recibos oficiais das oito moedas válidos para um instante de decisão D1/W1, com frequências/definições comparáveis e fonte de tempo atestada antes de iniciar o censo prospectivo de 56 pares-horizontes. A pendência do relógio AM12 permanece separada e não foi contornada.
