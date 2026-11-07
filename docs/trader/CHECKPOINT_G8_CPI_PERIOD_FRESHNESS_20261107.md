# AtlasQuant Trader — CPI: competência, data de publicação e cadência · 07/11/2026

**Estado:** somente LAB, revisão pendente. **Objetivo:** evitar que uma revisão tardia de dado velho seja confundida com inflação atual no filtro de evidências bilaterais G8/28.

## Falha específica corrigida

O gate anterior já ordenava pela competência (`observation_period`) e não pela publicação. Porém ainda poderia aceitar um CPI de, por exemplo, abril republicado em novembro como se estivesse atual, pois o frescor era medido somente pela data de publicação.

A melhoria aplica **duas checagens independentes**: prazo desde a divulgação e idade da **competência econômica**. Ambos são limites conservadores **de pesquisa**, não declaração do calendário real ou validação de fonte.

| Tipo | Prazo máximo desde publicação | Competência máxima atrás do mês da decisão | Limitações |
| --- | ---: | ---: | --- |
| CPI mensal (USD/EUR/GBP/JPY/CHF/CAD/AUD) | 60 dias | 2 meses | Frequência aqui é hipótese/catálogo do LAB; não prova vintage nem comparabilidade |
| CPI NZD trimestral (em 2026) | 120 dias | 4 meses | Requer competência no fim de trimestre 03/06/09/12; não prova release oficial |
| Taxa de juros | 120 dias (regra anterior) | NÃO inferir limite por competência | Uma taxa antiga pode continuar válida; exige série efetiva/decisões e prova de continuidade antes de inferir nível vigente |

Os prazos acima são apenas *tetos experimentais*, não autorização de uso após uma revisão. Fonte oficial, horário, periodicidade e frescor reais precisam ser verificados por instrumento e país.

## Regressões adicionadas

- CPI abril republicado em novembro → `REFERENCE_PERIOD_STALE`.
- CPI setembro consultado em novembro → competência 2 meses atrás, estado de metadados (não sinal).
- CPI NZD setembro elegível temporalmente no final de janeiro antes do próximo CPI trimestral, se os horários declarados forem compatíveis; continua NÃO atestado.
- CPI NZD setembro republicado em fevereiro → `REFERENCE_PERIOD_STALE`.
- Um CPI NZD declarado com competência outubro em 2026 → rejeitado porque não encerra trimestre.
- Taxa monetária não herda idade máxima do CPI, mas sua continuidade efetiva permanece por provar.

## Regras principais preservadas

- Qualquer falta de informação/vintage verificável → viés `AGUARDAR`; nenhum score, porcentagem, TOP10 ou probabilidade liberados.
- São duas moedas por par, 28 pares canônicos, viés W1/D1 e M15 técnico separado.
- Macro, microeconomia e geopolítica continuam etapas de contexto/qualidade; não há integração prematura.
- Três consultas econômicas por dia NÃO equivalem a três releases nem a três sinais.
- O Gate `atlasquant_trader_g8_macro_asof_lab.py` opera sobre **metadados declarados pelo chamador**, sem validar origem/assinatura/captura histórica independente.
- A alteração não mede reação do preço, desempenho OOS, capacidade de prever CPI ou rentabilidade.
- **HARD NO-GO:** sem merge, publicação, Worker, agendamento, cobrança, ordem real ou integração ao Radar.

## Próxima ordem técnica
1. Conferir a execução dos testes em CI, sem supor aprovação de verificações não vistas.
2. Exigir metadados reais de periodicidade e calendário por órgão + vintage original do valor, não apenas inferência da moeda.
3. Quando a fonte for verificada, revisar as regras de frescor e comparar os dois lados do par em frequências metodologicamente equivalentes.
4. Só depois avançar a pré-registros W1/D1, backtest fora da amostra e seletividade 0–10, sem substituir o objetivo principal.

Relação com o Checkpoint: `docs/trader/CHECKPOINT_MESTRE_FOCO_TRES_ABAS_20261104.md` e PR rascunho #1845. Os dois cálculos de notícias e o filtro seletivo permanecem isolados e não publicados.
