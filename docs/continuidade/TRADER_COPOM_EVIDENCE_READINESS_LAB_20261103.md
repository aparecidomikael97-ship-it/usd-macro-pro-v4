# AtlasQuant Trader — prontidão unificada de evidências do Copom (LAB 03/11/2026)

**Objetivo:** consultar em um único relatório de pesquisa o que está comprovado e o que ainda falta para estudar a decisão do Copom de 04/11 e o gap posterior de WINZ26/WDOZ26. Nenhuma decisão futura, taxa efetiva do Copom ou preço real é presumido. Sem HTTP, scraping B3, feed pago, relógio de rede, Render, Worker, cron, interface, operação ou merge.

## Os quatro tipos de evidência — não intercambiáveis

1. **Expectativa congelada**: verifica os bytes EXATOS do JSON pré-Copom, conforme commit `1281f21860211e9b6f784c649396aa56d17ecdf5`, pelo validador já existente `atlasquant_trader_copom_post_event_compare_lab.py`. O fato de o conteúdo estar preservado em Git **não atesta independentemente** a origem/horário de publicação das notícias, nem dá uma previsão de preço.
2. **Resultado do Copom**: a ausência de comunicado verificável resulta em `NO_AUTHENTICATED_RESULT`. Um suposto comunicado, URL do BCB, relógio e SHA-256 informados por um chamador podem passar regras de FORMATO, mas continuam `CALLER_SUPPLIED_BCB_CANDIDATE_UNATTESTED`. Nem mesmo o cenário `HOLD_13_75` coincidente com a maioria dos 33/48 economistas é prova de origem nem acerto de WIN/WDO.
3. **Janela regular B3**: identifica o planejamento documental de sessão (WIN até 18h25 BRT, WDO até 18h30 BRT, anúncio Copom a partir de 18h30; início da sessão seguinte apenas CANDIDATO), não prova calendário de exceções ou ticks verdadeiros. Continua `REGULAR_HOURS_DOCUMENTARY_ONLY`.
4. **Cotações**: sem arquivo, `NO_AUTHENTICATED_PRICE_DATA`. Com CSV fictício, `SYNTHETIC_TEST_ONLY`; com arquivo que diz ser exportado manualmente, `MANUAL_EXPORT_CANDIDATE_UNATTESTED`, ainda sem auditoria de origem ou direitos de uso. O relatório **não reproduz os valores, provedor ou bytes brutos** desses arquivos.

## Contrato implantado apenas em LAB

O novo `atlasquant_trader_copom_evidence_readiness_lab.py` coordena três validadores anteriores:
- `assess_copom_post_event_candidate_lab` (checkpoint e comunicado candidato);
- `build_copom_b3_session_reaction_lab` (horários de sessão ligados ao checkpoint);
- `inspect_b3_offline_price_export_lab` (CSV opcional, com manifesto obrigatório).

**Recusa o relatório inteiro** se o checkpoint divergir dos bytes originais, se um candidato ao resultado for apresentado antes da janela possível de divulgação, se o manifesto/csv vier incompleto, se o arquivo tiver horário futuro, vencimento trocado, valor alterado ou qualquer erro dos validadores. Uma cópia reformata do mesmo JSON é recusada, porque não é o artefato original congelado.

Mesmo com os quatro itens preenchidos por valores apenas declarados, retorna `LAB_COPOM_EVIDENCE_CANDIDATES_ONLY`, e **não** muda `outcome_rate_independently_verified=false`, `market_session_gap_verified=false`, `economic_causality_proven=false`, `trader_predictive_accuracy_proven=false`, `can_feed_real_oos=false`, `can_feed_live_radar=false`, `trade_authorized=false`.

São **sete pendências independentes**, todas abertas:
- Recibo de publicação pré-evento externo ao relógio declarado, ou prova independente equivalente
- Comunicado original BCB e horário comprovado
- Calendário B3 e sessões de exceção
- Proveniência e autorização de uso de cotações
- Mesmo contrato com ticks efetivamente primeiro/último negócio nos horários corretos
- Outras notícias e reprecificação macro ao longo da noite
- Previsão direcional de preço registrada antecipadamente e avaliação fora da amostra

O fato de uma maioria de economistas esperar uma taxa NÃO equivale à probabilidade de mercado; o Focus de fim de ano NÃO prevê automaticamente a reunião seguinte; e o gap entre sessões NÃO demonstra causalidade exclusiva do Copom.

## Validação

`test_atlasquant_trader_copom_evidence_readiness_lab.py`: **25 testes 100% sintéticos** contra retroatividade, bytes adulterados, falso comunicado oficial, timestamps de notícia, CSV incompleto, dados com vencimento inválido, origem/contrato sem licença, texto do candidato fabricado e promoção indevida para acerto ou operação. A CI de qualidade deve passar antes de declarar a versão aprovada.

Este é um **painel de pesquisa programático, somente em LAB**, não uma mudança na interface do aplicativo. PR #1803 continua DRAFT / HARD NO-GO. **Custo adicional: R$ 0.**
