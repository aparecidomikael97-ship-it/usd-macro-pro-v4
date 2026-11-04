# AtlasQuant Trader — paridade visual com a prévia e correção de tradução LAB

Data: 02/11/2026 | PR #1803 DRAFT | HARD NO-GO

## Evidência reportada

Uma captura enviada pelo proprietário da rota Trader Radar mostra a estrutura já instalada, mas com apresentação inferior à prévia interativa:
- Barra lateral estreita com textos corrompidos: no lugar de **Início**, aparece um texto longo sem relação com o menu; **Scanner Técnico** é reordenado como "Técnico de scanner".
- A marca **A** fica **UM**, típico de tradução automática inglesa "A" para artigo português "um". O rótulo de força das moedas também aparece como "seis".
- O topo, a área de aviso e oito cartões vazios ocupam muito espaço vertical; o Top 10 acaba fora da primeira janela.
- O código já contém os textos brasileiros esperados; esta evidência **sugere fortemente** tradução automática do Edge, mas não constitui um diagnóstico direto de extensões/configuração do navegador.

## Corrigido SOMENTE na branch LAB

Arquivo atlasquant_trader_radar_compact_ui.py:
- Protegido o componente e seu menu com `lang="pt-BR" translate="no"` e classe `notranslate`, para indicar que botões e marca não devem ser retraduzidos. Alguns tradutores ignoram esse atributo; o usuário também pode selecionar "Não traduzir este site" no Edge.
- Ajustado visual da versão aprovada: menu mais compacto, cards legíveis e baixos, título futurista sem excesso de altura, espaçamentos mais proporcionais e comportamento móvel preservado.
- Quando NÃO há dados diários validados, o **Top 10** mostra um único quadro explicativo e não dez cartões grandes com "Posição N · Sem par validado". Não cria líderes ou números fictícios.
- Quando os dados completos de 28 pares são validados, a ordenação legítima Top 10 continua funcionando e o código de cálculo **não foi alterado**.
- Os oito cartões de moedas continuam visíveis com "AGUARDANDO" quando não há dados; nenhum sinal, score, força relativa ou cotação é presumido.

## Validação

test_atlasquant_trader_radar_compact_ui.py atualiza a asserção anterior que exigia dez cartões vazios e adiciona **2 testes**:
1. Idioma PT-BR, proteção de tradução e os quatro menus corretos.
2. Layout compacto, oito cartões, somente um estado vazio de Top 10, sem gerar um ranking falso.

Também preserva os testes de proteção contra dados incompletos, oito moedas/28 pares, índices WIN/WDO, macro e acesso sem ordens. As 19 pipelines CI devem ser conferidas no HEAD antes de qualquer futura homologação.

## Critério de validação visual manual

Abrir a prévia LAB no Edge e comparar com a captura enviada: o menu deve mostrar exclusivamente **Início, Radar, Scanner Técnico, Painel Mestre**; a logo A não pode se transformar em UM; os cartões devem caber em área mais compacta; Top 10 indisponível deve aparecer uma única vez. Validar em desktop e mobile.

Se persistir retradução, **desativar Tradução automática do Edge para este site** e recarregar. Atributos HTML não controlam necessariamente extensões instaladas no navegador.

**Não foi feito merge ou deploy**; sem Worker, cron, ordens, custo ou ingestão de dados reais. PR continua DRAFT/HARD NO-GO.
