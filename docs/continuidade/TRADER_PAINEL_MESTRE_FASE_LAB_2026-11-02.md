# AtlasQuant Trader — Painel Mestre, continuação LAB (02/11/2026)

**Status:** IMPLEMENTADO / EM VALIDAÇÃO, sem merge e sem deploy desta revisão.  
**Base:** interface aprovada e publicada no commit `f030bf2e`; PR LAB #1803.  
**Governança:** Checkpoint Mestre 22/09, reconciliação 29/09, inventário Trader T01–T58 da PR #1473. Havendo conflito, decisão aprovada mais recente prevalece. Nenhum novo store do núcleo AION.

## Missão
O Painel Mestre explica **por que** um mercado pode mover-se, mas não fornece ordem, previsão infalível ou autorização de entrada. Ele separa evento e contexto macro, confirmação técnica e guardião de risco. O resultado legítimo inclui "aguardar" e "sem dados".

## O que já foi implementado nesta etapa LAB

- Contrato diário e dos próximos **seis dias** a partir de uma **única consulta controlada** `economic-events` EODHD por cache-hora (somente ao abrir a área, caso a credencial existente tenha direito). Sem alterações de plano, cobranças autorizadas ou cron.
- A normalização reconhece país/moeda, data UTC convertida para Brasília, período, base (MoM/YoY/QoQ), consenso, anterior, real, surpresa (real − consenso), identificação e horário da fonte. Campos ausentes não são inventados.
- Resultados futuros nunca podem aparecer como divulgados. Um consenso inserido manualmente exige perfil ADMIN, autor, fonte e data anterior ao release. O automático prevalece. Essa inclusão ainda é **temporária na sessão**, não durável.
- **Briefing macro:** número de divulgações recebidas, eventos por vir, resultados com consenso, possíveis surpresas e janelas de atenção antes/depois dos eventos **com prioridade editorial**. Esta prioridade não é previsão de volatilidade nem sinal de compra/venda.
- **Agenda da semana:** linhas expansíveis com dia, hora BRT, país, indicador, consenso e anterior, mais cenários condicionais acima/abaixo. Quando o teto de apresentação reduz a lista, ela é rotulada **parcial**; isso não invalida os eventos de hoje que tenham sido recebidos integralmente.
- Os quatro cards superiores mantêm a identidade visual aprovada: **Cenário macro** (quantidade de eventos, não tendência), **Bancos centrais** (contagem de eventos, não decisão verificada), **Geopolítica** e **Notícias** (sem feed verificado, não forçam leitura).
- Preservado catálogo de indicadores por EUA/Brasil/Europa/Ásia/G8. Catálogo é planejamento: não representa feed ativo em cada país.
- Surpresa numérica exibe diferença **na unidade do indicador**, não retorno financeiro nem "percentual de reação"; revisões não são declaradas confirmadas sem evidência específica.

## Critérios de falha segura

1. Sem fonte/horário, resposta velha ou de dia incorreto em Brasília: **INDISPONÍVEL**.
2. Resposta da API no limite de 1.000 eventos: bloqueia afirmação de cobertura completa.
3. Lista diária truncada: resumo diário bloqueado. Lista **semanal** truncada: diariamente válido permanece visível, semanal rotulado parcial.
4. Contagens contraditórias, item com hora inválida ou fora do intervalo: resumo rejeitado.
5. Sem consenso: surpresa não calculada. Notícias/geopolítica sem feed continuam sem leitura.
6. **Nenhuma execução de ordem, Worker AION, recomendação de entrada ou compra de feed**.

## Testes

- Laboratório AM12: **47/47 testes locais PASS**, incluindo contratos anteriores do Trader, calendário e 12 novos cenários do Painel Mestre. O teste visual sintetizou eventos com selo explícito `EXEMPLO FICTÍCIO · LAB`, sem apresentar dados sintéticos como reais.
- GitHub Actions da PR #1803: verificar estado final de Quality/Browser/Security antes de qualquer aprovação de promoção.

## Dependências para operação integral e definição de "concluído"

- Confirmar **entitlement e franquia disponíveis** na EODHD para o endpoint Economic Events, sem expor token e sem assumir dados universais ou tempo real.
- Verificar amostras reais de CPI/PCE/NFP/BCB, países e escalas, horários oficiais, atrasos, eventos revisados e comportamento no vencimento do cache.
- Habilitar — apenas depois de aprovação e estudo de custo — um agendador **independente do Worker do AION** caso a necessidade seja atualizar mesmo com o site fechado. No estado atual, a coleta é feita sob demanda e limitada por cache.
- Escolher armazenamento durável, com RBAC e trilha de auditoria, para consenso manual compartilhado, caso o proprietário aprove. O atual `session_state` é explicitamente provisório.
- Fontes e metodologias de microeconomia, geopolítica e notícias precisam de contratos próprios antes de deixar o estado `SEM FEED VERIFICADO`.
- Validar produção autenticada, desempenho no Render de 512 MiB, teste móvel e aceite humano antes de merge/deploy.

**Não declarar a integração externa pronta apenas porque os testes com fixtures passaram.**

## Continuidade técnica — biblioteca específica e notícias legadas (LAB)

- Biblioteca atlasquant_trader_master_indicator_guide.py: 25 tipos de indicadores com mecanismo, cenário acima/abaixo do consenso, checklist e ressalvas. ADP não é NFP; PMI surpresa positiva abaixo de 50 não significa expansão; balança comercial sem unidade/sinal mantém direção indeterminada. Desconhecidos jamais geram viés.
- O calendário diário/semanal mostra essas explicações ao expandir o evento. Preserva consenso, anterior, divulgado e surpresa numérica na unidade da fonte, sem inventar porcentagens de ganho.
- atlasquant_trader_calendar_ui.calendar_source_status() discrimina ausência de credencial, permissão/entitlement, limite de consulta, fonte atrasada e resposta incompleta. Nunca mostra token nem mensagem bruta do provedor.
- atlasquant_trader_master_legacy_news.py adapta, sem rede e sem custo adicional, snapshot v1061_currency_news do legado currency_news_v1062.py (Currency News Intelligence). Exige carimbo recente, fonte editorial e artigo recente; sanitiza URLs HTTPS, deduplica manchetes entre as oito moedas.
- atlasquant_trader_master_news_ui.py apresenta manchetes com data/hora Brasília, fonte, link seguro e rótulo OBSERVACIONAL · NÃO É SINAL. Palavras-chave geopolíticas são triagem textual, nunca confirmação de fatos ou influência causal. O score heurístico antigo não autoriza operações.
- atlasquant_reference_ui.py repassa v1061_currency_news somente após gate de acesso autenticado e quando já existir na sessão. O Painel Mestre não inicia RSS/NewsAPI nem compra créditos.
- Novos testes test_atlasquant_trader_master_indicator_guide.py, test_atlasquant_trader_master_news.py e test_atlasquant_trader_master_browser.py: reconhecimento editorial, comparação econômica, deduplicação, staleness, atribuição, segurança HTML/URL e clique em desktop/tablet/mobile.
- 70/70 testes locais PASS no AM12 antes da extensão Playwright, que depende do resultado da CI. Testes sintéticos não homologam feeds de mercado.

### Limites pendentes (não mascarados)

1. EODHD Economic Events depende do direito da conta e disponibilidade do plano. Nenhum teste com credencial de produção foi realizado. Documentação oficial: actual/estimate/previous, comparação, período, máximo de 1.000 eventos por consulta.
2. Calendário atualiza sob demanda/cache, não com aplicativo fechado. Agendador independente não foi aprovado nem ativado. Nenhum serviço novo contratado.
3. Consenso ADMIN é temporário em sessão; faltam persistência auditável e política de revisão.
4. Dados macro oficiais, notícias geopolíticas confirmadas e balanços de empresas exigem contratos de fonte. Manchete observada não equivale a informação factual homologada.
5. Performance e clique autenticado no Render devem ser validados após aprovação de eventual deploy. Auto-Deploy OFF; PR DRAFT; AION HARD NO-GO.

## Segurança financeira adicional — EODHD (LAB, ainda não ativado)

- A EODHD confirma por documentação oficial que o Economic Events Data API requer direito de plano (All-In-One ou Fundamentals), consome 1 API call por consulta, tem parâmetros from/to/country/comparison/limit e limite de 1000 resultados por request. O acesso de produção NÃO foi testado nem contratado por esta PR.
- atlasquant_trader_calendar_quota_guard.py agora impede chamadas por padrão, mesmo com CHAVE_EODHD configurada. Para ativar futuramente, somente após confirmar com proprietário os direitos do endpoint e possível custo: ATLASQUANT_CALENDAR_EODHD_ENABLED=1.
- Limite extra por processo/UTC: ATLASQUANT_CALENDAR_MAX_CALLS_PER_DAY=4 (padrão), teto forçado de 8, além de deduplicação por token hash/dia/hora, lock de concorrência e bloqueio de nova tentativa após erro HTTP/timeout no mesmo intervalo.
- Este limite NÃO é global/durável: réplicas ou reinícios podem zerá-lo; logo não é controle financeiro suficiente para escalonamento e não substitui a franquia do provedor. Enquanto o risco não for encerrado, o gate permanece desativado.
- Diagnóstico seguro ao proprietário: INTEGRAÇÃO DESATIVADA ou LIMITE INTERNO ATINGIDO. Nenhuma chave ou mensagem bruta de erro é exibida.
- test_atlasquant_trader_calendar_quota_guard.py cobre padrão desativado, concorrência, falha de fonte, virada de dia UTC, limite, dados de usuário e ausência de vazamento da chave. 78/78 testes locais PASS no AM12 após esta etapa. Nova bateria GitHub Actions aguardada.
- Para atualização automática com o aplicativo fechado, falta um **agendador aprovado** e uma **persistência compartilhada confiável** (não implementados). Não foi habilitado cron nem Worker do AION e não há nova cobrança.

## Séries macroeconômicas oficiais — BCB/SGS + FRED, sem consumo não autorizado

- O painel agora contém seis read-models de séries oficiais com valor, período estatístico, unidade e fonte, separados do calendário de consensos: BCB SGS 432 Meta Selic (diário, % a.a.), 433 IPCA mensal (% m/m), 13522 IPCA em 12 meses (% 12m), FRED CPIAUCSL usando transformação pc1 (% em 12 meses), UNRATE (%) e DGS2 Treasury 2Y (% a.a.).
- O período da observação econômica não é a data/hora de coleta, de publicação ou de negociação. A tela NÃO exibe dado vencido como atual: limites diários e mensais distintos, rejeição de valor NaN, de data futura e de número inválido.
- atlasquant_trader_master_official_series.py consulta somente quando ATLASQUANT_MASTER_OFFICIAL_DATA_ENABLED=1. POR PADRÃO DESATIVADO, apesar de BCB ser fonte pública e o código legado possuir CHAVE_FRED. Quando autorizado, faz no máximo seis consultas (três BCB, três FRED se chave existente) por UTC day/process via cache in-memory, timeout de sete segundos, paralelismo máximo três. Reinício/réplica podem refazer consultas: isso é limitações explícitas, não garantia de cota global.
- atlasquant_trader_master_official_ui.py preserva o layout aprovado; mostra apenas observações verificadas com unidades e datas ou traços se faltarem dados. Não afirma consenso ou surpresa de calendário nem abre operações.
- A rota de referência em atlasquant_reference_ui.py chama a camada oficial somente depois do gate autenticado, dentro de Painel Mestre. Não liga Worker, cron, pagamentos, chaves novas ou planos.
- Testes novos test_atlasquant_trader_master_official_series.py cobrem série/transformação, observação mais recente, fonte, dados mensais vs diários, datas antigas/futuras, limitações, URL/parâmetros de BCB/FRED e a tela vazia. **89/89 testes locais PASS com PY_EXIT=0 no AM12**.
- Documentação pública conferida: BCB SGS 432 (Meta Selic), 433 (IPCA mensal), 13522 (IPCA 12 meses), FRED observations API v1 com units=pc1. Acesso FRED exige chave já habilitada; EODHD tem direito de plano separado, não presume assinatura.

### Próximos gates de homologação
- Avaliar disponibilização de dados oficiais gratuitos na conta real com medição de tempo de resposta e limites (sem ativações automáticas).
- Validar se horário EODHD sem fuso na resposta corresponde a UTC antes de tratar hora BRT como comprovada; até isso, fonte não deve ser ativada por configuração de produção.
- Só com autorização explícita: agendamento independente e armazenamento auditável de consenso/versões, respeitando orçamento e HARD NO-GO do núcleo AION.
- Nenhuma dessas alterações está no Render; PR #1803 continua isolada e em rascunho.

## Plano diário de atualização — preparação sem executor (LAB)

- `atlasquant_trader_master_refresh_plan.py` entrega **somente** horários propostos em Brasília UTC−03 para a fase atual de 2026. Nenhuma função faz chamadas externas, grava banco, agenda tarefas ou ativa o Worker AION.
- Três janelas para calendário econômico: **06h35, 10h45 e 17h15 BRT**; uma janela de **06h40 BRT** para séries oficiais. Horários são PROPOSTAS: não afirmam que um dado novo foi publicado. Os eventos reais mantêm carimbo UTC e cada série mantém seu período econômico.
- A EODHD permanece desativada por padrão; limite por processo padrão 4/dia (3 janelas hipotéticas + 1 sob demanda), **não** garantia financeira global. O agendador não tem execução ativa; nenhum site fechado é atualizado por esse módulo.
- `atlasquant_trader_master_refresh_ui.py` mostra as janelas no Painel Mestre com aviso forte **AINDA NÃO ATIVADO**, sem botões ou ações de agendamento, preservando o visual aprovado.
- `test_atlasquant_trader_master_refresh_plan.py` cobre fuso, conversão UTC, virada do dia, horizonte, limites, feature flags, ausência de efeito colateral e UI. **99/99 testes locais PASS** no AM12 com exit code 0.

### Portão de ativação futura — REQUER APROVAÇÃO SEPARADA

1. Validar que a conta existente da EODHD tem `economic-events`, horário UTC confiável, dados reais e cota adequada, sem cobranças inesperadas.
2. Confirmar se existem limites globais compartilhados em reinícios/réplicas e serviço de armazenamento auditável (não implementar banco paralelo do Core).
3. Definir agendador independente autorizado, segredos protegidos, autenticação, logs, correlação de tentativa/revisão e desligamento imediato.
4. Garantir atualização sem usuário logado, de forma segura, com retenção/TTL e política de replay sem operações reais.
5. Rodar homologação com dados reais e aprovação visual/custos antes de programar ou publicar qualquer cron/deploy.

**Esta etapa conclui a preparação e testes de um plano, NÃO a automação real.**
