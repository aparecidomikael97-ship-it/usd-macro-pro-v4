# AtlasQuant Trader — fontes primárias para notícias macro, sem custo de assinatura (LAB 03/11/2026)

**DRAFT / HARD NO-GO.** Não há RSS ou API de notícias ligado ao aplicativo, Worker, cron, Radar, Render, corretora, ordens ou pagamento. Este é apenas um **plano offline de atenção a eventos**, reaproveitando a agenda G8 já existente.

## O que foi pesquisado

Cinco caminhos públicos oficiais, inicialmente sem assinatura contratada:

| Fonte | Caminho verificado como documentação oficial | Cobertura inicial |
|---|---|---|
| BLS, emprego | https://www.bls.gov/feed/empsit.rss | USD, emprego 06/11 |
| BLS, CPI | https://www.bls.gov/feed/cpi.rss | USD, inflação 10/11 |
| Federal Reserve | https://www.federalreserve.gov/feeds/press_monetary.xml | USD, decisões monetárias posteriores (não confundir com reunião atual) |
| Banco Central do Brasil | https://dadosabertos.bcb.gov.br/dataset/atas-comunicados-copom | BRL, comunicados/atas; a existência de API não prova baixa latência |
| Banco da Inglaterra | https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates | GBP, agenda 05/11; **página, não RSS de resultado verificado** |

Referências dos índices oficiais: https://www.bls.gov/feed/ , https://www.federalreserve.gov/feeds/feeds.htm e https://www.bcb.gov.br/acessoinformacao/calendariobc?agenda=Reuni%C3%B5es+do+Copom .

**Atenção:** páginas ou canais públicos não constituem oferta formal de serviço de notícias em tempo real, licença comercial automática, garantia de disponibilidade, conteúdo completo ou horário de recebimento. Não foi feita captura autenticada de nenhuma mensagem dos feeds, nem medição de latência. Preço para avaliação aqui: nenhum fornecedor pago contratado; custo operacional/termos de eventual consulta automática ainda requerem revisão.

## Agenda prioritária em 03/11/2026

- 04/11 Copom, Brasil. **Precisão DATE_ONLY** no contrato: não inventamos minuto de divulgação; não antecipar Selic decidida.
- 05/11 Banco da Inglaterra, decisão de juros. **Precisão DATE_ONLY** no contrato existente.
- 06/11 emprego dos EUA (BLS, horário programado 13:30 UTC). Resultado efetivo e consenso são desconhecidos neste plano.
- 10/11 CPI dos EUA (BLS, horário programado 13:30 UTC). Resultado efetivo e consenso são desconhecidos neste plano.

O leitor `atlasquant_trader_primary_news_routes_lab.py` reutiliza os três eventos do `atlasquant_trader_macro_event_exposure_lab.py`, acrescentando a exposição doméstica brasileira específica, e organiza **28 pares × três horizontes = 84 linhas** e **5 índices × três horizontes = 15 linhas**. O par GBP/USD recebe os eventos GBP e USD; WIN/WDO recebem Copom como contexto doméstico e BLS como contexto externo indireto. Índices dos EUA não herdam diretamente o Copom.

**Janela móvel e precisão:** W1 equivale a 7×24h a partir do instante consultado, não à semana civil. Por isso, o CPI 10/11 às 13:30 UTC está fora de W1 em 03/11 às 00:00 UTC, mas dentro de W1 em 03/11 às 14:00 UTC. Eventos DATE_ONLY que podem ter ocorrido durante o dia ficam marcados com incerteza, nunca automaticamente divulgados. Evento vencido passa a `WINDOW_PASSED_ACTUAL_NOT_VERIFIED` e deixa de aparecer como "próximo"; é necessário conferir a publicação atual para remover pendência.

## Prioridade do orçamento

1. Primeiro, validar manualmente conteúdos e datas oficiais, disponibilidade e atualização dos feeds/documentos.
2. Comparar horários de **divulgação oficial, primeira detecção, captura e exibição** por várias notícias; medir atrasos e falhas sem fingir rapidez.
3. Em paralelo, documentar consenso/expectativas pré-evento com fontes independentes. RSS do resultado **não fornece, por si só, consenso de mercado** nem surpresa.
4. Somente se houver atraso relevante, licença/uso de dados insuficiente ou necessidade comprovada de eventos não cobertos, pesquisar fornecedor pago. Levar preço, limites, licenciamento e benefício mensurável ao proprietário para **autorização explícita**. Nenhum plano pago foi aprovado agora.

**Não fazer gastos para substituir Render automaticamente:** Render é hospedagem; um provedor de notícias é outra função. Cancelamento do Render requer conferir serviços e backups antes. Não ativar monitoramento contínuo sem decisão e verificação de custos. A cobertura inicial é parcial: USD/GBP/BRL, não cobre as oito moedas nem todas as notícias/geopolítica.

## Testes

`python -m unittest -q test_atlasquant_trader_primary_news_routes_lab.py`

22 testes locais (parcialmente com stubs fiéis aos universos canônicos para execução isolada) passaram, incluindo cortes W1, eventos expirados, veto a actual/consenso forjados, recusa de mudança de URLs e proteção de WIN/WDO. O CI da PR executará os testes reais com importações do repositório. Passar não homologa feed real, velocidade, segurança de origem nem previsão.

`directional_bias=null`, `probability_calibrated=null`, `news_live=false`, `trade_authorized=false`, `can_feed_live_radar=false`, `render_configuration_changed=false` e `scheduler_enabled=false`.

**UI aprovada, main, contas, Worker e produção continuam intocados.**
