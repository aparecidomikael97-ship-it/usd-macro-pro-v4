# Interface premium AtlasQuant

Camada visual própria. Não altera cálculo de mercado, ranking, autenticação, secrets, Render ou execução.

## Design system

Tokens em `atlasquant_premium_shell.TOKENS` e `PREMIUM_CSS`:

- Fundo `#07111f` / `#0c1a2c`
- Superfície `#102338` / `#17304a`
- Texto `#f5f8fc`, apoio `#d7e4f2`
- Destaque latão `#d7b56d`, maré `#8fd0c4`
- Sucesso `#3dbe8b`, atenção `#e2b657`, perigo `#e36b78`, info `#8eb7e8`
- Raio 18px nos cartões, 12–14px nos painéis internos
- Sombra suave, borda `rgba(198,214,232,.22)`
- Hover levanta o cartão 2px; foco usa contorno latão
- Desabilitado mantém texto `#d7e4f2` sobre `#1c3048`
- `prefers-reduced-motion` desliga entrada e pulso

## Componentes

Funções em `atlasquant_premium_shell.py`:

- `premium_module_card_html`
- `section_hero_html`
- `status_badge_html`
- `metric_card_html` / `navigation_tile_html`
- `alert_card_html`
- `premium_panel_html`
- `empty_state_html`
- `loading_state_html`

## Como adicionar um setor

1. Inclua um item em `PREMIUM_MODULES` com `id`, `sector`, `title`, `motif`, `summary`.
2. `page` precisa ser um rótulo que já existe em `NAVIGATION_LABELS` ou `🧠 AION`.
3. `fast_page` fica vazio se o shell rápido do Iniciante não tiver essa área.
4. Se precisar de um desenho novo, acrescente um SVG em `_svg`. Não use arquivo externo.
5. Não ligue o cartão a ordem, secret, deploy ou regra de risco.

O clique só grava `atlasquant_premium_nav_target`. Quem aplica o destino, antes do seletor, é `consume_premium_navigation`.

## Decisões

- A home visual é um catálogo. O seletor estável continua existindo para celular, teste e teclado.
- Paper Trading não abre mesa. O cartão leva ao Backtest já existente e deixa explícito que nenhuma ordem é enviada.
- Radar segue com 28 pares, Top 10 e filtros. O movimento é um ponto CSS, sem vídeo.
- Painel Mestre continua na matriz atual (`head(7)`). O texto deixa claro que esse universo não é o Radar de 28 pares.
- Iniciante ganha uma faixa com ativo, viés, confiança, operar ou não, risco, notícia e próximo passo, lida dos campos que o Radar já calculou.
