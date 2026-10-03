# AtlasQuant — revisão consolidada da interface / PR #554

Branch exclusiva: `fix/trader-scanner-nav-20261003`. Head inicial verificado antes de editar: `2e820b892c828d01dd9637bc8f89901fa9b3fe3d`. Sem merge, deploy, produção, ordem real ou chamadas novas a providers.

## Navegação preservada

Os 24 acessos ficam diretamente na barra lateral desktop/tablet, com rolagem interna. No mobile, `Funções do Trader · 24` e `Ver todas as funções · inclui avançadas` abrem a lista completa. Iniciante simplifica orientação; Avançado oferece orientação direta. Ambos preservam todas as funções, os atalhos da home e retorno ao início. Permissões permanecem as existentes.

| Função | Rota da interface | Destino existente |
|---|---|---|
| Início | home | Home Trader |
| Radar | radar | Radar |
| Scanner Técnico | scanner | Painel Mestre legado / scanner |
| Painel Mestre | master | Hub de contexto; ponte para Painel Mestre legado |
| Macro · EUA | macro | EUA |
| Fed | fed | Fed |
| Micro | micro | Moedas |
| Geopolítica | geo | Notícias |
| Notícias | market_news | Notícias |
| Fundamentalista | fundamental | Pares |
| ICT/SMC | ict | Pares |
| Calendário Econômico | calendar | EUA / calendário |
| Pré-Notícia | news | Macro Briefing |
| Market Map | market_map | Market Map |
| Laboratório/Backtests | lab | Backtest |
| Paper Trading | paper | Backtest / Forward existentes |
| Guardião de Risco | guardian | Decisão |
| Autopilot | autopilot | Autopilot, gates existentes |
| Performance/Melhorias | performance | Melhorias |
| Academia | academy | Aprender |
| Diário | journal | Histórico existente |
| Vídeos/Conteúdo | video | Aprender |
| AION Trader | aion_specialist | Especialista existente |
| Perfil/Configurações | profile | Conta |

`Radar Mestre` não aparece como acesso duplicado. Scanner, Radar e hub Painel Mestre têm contextos distintos. Notícias e Pré-Notícia permanecem separados. Todas as pontes anteriores para páginas operacionais foram preservadas; esta entrega não cria motores novos.

## Ranking, dados e estados

O Painel Mestre apresenta destaque nativo em duas colunas para até dez leituras elegíveis e uma área secundária compacta. A população vem somente do estado residente do Radar existente. A ordem é a de `rank_fx_population`; esta interface não cria pesos, scores, sinais, cotação ou desempenho.

Para publicar posição, a leitura precisa ter par oficial, dados prontos, proveniência confirmada, pipeline elegível, score finito e origem; o snapshot precisa declarar estado validado e timestamp dentro do limite de frescor de 90 minutos já utilizado pelo Fast Startup. Duplicatas e pares desconhecidos são rejeitados. Ao perder elegibilidade, o par deixa de ocupar posição e o próximo elegível é promovido. Direção só aparece confirmada quando o sinal residente também está confirmado e dentro da validade temporal.

Sem evidência: `Ranking aguardando dados validados`; os 28 pares permanecem monitorados, sem numeração arbitrária. Nunca há `TOP 10` junto de `POSIÇÃO A VALIDAR`. Universo de 28 não significa cobertura técnica institucional nos 28: o runtime atual continua tendo cobertura conforme seus packs reais, frequentemente sete pares. Destaque para estudo nunca autoriza entrada.

Ticker continua com `PRÉVIA` / `—` quando não há dados residentes validados. Negócios não recebe ticker Forex; Investimentos mantém universo próprio. Os três painéis inferiores de Investimentos recebem estados nativos neutros que cobrem cotações e percentuais desenhados na referência, inclusive no hover/focus e no mobile. Não há rentabilidade inventada.

## Histórico de Validação AtlasQuant

O laboratório reutiliza o painel operacional, CSV TradingView, replays, métricas e snapshot history existentes. O histórico agora oferece filtros por Ano, Mês, Setup, Ativo e Timeframe com metadados disponíveis. Campos ausentes ficam `Não informado`. A linha do tempo é filtrada; comparação, verificação de integridade, exportação integral e restauração ZIP permanecem intactas.

Diário continua Histórico; Backtest testa regras em candles históricos; Paper/Forward corresponde à simulação prospectiva já existente. Nenhum banco ou motor paralelo foi criado.

Snapshots continuam locais em `.atlasquant_research/backtest_snapshots`. Hospedagem efêmera não garante histórico multiano; backup ZIP e armazenamento externo durável continuam dependências reais, sem promessa de persistência.

## Central e ambientes

Login recebeu apenas CSS e marca local da referência. Autenticação, sessão e RBAC permaneceram intactos. Central conserva os quatro acessos: Trader, Negócios, Investimentos e AION. Arte aprovada continua sendo ilustração; valores desenhados na arte não representam telemetria real.

Negócios e Investimentos expõem também as capacidades do catálogo em atalhos visíveis, sem esconder módulos atrás de uma seção avançada. Estados originais `PRÉVIA`, `EM CONSTRUÇÃO` ou `CONECTADO` são preservados; CRM/B2B/automação sem implementação não ganham dados fictícios.

AION apresenta um único Core e oito papéis de produto: Orquestrador/Núcleo; Arquiteto/Estrategista; Guardião/Auditor; Prime/Execução; Shadow/Pesquisa e Triagem; Sentinel/Monitoramento; Comercial/Leads e CRM; Educador/Treinamento. São explicações de responsabilidades na UI, não uma migração do registro técnico interno. Nenhum arquivo do Core, provider, autoridade ou gate foi alterado.

## Evidências e limites de revisão

Matriz obrigatória: 1280×720, 1024×768, 768×1024 e 390×844. Testes Chromium cobrem os 24 acessos em ambos os modos, cliques, retorno, descoberta mobile, geometria de hover/focus, ausência de overflow e reduced-motion. Capturas são geradas em `visual_review/` pelo workflow Reference UI.

O harness de revisão usa identidade local identificada, sem autenticação de produção. O login capturado usa o shell real com formulário de revisão; autenticação real é coberta separadamente pelos testes existentes. O Backtest capturado é o painel offline real. Capturas `final-top10-test-fixture-*` têm aviso explícito de fixture e comprovam layout com dados sintéticos exclusivamente de teste; não são evidência de ranking financeiro real. Os demais painéis sem evidência mostram estados neutros.

Pendências reais: conexão de dados validados à apresentação quando disponíveis; cobertura técnica além dos packs existentes; conteúdos e capacidades B2B em prévia; persistência externa durável dos snapshots. Nenhuma dessas pendências foi mascarada por dados inventados.
