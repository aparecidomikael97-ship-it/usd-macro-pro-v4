# AtlasQuant Trader — triagem pré-Copom do novo Focus e pesquisa Reuters (03/11/2026)

**PR #1803 DRAFT · LAB / HARD NO-GO. Nenhum merge, deploy, Worker, cron, API paga, Render, alerta live, ordem ou alteração no visual aprovado.**

## Descoberta com utilidade real para o viés macro

Em 03/11/2026, diversos veículos reportaram uma forte revisão nas expectativas agregadas do Focus com **data-base 30/10/2026**, em relação ao PDF **BCB de 23/10**, publicado em 26/10, cuja transcrição anterior já existe em `atlasquant_trader_brazil_focus_documentary_lab.py`.

As oito revisões anuais noticiadas, todas com o mesmo prazo de previsão nas duas colunas, são:

| Referência/variável | 23/10: PDF BCB anterior | 30/10: novo Focus segundo imprensa | Diferença |
|---|---:|---:|---:|
| IPCA 2026 (variação ano) | 5,19% | 5,22% | +0,03 ponto percentual |
| IPCA 2027 | 4,34% | 4,76% | +0,42 pp |
| Selic FIM 2026 (% a.a.) | 13,25% | 13,50% | +0,25 pp |
| Selic FIM 2027 (% a.a.) | 11,75% | 12,50% | +0,75 pp |
| Câmbio média DEZEMBRO 2026 (R$/USD) | 5,05 | 5,34 | +R$ 0,29 |
| Câmbio média DEZEMBRO 2027 (R$/USD) | 5,15 | 5,40 | +R$ 0,25 |
| PIB real 2026 (variação ano) | 1,80% | 1,76% | −0,04 pp |
| PIB real 2027 | 1,31% | 1,20% | −0,11 pp |

Fontes independentes da imprensa observadas em 03/11:
- SAFRAS & Mercado, 03/11: https://safras.com.br/focus-eleva-projecoes-para-inflacao-selic-e-dolar/
- IstoÉ Dinheiro, 03/11: https://istoedinheiro.com.br/boletim-focus-selic-dolar-inflacao-pib-3-novembro-2026
- Relatório anterior oficial BCB: https://www.bcb.gov.br/content/focus/focus/R20261023.pdf

**LIMITE:** a edição oficial nova `R20261030.pdf`, ou o OData com bytes originais, **não foi obtida/autenticada** nesta execução, apesar de busca pública. Os valores novos são **REPORTADOS PELO JORNALISMO, pendentes de verificação na fonte primária**, não vintage autenticada nem dado habilitado no Radar. A referência 30/10 é a data da pesquisa, não a hora de publicação ou captura; o registro de pesquisa é de 03/11, sem recibo independente do horário exato de disponibilização.

### Armadilha muito importante para WIN/WDO

A Reuters em 03/11 publicou uma pesquisa com **33 de 48 economistas esperando manutenção da Selic em 13,75% na decisão do Copom de 04/11**.

Fonte: https://www.reuters.com/world/americas/brazils-post-election-market-shock-clouds-path-cheaper-credit-2026-11-03/

- `33/48 = 68,75%` significa somente **a proporção dos respondentes da pesquisa da Reuters** que escolheram manutenção. NÃO é `P(manutenção) = 68,75%` do mercado, nem extração de futuro DI/OIS, nem probabilidade calibrada.
- A mediana `13,50%` do Focus para o **fim de 2026** tem horizonte e interpretação diferentes de uma pesquisa sobre o dia **04/11**. NÃO interpretar a diferença entre 13,75% atual e 13,50% de dezembro como certeza de corte amanhã.
- A imprensa também apresenta leituras diferentes do contexto macro e do ritmo dos cortes. Não selecionar um painel que favoreça uma operação e ignorar o outro.
- Reprecificação de expectativas, risco fiscal, inflação e dólar podem transmitir pressão contraditória sobre WIN/WDO. Sem preços futuros DI confiáveis, consenso por reunião corroborado, hora de divulgação e mercado pós-evento, o único viés responsável é **AGUARDAR**.

## Entrega de código

`atlasquant_trader_brazil_focus_secondary_triage_lab.py` importa os valores anteriores dos registros BCB já congelados (evita copiar/manipular retrospectivamente), compara-os com oito valores fixos **sinalizados como secundários**, exibe unidade/corte apropriados, guarda um único registro fixo da amostra Reuters e proíbe inferência de probabilidade, atual Copom, câmbio spot, ranking de trades, transmissão de notícia sem autenticação ou ativação de serviço.

`test_atlasquant_trader_brazil_focus_secondary_triage_lab.py`: 26 contratos, inclusive valor/ano trocado, fonte adulterada, futuro antecipado, `survey_share != probability`, unidade de câmbio distinta de pontos percentuais, ausência de consenso imediato e recusa de qualquer trade/Worker/Render.

**CI Quality:** registrar resultado somente após execução real em GitHub do commit. Nenhum teste prova por si só a origem do relatório de 30/10.

**Ações pendentes:** conseguir arquivo oficial BCB/OData para data-base 30/10 sem custo, salvar bytes/hash autênticos, revisar a pesquisa pré-decisão com denominadores e horários e só então preparar evidência real para análise prospectiva, sem confundir notícia pós-eleição com probabilidade de trade.

**Custo adicional zero. HARD NO-GO.**
