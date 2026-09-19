# AtlasQuant

Market Intelligence Platform — versão privada.

O AtlasQuant integra contexto macroeconômico, força relativa de moedas, Federal Reserve, scanner técnico, ICT/SMC, Market Map, controles de integridade, pesquisa histórica, Paper Trading e auditoria em uma única aplicação.

## Estado

A base atual é voltada a análise, pesquisa e uso privado. Ordens reais, conexão com broker, promoção automática de modelos e alteração automática de pesos/Gate permanecem desativadas.

Para o estado detalhado da release atual, consulte `docs/release/ATLASQUANT_RELEASE_FINAL.md`.

## Princípios

- dados ausentes, inválidos ou stale falham de forma conservadora;
- score não é probabilidade de lucro;
- pesquisa histórica não autoriza operação futura;
- Safety Core funciona como veto independente;
- evidência operacional mutável pertence ao runtime, não ao código de release;
- promoção de release/modelo exige revisão humana.

## Principais áreas

- Central e Painel Mestre;
- moedas, EUA, pares e Fed;
- Market Map e decisão operacional;
- notícias e Macro Briefing;
- Backtest, Walk-Forward e laboratórios de validação;
- Autopilot e Paper Trading;
- Academy;
- Conta, instalação e área comercial.

## Plataformas

A distribuição atual é PWA instalável pelo navegador em Android, iPhone/iPad, Windows, macOS e Linux. Publicação nativa na Google Play e Apple App Store é uma etapa separada e não é declarada como concluída.

## Desenvolvimento

Antes de alterar o motor, preserve os contratos de Safety Core, integridade/frescor, ausência de look-ahead e separação entre pesquisa e execução.

Checkpoints e histórico detalhado permanecem em `CONTEXTO_DO_PROJETO.md`, `HISTORICO_DE_ALTERACOES.md` e `docs/continuidade/`.

Documentos com nomes USD Macro Pro / V11.x são registros históricos e não definem o branding atual do produto.
