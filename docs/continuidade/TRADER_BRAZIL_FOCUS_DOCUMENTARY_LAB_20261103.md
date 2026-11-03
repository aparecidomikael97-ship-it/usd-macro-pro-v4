# AtlasQuant Trader — expectativas Focus com origem oficial, sem antecipar divulgação (LAB 03/11/2026)

## Objetivo
O usuário quer **viés macro antecipatório** em D1/W1/MN1 para 28 pares Forex e índices. Para WIN/WDO, expectativas de Selic/IPCA/câmbio/PIB são relevantes, mas precisam ser **datadas e distinguíveis**: um valor de fim de ano não é consenso de decisão do Copom seguinte, e uma mediana da pesquisa não é probabilidade de acertar direção.

## A fonte oficial verificável
- Documento oficial Banco Central, **Focus de referência 23/10/2026**: [PDF de 2 páginas](https://www.bcb.gov.br/content/focus/focus/R20261023.pdf). Na página do BCB o relatório é publicado em **26/10/2026**. Este estudo admite apenas sua leitura documental a partir do dia UTC seguinte à publicação.
- O [calendário oficial](https://www.bcb.gov.br/publicacoes/focus) indicava divulgação do Focus em **03/11/2026** (após o feriado de 02/11). **Não foi possível verificar aqui diretamente o PDF, seus bytes e o horário original do relatório novo de 03/11**. Portanto este módulo **não inventa nem importa as medianas novas**; trata o relatório de 23/10 como **documento anterior sujeito a atualização**, não "último Focus" em 03/11.
- A transcrição da página PDF é manual, com link e data; **sem hash de conteúdo original, cadeia de custódia ou captura assinada**. O contrato exige os nove valores/documentos exatos, bloqueando mudanças por parâmetros externos, mas não comprova autenticidade criptográfica da publicação.

## Median as-of do documento oficial de 23/10
| Indicador | Alvo da expectativa | Mediana da coluna "Hoje" | Observação |
|---|---|---:|---|
| IPCA | **ano de 2026** | 5,19% | Projeção anual, não IPCA já observado |
| IPCA | **ano de 2027** | 4,34% | Projeção anual de outro período |
| Selic | **final de 2026** | 13,25% a.a. | Meta esperada ao término do ano |
| Selic | **final de 2027** | 11,75% a.a. | Não é taxa efetiva de hoje |
| Câmbio | **dezembro de 2026** | R$ 5,05/US$ | Média de referência de dezembro, não dólar spot |
| Câmbio | **dezembro de 2027** | R$ 5,15/US$ | Não é sinal para o WDO |
| PIB total | **ano de 2026** | +1,80% | Previsão anual, não PIB 2T observado |
| PIB total | **ano de 2027** | +1,31% | Projeção de outro exercício |
| Selic | **fim de novembro de 2026** | 13,50% a.a. | Página 2 do PDF; não é prova de consenso da reunião de 04/11 |

**A distinção decisiva:** Selic **13,25% de final de dezembro** e **13,50% no fim de novembro** convivem no MESMO Focus de 23/10, para períodos diferentes. Não permitir selecionar uma delas silenciosamente como "a chance de corte no Copom".

Em 03/11, a Selic oficial ainda observada era **13,75% a.a.**, decidida em setembro ([BCB](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?numero=45963&tipo=Comunicado)). A decisão de 04/11 ainda precisava ocorrer. Estimar chance de corte exigiria consenso específico por reunião, cotação de DI e normalização por prêmio de risco, todos verificados antes do evento.

## Contrato e testes
Função: atlasquant_trader_brazil_focus_documentary_lab.py
Teste: test_atlasquant_trader_brazil_focus_documentary_lab.py

- Nove medianas oficiais de **um único PDF antigo** com indicador, tipo de alvo, data, valor e unidade;
- composição com os fatos BR e calendário BR/US de WIN/WDO, duas séries de três horizontes;
- estado obrigatório NEW_SCHEDULED_FOCUS_RELEASE_REQUIRES_OFFICIAL_PDF_REVIEW a partir de 03/11, sem afirmar que o antigo é atual;
- pre_meeting_consensus_verified=false, market_priced_brazil_expectations_verified=false;
- next_copom_meeting_decision_consensus_pct=null, next_copom_cut_probability=null, directional_bias=AGUARDAR, probability_calibrated=null;
- nada se torna trade, execução, ordem, worker, cron ou Radar live.
- **32 testes locais** cobrem os 9 números, diferenças de período, entrada adulterada, calendário e ausência de direção.

## Próximo passo para realmente antecipar
1. Obter **diretamente do BCB** o Focus referente a **30/10**, que seria divulgado em 03/11, ou os dados oficiais do OData Olinda com **Data, DataReferencia, coleta, publicação, metadados, captura e hash**.
2. Congelar as expectativas pertinentes *antes do Copom* e separar projeções de fim de ano/mês de expectativas da reunião. Estudar dados de curva DI com fornecedor e licença adequados, sem custo não autorizado.
3. Comparar o resultado de 04/11 com consenso prévia e teoria causal de WIN/WDO (fiscal, fluxo, dólar global, risco), incluindo cenários contrários.
4. Fazer walk-forward D1/W1/MN1 com preços independentes e medir abstenção, baseline, custo, erro e calibração OOS, antes de qualquer afirmação de acerto de 90%.

**LAB / HARD NO-GO:** PR rascunho, sem Worker, UI, main, deploy, preços, ordens ou custos novos.
