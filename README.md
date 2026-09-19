# AtlasQuant

Market Intelligence Platform — versão privada.

O AtlasQuant integra contexto macroeconômico, força relativa de moedas, Federal Reserve, scanner técnico, ICT/SMC, Market Map, controles de integridade, pesquisa histórica, Paper Trading, auditoria, Academy, suporte e preparação comercial em uma única aplicação.

## Estado

A base técnica e a preparação interna do produto estão consolidadas para uso privado e revisão comercial. Ordens reais, conexão com broker, promoção automática de modelos e alteração automática de pesos/Gate permanecem desativadas.

A preparação comercial interna inclui:
- Central de Suporte;
- Guia informativo de Corretoras & Plataformas;
- Academy textual e roteiros/storyboards dos vídeos;
- infraestrutura/contrato seguro do Assistente de Voz;
- PWA instalável;
- USER / SALES / ADMIN;
- rascunhos internos de Termos, Privacidade e Divulgação de Riscos;
- checklist e contrato técnico fail-closed para cobrança;
- inventário técnico das fontes de dados/licenciamento;
- checklists e metadados para empacotamento nativo.

Isso **não** significa lançamento público concluído. Revisão jurídica, licenças comerciais dos provedores, provedor real de pagamentos, TTS externo, renderização/publicação dos vídeos e pacotes assinados/publicação nas lojas continuam dependências externas.

Para o estado detalhado da release atual, consulte `docs/release/ATLASQUANT_RELEASE_FINAL.md`. Para o primeiro acesso, use `docs/release/USER_QUICKSTART.md`.

## Princípios

- dados ausentes, inválidos ou stale falham de forma conservadora;
- score não é probabilidade de lucro;
- pesquisa histórica não autoriza operação futura;
- Safety Core funciona como veto independente;
- evidência operacional mutável pertence ao runtime, não ao código de release;
- promoção de release/modelo exige revisão humana;
- preparação interna nunca é convertida automaticamente em aprovação externa.

## Principais áreas

- Central e Painel Mestre;
- moedas, EUA, pares e Fed;
- Market Map e decisão operacional;
- notícias e Macro Briefing;
- Backtest, Walk-Forward e laboratórios de validação;
- Autopilot e Paper Trading;
- Academy;
- Conta, instalação, suporte e área comercial.

## Plataformas

A distribuição atual é PWA instalável pelo navegador em Android, iPhone/iPad, Windows, macOS e Linux.

O repositório contém metadados e checklists para preparação de empacotamento Android/iOS, mas **não** declara pacote assinado ou publicação na Google Play/Apple App Store antes da evidência correspondente.

## Desenvolvimento

Antes de alterar o motor, preserve os contratos de Safety Core, integridade/frescor, ausência de look-ahead e separação entre pesquisa e execução.

Checkpoints e histórico detalhado permanecem em `CONTEXTO_DO_PROJETO.md`, `HISTORICO_DE_ALTERACOES.md` e `docs/continuidade/`.

Documentos com nomes USD Macro Pro / V11.x são registros históricos e não definem o branding atual do produto.
