# AtlasQuant — AION Studio + Negócios Persistentes — 2026-09-23

## Objetivo

Transformar Studio e Negócios de painéis demonstrativos em workspaces persistentes do AION, mantendo publicação externa bloqueada até existir integração real, Guardian e aprovação.

## Studio

Criado `atlasquant_aion_studio.py`.

O Studio agora registra no Checkpoint Mestre:

- ideias;
- objetivo;
- canais;
- formato;
- duração;
- público;
- tom;
- CTA;
- status;
- aprovação;
- evidência de publicação, quando existir.

### Canais preparados

- Instagram;
- TikTok;
- YouTube.

### Roteiro-base

Cada projeto pode gerar um storyboard determinístico com:

- Gancho;
- Contexto;
- Demonstração;
- Prova/clareza;
- CTA.

O roteiro-base inclui guardrails:

- não prometer rentabilidade;
- não tratar backtest como resultado futuro;
- não afirmar recurso inexistente;
- distinguir demonstração real de conceito futuro.

### Publicação

Criar ou aprovar projeto **não publica**.

O preflight exige:

1. conteúdo aprovado;
2. sessão ADMIN;
3. feature flag social;
4. aprovação explícita;
5. Guardian.

Mesmo quando o preflight fica elegível, ele retorna `executes_publish=false`.

Um conteúdo só pode ser marcado como `PUBLISHED` quando um conector futuro devolver evidência concreta e confirmada, como ID externo ou URL.

## Negócios

Criado `atlasquant_aion_business.py`.

A área Negócios registra:

- produto;
- canal;
- fornecedor;
- fonte da pesquisa;
- URL/referência;
- estado da evidência;
- nota sobre tendência/demanda;
- preço estimado;
- custo unitário;
- taxa da plataforma;
- frete/logística;
- impostos;
- outros custos;
- lucro por unidade;
- margem líquida;
- ROI sobre custo;
- aprovação;
- evidência de anúncio live, quando existir.

### Canais preparados

- Mercado Livre;
- TikTok Shop;
- Outro.

### Regra da Verdade de tendências

Um produto não pode ser chamado automaticamente de tendência ou campeão de vendas.

`trend_assessment` só permite chamar de tendência quando:

- `truth_state=CONFIRMED`;
- existe fonte registrada;
- existe evidência/nota sobre a demanda.

“Best-seller” continua false por padrão e não é inferido a partir de margem ou opinião.

### Economia unitária

O AION calcula deterministicamente:

- custo total;
- lucro líquido por unidade;
- margem líquida;
- ROI sobre custo.

Esses cálculos usam valores fornecidos pelo administrador; não são vendas reais confirmadas.

### Sustentabilidade do AtlasQuant

O painel mantém a meta:

- custo mensal do ecossistema;
- lucro líquido informado;
- percentual coberto;
- valor restante para cobrir.

Isso permanece separado de trading.

### Marketplace

Aprovar um produto **não publica anúncio**.

O preflight exige:

1. produto aprovado;
2. economia unitária preenchida;
3. feature flag de marketplace;
4. aprovação explícita;
5. Guardian.

Um anúncio só pode ser marcado `LIVE` com evidência concreta de um conector futuro.

## Checkpoint Mestre v3

A memória passa a conter:

`studio.projects`

e

`business.products`

com digests próprios.

Checkpoints antigos são atualizados em memória sem afirmar que a migração foi persistida até o administrador salvar o Checkpoint Mestre.

## Interface

O Command Center ADMIN passa a mostrar no Studio:

- total de projetos;
- em revisão;
- aprovados;
- publicados confirmados;
- criação persistente;
- storyboard;
- aprovação;
- status de publicação.

Em Negócios passa a mostrar:

- produtos pesquisados;
- candidatos com margem positiva;
- tendências confirmadas;
- cobertura dos custos;
- cadastro de produto;
- evidência;
- unit economics;
- aprovação;
- status de marketplace.

## O que continua bloqueado

- postagem real Instagram/TikTok/YouTube;
- anúncio real Mercado Livre/TikTok Shop;
- leitura automática de pedidos;
- compra automática de estoque;
- pagamentos;
- trading real.

## Gate

Antes de merge:

- Quality Tests;
- Release Readiness;
- UI Smoke;
- Mobile DOM;
- revisão do diff.

Produção continua exigindo Production Build Identity para confirmação exata do bundle.
