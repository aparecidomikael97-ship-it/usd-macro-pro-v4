# AtlasQuant Trader — três janelas de atualização (BRT, Cuiabá, NY)

**Checkpoint: 10/11/2026. Apenas plano temporal offline; nenhum job criado.**

## Motivação

O usuário concordou em trabalhar inicialmente com **pelo menos três
atualizações diárias**, sem comprar agora uma fonte que atualize a cada
hora. Os horários propostos previamente para o calendário foram 06h35,
10h45 e 17h15 **BRT**, com checagem da idade dos indicadores às 06h40 BRT.
Importante: BRT/Brasília e a hora local de Cuiabá não são idênticas.

## Novo planejador

`atlasquant_trader_three_daily_schedule_lab.py` usa `zoneinfo` do Python:

- `America/Sao_Paulo` para os horários propostos de Brasília;
- `America/Cuiaba` para exibição no horário local do usuário;
- `America/New_York` para contexto de releases/sessão dos EUA, respeitando
  mudanças do horário de verão americano sem fixar UTC manualmente.

Em **10/11/2026**, as conversões calculadas e testadas são:

| Janela | Brasília (BRT) | Cuiabá | Nova York | UTC |
| --- | --- | --- | --- | --- |
| Manhã | 06h35 | 05h35 | 04h35 | 09h35 |
| Meio do dia | 10h45 | 09h45 | 08h45 | 13h45 |
| Tarde | 17h15 | 16h15 | 15h15 | 20h15 |
| Indicadores (checar idade) | 06h40 | 05h40 | 04h40 | 09h40 |

Na época de horário de verão em Nova York, os horários locais americanos
mudam, enquanto a hora BRT é obtida do fuso `America/Sao_Paulo` no próprio
banco de dados IANA. O sistema não congela um deslocamento americano falso.

## Proteção de qualidade

- `CalendarEventClaim` aceita apenas alegações com horário timezone-aware,
  impacto e ID único. Uma alegação de notícia/evento `HIGH` a até ±30
  minutos de uma atualização sinaliza **janela de risco**.
- A atualização de dados planejada não é cancelada por esse motivo;
  porém nenhuma delas autoriza emissão automática de viés.
- A ausência de eventos na lista **não** comprova calendário completo.
  Mesmo sem evento alegado, o estado da revisão de viés permanece
  `CALENDAR_COMPLETENESS_UNVERIFIED`.
- Verificação de idade dos indicadores 06h40 é uma tarefa conceitualmente
  distinta das três janelas do calendário e **não** é um quarto sinal.
- Finais de semana, feriados, sessão Pepperstone/B3, recibos de publicação
  e integridade da fonte continuam pendentes, não são inferidos pelo plano.

## Testes

- `test_atlasquant_trader_three_daily_schedule_lab.py`: **15/15 casos**
  de três janelas, fuso Cuiabá, horário padrão e verão de NY, horários
  de indicadores, intervalo de 30/31 min, evento baixo impacto, lista
  vazia, evento duplicado e horário sem fuso.
- `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **429/429 testes locais aprovados**.

## Estado e próximos passos

`refresh_jobs_actually_scheduled=false`, `news_fetched=false`,
`macro_data_fetched=false`, `calendar_events_independently_authenticated=false`,
`new_bias_emitted=false`, `calibrated_probability=null`,
`operational_bias=AGUARDAR`, `trade_authorized=false`.

Esta etapa **não liga um scheduler**, não cria custos e não altera o
aplicativo publicado. Antes de executar três coletas reais por dia,
validar a disponibilidade das fontes e confirmar esses horários com o
usuário. A decisão de emitir viés deverá exigir dados anteriores à
decisão, macro bilateral, notícias relevantes, veto de evento, qualidade
de preços e evidência prospectiva, separadamente da atualização dos cards.
