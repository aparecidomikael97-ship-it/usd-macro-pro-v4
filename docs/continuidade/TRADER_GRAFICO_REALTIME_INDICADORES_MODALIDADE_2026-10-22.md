# Trader — Gráfico integrado, feed em tempo real e pacote modular de indicadores

**Data:** 22/10/2026 · **Origem:** pedido direto do proprietário com screenshot TradingView DXY H4, indicadores na lateral e ação de visibilidade por olho. **Status:** REQUISITO DE PRODUTO REAFIRMADO / IMPLEMENTAÇÃO FUTURA NÃO AUTORIZADA AGORA.

Este documento complementa `TRADER_PENTE_FINO_AMPLIADO_2026-10-22.md`, sem modificar o código ou os processos da segurança A183. Não cria feed, scripts operacionais, conta externa ou assinatura. **Seis P0 ainda não homologados. HARD NO-GO.**

## 1. Resultado de experiência pretendido pelo proprietário

O usuário entra no **AtlasQuant → Trader → Gráfico** e tem uma experiência profissional semelhante à captura de referência, **sem precisar abrir o site TradingView em outra aba**.

- Gráfico com candles e atualizações *ao vivo*, sempre rotulado com fonte, atraso real, horário/fuso, ativo, timeframe, estado do mercado e qualidade do último candle.
- Barra de ativos/favoritos e múltiplos timeframes (M1, M5, M15, H1, H4, Diário, Semanal, Mensal e outros somente se suportados por fonte e contrato). O print mostra **DXY em H4**, não dados operacionais certificados.
- Biblioteca/catálogo lateral dos indicadores com rótulos, parâmetros, grupos e ação **olhinho mostrar/ocultar por indicador**, equivalente à UX familiar do TradingView. O estado oculto não remove a configuração do indicador.
- Layout e visibilidade persistentes **por proprietário, ativo, timeframe e dispositivo**; perfis opcionais Iniciante, Avançado, análise macro e operacional. Alternância deve ser imediata e não gerar chamada extra de API para indicador meramente oculto.
- Controles de personalização para cores, zonas, labels, transparência, ordem, sessão, fusos e templates. Layout desktop e celular com usabilidade comprovada.
- AION pode explicar o significado de cada zona/sinal, indicar dados faltantes, riscos e cenário invalidante; **não inventa o valor do indicador e não transforma um desenho em autorização de ordem**.
- O proprietário mencionou de passagem `Negócios`, mas terminou explicitamente solicitando **Trader**. O destino do gráfico aqui é **Trader**, sem inserir ticker/gráfico financeiro em Negócios.

## 2. Biblioteca inicial: catálogo de métodos e comportamento

| Família | Indicadores/estudos desejados | Controle individual e dependências |
|---|---|---|
| Estrutura/SMC | Order Blocks, Breaker, Mitigation, BOS, CHOCH, MSS, sweeps de liquidez, FVG e displacement | Cada sobreposição com olhinho independente e regra de invalidação |
| ICT e tempo | Sessions Ásia/Londres/NY, kill zones, HTF structure, AMD/Power of Three, Quarterly Theory, Weekly Profiles | Ajuste de timezone/DST, sessões fechadas/completas, definições objetivas |
| Volume/preço | Volume Profile (eventual POC, VAH/VAL, HVN/LVN **somente após definir cálculos**), VWAP, volume declarado/tick/futuros, filtros por sessão | Rastrear fonte e qualidade; nunca chamar volume de Forex spot de volume consolidado global |
| Técnicos e níveis | Fibonacci, OTE 50/62/70,5/79, CRT, ATR, ADR, zonas, suportes/resistências | Scripts/versionamento/configuração; CTR/CRM citado oralmente pelo proprietário requer confirmar sigla: **CRT** já tem documentação, `CRM` não será inventado como indicador |
| Macro/fluxo | DXY, força G8, contexto COT/posicionamento, eventos e calendários em *overlays* ou painéis auxiliares | Dados com carimbo, limites de validade, regras de pesquisa e licenças distintas |
| Recursos de terceiros | LuxAlgo Sessions, FVG Sessions, ICT Concepts e HTF Power of Three aparecem nominalmente na imagem | O print **não concede licença**, acesso a código, direito de reproduzir scripts nem sincronização da conta TradingView; avaliar somente integração permitida e alternativas autorais |

O requisito **“todos os indicadores”** deve ser interpretado como **catálogo completo dos indicadores selecionados/aprovados pelo proprietário**, não uma promessa irrestrita de copiar todo indicador proprietário existente na TradingView.

## 3. Correção arquitetural: “um script para tudo” versus “um olho para cada indicador”

O usuário deseja experiência de **um pacote AtlasQuant instalado/configurado**, mas com controle isolado por ferramenta. A solução tecnicamente defensável é uma coleção de estudos/overlays sob um **manifesto de pacote comum**, com versões, dependências, parâmetros, permissões e estados de visibilidade independentes. Um único Pine Script pode agrupar múltiplos desenhos e disponibilizar parâmetros para ativá-los/desativá-los, mas **o olhinho nativo é controle do estudo inteiro**: isso não implementa automaticamente um olhinho nativo para cada subindicador.

Duas implementações possíveis a avaliar somente na fase Trader:

**A. Widget incorporado (baixo esforço visual, capacidades limitadas).**
- Experiência de gráfico embutido e estudos disponíveis no widget, subject to widget API.
- TradingView confirma que **não é possível adicionar Pine Scripts personalizados aos widgets**.
- Portanto **não satisfaz sozinho** o pacote completo solicitado nem a inclusão automática dos scripts da conta do proprietário.

**B. Biblioteca de gráficos licenciada ou renderizador próprio (maior esforço, maior controle).**
- Renderizador profissional com fonte de dados permitida, histórico e stream; bibliotecas como TradingView Advanced Charts exigem conferir condições de licença para o ambiente AtlasQuant.
- A documentação oficial confirma que **Advanced Charts não suporta Pine Script**, mas admite indicadores customizados em **JavaScript**. Isso exigiria reimplementar em JS os estudos cuja lógica e propriedade intelectual permitam, ou construir motor próprio com overlays sincronizados ao chart.
- TradingView Advanced Charts **não traz dados de mercado**; o AtlasQuant precisa contratar/obter fonte licenciada ou utilizar feed permitido, criar datafeed histórico e subscrição live (além de reconexão, correção de candles e limitação de tráfego).
- As condições públicas documentadas para uso gratuito de Advanced Charts incluem atribuição visível e ambiente **público**, não privado ou protegido por paywall. Verificar termos e obter licença/acordo aplicável **antes** de assumir uso no AtlasQuant privado/comercial.
- Os cinco scripts Pine já encontrados em `tradingview/` (BOS/CHOCH+OB, FVG, OTE, CRT, AMD/PO3) **são pesquisa separada**, não plugins automaticamente portáveis para Advanced Charts. Compatibilidade/fidelidade precisa ser demonstrada.

**Fontes oficiais consultadas em 22/10/2026:**
- TradingView widget: https://www.tradingview.com/widget-docs/faq/general/ (Pine em widget não suportado).
- Advanced Charts FAQ: https://www.tradingview.com/charting-library-docs/latest/resources/Frequently-Asked-Questions/ (Pine não suportado; JS custom).
- Indicadores customizados: https://www.tradingview.com/charting-library-docs/latest/custom_studies/ .
- Conexão com dados: https://www.tradingview.com/charting-library-docs/latest/connecting_data/ (feed de dados não incluído).
- Licensing/overview: https://www.tradingview.com/charting-library-docs/latest/introduction/ .

## 4. Critérios objetivos de aceite futuro

| Gate | Deve ser testado e evidenciado |
|---|---|
| UI-01 | Acessar Trader → Gráfico sem redirecionamento obrigatório para o site externo; trocar DXY/H4, pares e timeframes com histórico consistente e proveniência. |
| UI-02 | Adicionar/remover indicador ao pacote; ícone de olho individual com show/hide sem perder configuração; persistência após logout e em celular/PC. |
| UI-03 | Ocultar Order Block sem ocultar FVG; ocultar Volume Profile sem afetar Fibonacci; grupos e ordenação da lista; conflito de camadas e performance sob múltiplos estudos. |
| UI-04 | Mostrar dados vazios, fora de mercado, atrasados, sem assinatura ou com feed em falha como **NO DATA / STALE**, não tempo real fictício nem preço congelado rotulado live. |
| DATA-01 | Histórico e streaming da fonte licenciada (nome, fuso, mercado e política de atraso), reconexão, deduplicação, bar fechado vs em formação, TTL, DST e custos. |
| MODEL-01 | Testes determinísticos dos cálculos/zonas, anti-look-ahead e invalidação para cada indicador autoral, paridade com replay/backtest quando aplicável. |
| LEGAL-01 | Licença de chart + feed + indicadores de terceiros por ambiente privado/comercial; nenhuma cópia de scripts protegidos ou reutilização automática de scripts privados de conta externa. |
| FINOPS-01 | Sem assinatura/API nova nesta etapa; proposta de custo antes da implantação, cache, limites de stream, rate limits e teto de R$200/mês (ChatGPT Plus excluído). |
| SAFE-01 | Somente leitura; nenhum botão de gráfico nem script abre operação real, altera autorização P0, envia ordem ou bypassa Safety Core. |
| QA-01 | Demonstração em Windows, celular, múltiplos ativos e intervalos, carga com todos os indicadores, reconexão e estado persistido; evidências com screenshots e logs rastreáveis. |

## 5. Ordem de construção após homologar núcleo

1. Inventariar quais dados/indicadores são realmente acessíveis, custos e licenças. Distinguir *“visual TradingView dentro do Trader”* de *“reproduzir exatamente minha conta pessoal do TradingView”*: este segundo exige capacidades que embeds normalmente não oferecem.
2. Prototipar (dados sintéticos/CSV, **SEM CONEXÃO REAL**) a experiência do gráfico, catálogo e olhinhos independentes para comprovar UX/performance.
3. Validar engine e adapter legal de chart, fonte com dados permitidos em tempo real e contratos de sincronização.
4. Portar/calcular as estratégias autorais com testes objetivos; habilitar os módulos individuais e manter presets por ativo/timeframe.
5. Homologar no PC e celular, verificar políticas FinOps e só ativar live feed com autorização humana expressa posterior.

### Situação presente

**Requisito salvo, implementação ainda não iniciada.** Nenhuma entrega deste documento autoriza merge, deploy, dados ao vivo, contratação de TradingView/feed/API, acesso à conta pessoal ou execução de ordens. **P0 0/6, HARD NO-GO; Cloud A183 permanece prioritário.**
