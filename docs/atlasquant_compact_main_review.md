# AtlasQuant — refinamento compacto sobre a main atual

Base exclusiva: main `f0ce8af00357e09b17d092ea70218258ecdd3426`.
Branch: `integration/trader-main-refinement-20261003`.
Nenhum código foi copiado, mesclado ou rebased da branch auditada `integration/reference-clickable-ui-v4-20261003`.
Sem merge ou deploy.

## Alterações

- Trader usa a nova imagem `atlasquant_trader.png` como referência. Foram extraídos elementos gráficos sem perda e construídos cartões compactos com textos nativos em português, painéis integrados e menu com rolagem interna. Os 19 acessos e a ponte para as análises existentes permanecem.
- Faixa horizontal com 16 ativos Trader e universo próprio de 10 ativos em Investimentos; setas, teclado e gesto de rolagem usam o mesmo container interno. Nenhum ticker é criado em Negócios. A banda financeira foi retirada fisicamente do asset de Negócios, com cabeçalho próprio sem espaço reservado.
- Símbolos locais por país/moeda: DXY EUA; Forex duas moedas; ações brasileiras Brasil; índices, commodities e cripto símbolos próprios. Não há bandeiras aleatórias ou sparklines fixas.
- Preço e variação indisponíveis mostram —. Estado é PRÉVIA. O componente aceita lista residente validada, preserva a ordem do motor e só mostra série quando real e validada. Não utiliza scores como percentuais de preço.
- Hover/focus iluminam a própria borda, sem translateY, outline externo ou mudança de dimensões. Foram corrigidos também `.aq-ws-card`, `.aq-central-reference-card`, `.aq-premium-card` e os botões legados. ETF, Criptomoedas e Carteira Global tinham hit regions deslocadas em relação à arte; as coordenadas foram corrigidas.
- Mantidas as melhorias mobile da main. A regra antiga de controles flutuantes ficou restrita ao cockpit raster; o novo cabeçalho não cobre o ticker.
- Rótulos e números nativos em PT-BR. Fechamento do Dia, Calendário Econômico e Eventos Geopolíticos seguem o padrão de bordas e contraste do cockpit.

## Descoberta das 19 funções — revisão final do Trader

Continuação confirmada antes de editar: branch `integration/trader-main-refinement-20261003`, head `eb4bad9f61b8d0972eaca32c0c2b80531cace964`, Draft PR #551. PR #552 não foi tocada.

No desktop e no tablet, a barra lateral permanece com o título **Funções · 19** e os 19 botões diretamente na lista, com rolagem interna quando necessário. Nas páginas profundas, a navegação lateral também continua disponível. Nenhuma função é filtrada por breakpoint ou modo.

No mobile, acima da home e também nas páginas profundas, o acesso **Funções do Trader · 19** apresenta a instrução **Ver todas as funções · inclui avançadas**. Ao abrir, mostra a lista completa em duas colunas, com rolagem interna. Não existe um segundo grupo recolhido para esconder as funções avançadas. Os cards e demais atalhos da home foram preservados.

Iniciante oferece orientação simplificada, com aviso explícito de que funções avançadas continuam disponíveis. Avançado oferece acesso direto com orientação correspondente. Ambos apresentam as mesmas 19 funções e conservam o modo ao navegar e voltar à home; o modo não muda permissões nem disponibiliza dados inexistentes.

Lista preservada: Início; Radar Mestre; Radar; Painel Mestre; Macro; Micro; Geopolítica; Fundamentalista; ICT/SMC; Calendário Econômico; Pré-Notícia; Laboratório/Backtests; Paper Trading; Guardião de Risco; Academia; Diário; Vídeos/Conteúdo; AION Trader; Perfil/Configurações. Nenhuma função foi removida.

O novo teste de contrato compara a lista com as 19 rotas explicitamente esperadas, sem duplicatas ou grupos recolhidos. O teste Chromium percorre cada uma nos dois modos em 1280×720, 1024×768, 768×1024 e 390×844; verifica descoberta, clique, retorno à home, cards preservados, geometria de hover/focus, ausência de overflow e reduced-motion determinístico. Gera capturas da home, lista mobile aberta, Iniciante, Painel Mestre, ICT/SMC e retorno.

Pendências de dados permanecem: sem cotação residente validada, preço/variação mostram `—`, estados ficam `PRÉVIA` ou aguardando dados. A lista Top 10 da home ainda é uma estrutura em ordem do universo, não um ranking validado. Conteúdos e análises não conectados permanecem identificados como prévias. Nenhuma API/provider ou lógica financeira foi alterada.

`reference_html(..., market_items=[...])` e o estado residente `atlasquant_validated_market_items` aceitam registros com `asset`, `source`, `as_of` ISO com fuso e `validated=True`. Campos opcionais: `price`, `change_pct`, `score`, `bias` (Compra/Venda/Neutro), `series` numérica real. A ordem recebida é mantida. Dados ausentes, inválidos, futuros ou com mais de uma hora não viram preço, percentual ou ranking. A camada não coleta APIs, não calcula sinais e não modifica o motor financeiro. A lista Forex continua separada das outras classes; os 28 pares permanecem no Radar.

## Validação da revisão final

- Integração local atualizada: 160 testes e 48 subtestes passaram; inclui dois contratos explícitos das 19 rotas, um para cada modo.
- Compilação dos módulos e testes alterados e `git diff --check` passaram.
- A nova matriz Chromium e as capturas estão no teste `test_trader_19_functions_discoverable_and_clickable_in_both_modes`; as evidências finais e o status dos workflows são publicados junto ao Draft PR #551.
- O harness de prévia inicializa o modo Avançado no estado, de acordo com seu rótulo inicial. Não modifica autenticação, RBAC ou a inicialização de produção.

## Validação anterior no head de partida

- Integração local: 158 testes e 48 subtestes passaram.
- Contratos de apresentação: 35 testes passaram.
- Compilação dos quatro módulos de execução alterados passou.
- Chromium verifica cliques, setas/teclado do ticker, hover e foco sem alteração do retângulo, Painel Mestre, ausência de ticker em Negócios e overflow em 1280×720, 1024×768, 768×1024 e 390×844.
- Chromium local: varredura completa das cinco áreas passou em 135,13 s; teste adicional da Central e dos três seletores legados passou em 15,59 s. Hover/focus, rolagem e retorno ao topo foram verificados, incluindo capturas de Criptomoedas.
- Capturas finais e resultado atualizado de Chromium/CI ficam em `visual_review/` como artefatos locais e nos workflows do Draft PR.

## Limites reais

Não foi conectado novo provider de cotações. Quando não há lista residente validada, preço/percentual/viés ficam neutros. Os dez pares da home são uma estrutura de destaque em ordem do universo, identificada como ainda não ranqueada. Vídeos, chat e conteúdo ainda não conectado mantêm as prévias existentes. A referência enviada tem resolução 768×512 e parte inferior cortada; os elementos gráficos têm essa resolução original. Textos da nova home Trader são nativos. Os ambientes Investimentos/AION preservam arte ilustrativa nos painéis do corpo, com aviso explícito de que esses dados pintados não são vivos.

Autenticação, RBAC, gates, AION Core, banco, APIs, providers, execução e lógica financeira não foram alterados. As únicas mudanças nos shells legados são estilos de interação. A entrada autenticada, os callbacks e os controles de acesso da main continuam responsáveis pela navegação.
