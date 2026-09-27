# AION — Checkpoint do Ecossistema e UX

Data: 2026-09-27

Estado: **DECISÕES APROVADAS · OBRIGATÓRIAS · NÃO ALTERAM A ORDEM DO CHECKPOINT MESTRE**

## Regra de continuidade

Este documento é um adendo do **AION Checkpoint Mestre NextGen aprovado em 2026-09-25**.

As decisões abaixo **não criam um cronograma novo** e **não autorizam desviar da sequência já aprovada**. Elas refinam a arquitetura visual, a separação dos workspaces e as regras de acesso. Quando a etapa correspondente chegar no cronograma, estas regras passam a ser requisitos obrigatórios da implementação.

A execução continua obedecendo às regras existentes de segurança: sem autoelevação de permissão, sem ordem real, sem gasto, sem publicação externa, sem merge/deploy/alteração de produção ou secrets sem autorização apropriada.

## Ordem de prioridade operacional — obrigatória

A sequência estratégica aprovada deve ser preservada:

1. **AION primeiro** — consolidar o núcleo inteligente, memória/checkpoints, administração, desenvolvimento, vídeo/conteúdo, orquestração, segurança, ferramentas e capacidade de apoiar os demais domínios.
2. **AtlasQuant / sistema depois** — usar o AION já mais maduro para acelerar, revisar, testar e evoluir o AtlasQuant Trade e a Central do Ecossistema.
3. **Monetização e demais núcleos na sequência** — estruturar e amadurecer Negócios/Vendas, Afiliados, Dropshipping, Conteúdo/Clipagem e Investimentos/Renda Fixa de forma separada e segura.

Racional aprovado: colocar o AION em condição forte primeiro para que ele ajude a construir e melhorar o próprio ecossistema. Depois, levar o sistema comercial a um nível que permita gerar receita legítima e sustentável, reinvestindo recursos na evolução contínua do AION e do ecossistema.

Essa lógica **não autoriza promessa de lucro, automação financeira, gasto, anúncio, publicação externa, ordem real ou investimento automático**. Monetização continua sujeita a produto real, validação, dados, controles, aprovação e risco explícito.

Novas ideias devem ser encaixadas na etapa correta dessa ordem; não devem criar uma fila paralela que faça o projeto abandonar o cronograma.

## AION como pilar do ecossistema

O **AION é o núcleo principal e independente**.

Ele não pertence exclusivamente ao AtlasQuant Trade. Deve operar como núcleo reutilizável que atende workspaces separados por domínio, sempre com isolamento de contexto, permissões e memória.

Workspaces/núcleos administrativos aprovados:

1. **AtlasQuant Trade**
2. **AtlasQuant Investimentos / Renda Fixa**
3. **AtlasQuant Negócios / Vendas**
4. **AION Core / Central**

Desenvolvimento, Vídeo/Conteúdo, Clipagem, Afiliados, Dropshipping e demais capacidades ficam ligados ao AION e/ou ao workspace de Negócios conforme o domínio, sem serem misturados ao shell de Trade.

## Regra de acesso ADMIN x USER

### ADMIN

O administrador possui acesso aos quatro núcleos da Central do Ecossistema:

- AtlasQuant Trade;
- AtlasQuant Investimentos / Renda Fixa;
- AtlasQuant Negócios / Vendas;
- AION Core / Central.

### USER / cliente comercial

O cliente do produto comercial deve ter acesso **somente ao AtlasQuant Trade**.

Investimentos, Vendas/Negócios e AION Core não devem aparecer como portas navegáveis para USER. A separação não é apenas visual: deve continuar protegida por autorização/entitlement no backend. Ocultar um item de menu nunca substitui controle de acesso.

## Central do Ecossistema após login

Para ADMIN, após autenticação deve existir uma tela simples de entrada com quatro portas claras, sem mistura de funcionalidades:

- **AtlasQuant Trade** — mercado, Radar, Painel Mestre, Macro, Pré-Notícia, Calendário, ICT/SMC, Laboratório, Backtest, risco e demais ferramentas de trading;
- **AtlasQuant Investimentos** — Renda Fixa, FIIs, dividendos, valuation, comparação de produtos e pesquisa patrimonial;
- **AtlasQuant Negócios** — Vendas, marketplace, catálogo, margem, fornecedores, afiliados, dropshipping, tracking, funil, conteúdo comercial e clipagem autorizada;
- **AION** — núcleo inteligente, Administração, Desenvolvimento, Vídeo/Conteúdo e demais capacidades administrativas autorizadas.

Para USER, o fluxo deve levar diretamente ao AtlasQuant Trade ou apresentar somente a porta Trade, conforme a melhor solução de UX validada em testes.

## Navegação do AtlasQuant Trade

A página de entrada do Trade não deve exigir que o usuário desça uma página longa para encontrar Radar, Painel Mestre, Macroeconomia, Pré-Notícia e demais áreas.

Os atalhos principais devem ficar **lado a lado em uma faixa/carrossel com rolagem lateral**, permitindo avançar para o lado com mouse/trackpad/touch.

Objetivo:

- reduzir rolagem vertical longa;
- evitar descer e depois subir a página para trocar de área;
- permitir que o usuário bata o olho e encontre rapidamente o módulo desejado;
- preservar boa experiência em desktop e mobile;
- manter acessibilidade por teclado, foco visível e navegação responsiva.

A orientação deve ser definida pelo comportamento funcional acima; não depender do uso informal dos termos “vertical” ou “horizontal”.

## Direção visual obrigatória

A interface deve continuar evoluindo. Não considerar “premium” somente porque contraste e overflow passaram nos testes.

Evitar estética genérica/clichê:

- bolas e cubos flutuantes;
- formas geométricas decorativas sem função;
- robô humanoide para representar o AION;
- neon excessivo;
- visual gamer/cyberpunk genérico;
- gráficos/candles falsos usados apenas como decoração.

Direção aprovada:

- identidade própria AtlasQuant/AION;
- grafite profundo e acabamento institucional;
- imagens/fundos discretos e específicos por domínio;
- profundidade e iluminação sutis;
- microinterações leves;
- informação em camadas: resumo -> detalhe -> diagnóstico avançado;
- alta legibilidade e performance preservada.

Assinaturas sugeridas, sem copiar identidade de terceiros:

- Painel Mestre: panorama financeiro abstrato, fluxos e contexto global;
- Radar: mapa abstrato de força/liquidez, não radar militar clichê;
- AION: arquitetura abstrata de dados, sem “robôzinho”;
- Laboratório: matrizes, evidências e linguagem de pesquisa/engenharia;
- Macro: ciclos e curvas econômicas abstratas, sem fabricar dados.

A referência externa pode inspirar **princípios de organização e experiência**, mas a execução visual deve ser autoral e não reproduzir identidade, assets, trade dress ou aparência característica de outro produto.

## Relação com o cronograma existente

Não reiniciar tarefas já concluídas e não criar nova fila paralela.

A sequência continua sendo governada pelo Checkpoint Mestre e pelos checkpoints técnicos posteriores. O refinamento de hoje entra **dentro da etapa de Central/Interface/UX**, sem substituir as prioridades já registradas para:

- AION Central;
- Memória/Checkpoint Mestre;
- Guardian/segurança;
- AtlasQuant Trade e seus motores;
- Laboratório/Backtest;
- Vídeo/Conteúdo/Clipagem;
- Negócios/Vendas/Afiliados/Dropshipping;
- Investimentos/Renda Fixa;
- Voz;
- Performance, testes e auditoria.

## Estratégia de desenvolvimento multi-IA preservada

Permanece a estratégia aprovada:

- **Codex** como referência forte de execução de desenvolvimento;
- **Cursor** como acelerador principalmente de trabalho visual/interativo e implementação assistida;
- **Claude Code** como referência de revisão/crítica quando aplicável;
- outros modelos/ferramentas podem ser usados como apoio quando trouxerem ganho real de velocidade ou qualidade e estiverem disponíveis;
- AION como orquestrador, sem conceder soberania a nenhuma ferramenta externa.

O uso de Cursor, GPT, Codex, Claude Code ou outra IA disponível serve para **acelerar a etapa atual do cronograma**, nunca para trocar a prioridade, abrir projeto paralelo ou conceder permissão adicional.

O uso dessas ferramentas não altera as regras de aprovação, não autoriza merge/deploy e não muda o cronograma por conta própria.

## Regra de aprovação externa

O AION pode preparar roteiro, imagem, vídeo, voz autorizada, clipagem, campanha, catálogo, análise, relatório e publicação em fila de aprovação.

Mas publicação, impulsionamento, compra de mídia, pagamento, contratação, operação financeira, alteração de credencial, merge, deploy ou ação equivalente continuam exigindo a aprovação apropriada.

## Próximo princípio operacional

Ao retomar trabalho, consultar primeiro:

1. Checkpoint Mestre NextGen;
2. este adendo de Ecossistema/UX;
3. estado técnico atual do repositório/PRs/produção;
4. próxima etapa pendente do cronograma já aprovado.

Se surgir uma nova ideia, registrá-la como refinamento da etapa correta em vez de criar uma nova sequência concorrente.
