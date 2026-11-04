# AtlasQuant Trader — checkpoint PRÉ-COPOM de 04/11/2026 (congelado em 03/11)

**Finalidade:** registrar, antes de ser conhecida a decisão, o que as fontes de 03/11 realmente indicavam, e preservar cenários alternativos sem inventar probabilidades ou prever o preço do WIN/WDO.

**Marco documental:** `docs/continuidade/TRADER_COPOM_20261104_FROZEN_PRE_EVENT_20261103.json`, com verificação por `atlasquant_trader_copom_pre_event_lock_lab.py`. Registo da origem no commit GitHub deste PR #1803, em DRAFT e LAB / HARD NO-GO. O SHA do registro e o hash do Git identificam conteúdo; o módulo **não comprova o horário independente do push/publicação, autenticação dos artigos nem posse dos bytes do PDF original**. Para auditoria futura, conferir data de chegada do commit pelos registros do próprio GitHub.

## Fontes anteriores à decisão

1. **Calendário oficial BCB:** reuniões do Copom em **03 e 04/11/2026**, https://www.bcb.gov.br/detalhenoticia/20739/nota/https%3A/www3.bcb.gov.br/sgspub .
2. **Comunicado normativo BCB 43.383:** comunicado da decisão na segunda sessão, **a partir das 18h30 de Brasília (21h30 UTC; 17h30 Mato Grosso)** e logo após o término da reunião. Este é um **limite mínimo para publicação**, não um horário exato nem garantia de entrega, https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Comunicado&numero=43383 .
3. **Focus oficial, data-base 30/10, publicado em 03/11:** https://www.bcb.gov.br/content/focus/focus/R20261030.pdf. No texto do PDF conferido, mediana Selic ao **fim de 2026 = 13,50% a.a.**, ao **fim de novembro = 13,50%**, ao **fim de 2027 = 12,50%**. Distintos de decisão 04/11. Página oficial: https://www.bcb.gov.br/publicacoes/focus/30102026 . **Não há PDF bruto versionado**; SHA-256 do binário permanece NULL.
4. **Pesquisa de economistas Reuters, artigo 03/11:** https://www.reuters.com/world/americas/brazils-post-election-market-shock-clouds-path-cheaper-credit-2026-11-03/ . **33 de 48 economistas** disseram esperar manutenção da Selic em **13,75%** na decisão de 04/11. A fração **68,75%** é participação entre os entrevistados, NÃO probabilidade de manutenção implícita em DI/OIS. Os **outros 15 respondentes** não foram automaticamente classificados como corte de 0,25 ponto: respostas detalhadas não estão neste registro.

## Três cenários prospectivos definidos AGORA

| Cenário pré-evento | Condição observável após comunicado | Interpretação limitada |
|---|---|---|
| `HOLD_13_75` | Taxa anunciada = 13,75% | Coincidiria com a expectativa de manutenção que mais respondentes escolheram; **não implica alta ou baixa de dólar/índice** |
| `CUT_25BP_13_50` | Taxa anunciada = 13,50% | Seria um corte de 0,25 p.p. em relação à taxa atual informada; o Focus de dezembro não equivale a essa previsão |
| `OTHER` | Outra decisão, ou nenhuma taxa efetiva verificada | Exige comparação explícita; não criar rótulo "acerto" por conveniência |

Esse registro é uma **expectativa sobre a decisão de política monetária**, não uma previsão direcional de FX ou WIN/WDO; o comunicado e seu TOM importam, mas não temos reprecificação de juros DI, preços e fluxos ponto-no-tempo para quantificar reação. Para avaliação, não tratar um evento único como estatística de assertividade.

## Limite temporal e avaliação futura

O módulo só admite a emissão de uma versão NOVA entre **03/11 15h UTC e 04/11 00h UTC** (intervalo conservador para não olhar o resultado depois). A versão foi salva na PR durante 03/11. A data do commit deve ser verificada externamente; autor e relógios locais não são selo de custódia.

Depois de 04/11, qualquer rotina de comparação deve consumir **o artefato já versionado**, nunca reconstruir uma hipótese com o resultado conhecido. Conferir o comunicado original e a eventual fala/ata, data de publicação e o mercado DI antes de inferir surpresa. Se não houver verificação oficial, classificar o resultado como **PENDENTE**. Não decidir compra/venda com base apenas em Focus x pesquisa de analistas.

Os 22 contratos em `test_atlasquant_trader_copom_pre_event_lock_lab.py` cobrem: cortes temporais, 33/48 como amostra e não odds, três cenários, falta de confirmação de PDF bruto e hora de publicação, rejeição de fontes, valores e amostras adulterados e bloqueio de ativação.

**Sem Render, custo, API paga, RSS live, Worker, scheduler, UI, merge, deploy, ordens, uso em Radar, probabilidade calibrada ou taxa de acerto inventada.**
