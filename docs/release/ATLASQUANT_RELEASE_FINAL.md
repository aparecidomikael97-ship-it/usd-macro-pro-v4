# AtlasQuant — Release Final

Atualizado em 19/09/2026.

Este documento descreve o estado atual do produto. Checkpoints históricos permanecem nos documentos de continuidade e não devem ser lidos como o estado presente.

## Estado atual

### Base técnica — pronta para uso privado

- aplicação AtlasQuant com interface responsiva;
- macro, força relativa, Fed e comparação de pares;
- scanner técnico H4/H1/M15;
- ICT/SMC e Market Map;
- Decision Integrity e Safety Core fail-closed;
- Autopilot de coleta/análise;
- Paper Trading com custos/fricção;
- backtest, walk-forward, robustez e evidência reproduzível;
- Performance, Calibration, Stability e Shadow Mode;
- Flight Recorder e trilha de auditoria;
- acesso USER / SALES / ADMIN;
- PWA instalável pelo navegador;
- Central de Suporte;
- Guia informativo de Corretoras & Plataformas;
- Academy textual estruturada;
- roteiros/storyboards dos vídeos da Academy;
- contrato interno seguro para Assistente de Voz/TTS;
- pacote interno de preparação comercial;
- contrato técnico fail-closed para futura integração de billing;
- inventário técnico das fontes de dados/licenciamento;
- metadados e checklists de preparação para empacotamento nativo.

## Segurança operacional

O estado atual preserva:

- ordens reais desativadas;
- conexão com broker desativada;
- promoção automática desativada;
- alteração automática de pesos/Gate desativada;
- score não é apresentado como probabilidade de lucro;
- dados ausentes, inválidos ou stale falham de forma conservadora;
- voz, billing, publicação em lojas e preparação comercial não alteram permissões de trading.

## Validação quantitativa

Resultados históricos e paper não constituem previsão de resultado futuro. Performance, calibração, estabilidade e Shadow acumulam evidência para revisão humana. Amostra insuficiente não autoriza promoção automática.

## Distribuição

A PWA cobre instalação pelo navegador em Android, iPhone/iPad, Windows, macOS e Linux.

A preparação de empacotamento nativo possui metadados e checklists internos. Google Play e Apple App Store continuam etapas externas separadas, pois exigem toolchain autorizado, assinatura, contas de desenvolvedor, testes em dispositivos e processo de publicação/revisão.

## Preparação comercial interna

O AtlasQuant já mantém no repositório:

- rascunhos internos de Termos de Uso, Política de Privacidade e Divulgação de Riscos;
- checklist de licenciamento comercial de dados;
- inventário técnico explícito das fontes/provedores;
- checklist e contrato técnico de cobrança/assinatura;
- checklist de publicação em lojas;
- agregador de launch readiness fail-closed.

A preparação interna pode ser marcada como completa **sem** marcar dependências externas como concluídas.

## Dependências externas ainda obrigatórias

Antes de venda pública completa permanecem necessárias:\n\n1. configurar e validar o primeiro ADMIN no ambiente de produção;\n2. revisão jurídica/privacidade dos documentos finais;
3. confirmação contratual/licenciamento comercial dos provedores de dados;
4. escolha e integração real de um provedor de pagamento/assinatura;
5. configuração de provedor TTS externo para narração;
6. renderização e publicação dos vídeos da Academy;
7. geração de pacotes assinados e publicação/revisão em Google Play/Apple App Store;
8. revisão humana final do lançamento.

Nenhum destes itens é inferido automaticamente por existir código, checklist ou documentação.

## Arquitetura de branches

- `main`: código/release estável;
- `atlasquant-runtime`: evidência e estado operacional mutável;
- branches de integração/release: mudanças revisáveis antes de entrar no `main`.

Dados operacionais mutáveis não devem voltar a ser usados como motivo para commits contínuos no `main`.

## Backup automático da fonte

O workflow `AtlasQuant - Source Backup ZIP` cria um ZIP da `main` em cada push e também pode ser executado manualmente. O artefato inclui manifesto, SHA-256 e retenção temporária no GitHub Actions.

O backup contém a fonte estável da release e não substitui o histórico Git nem a branch mutável de runtime.

## Auditoria automatizada de prontidão

O workflow `AtlasQuant - Release Readiness` executa periodicamente e em mudanças relevantes para confirmar que:
- a preparação interna continua completa;
- os documentos de handoff continuam presentes;
- as dependências externas não são inferidas como concluídas;
- broker e ordens reais continuam desativados.

Essa auditoria complementa Quality, Production Health e Browser Smoke; ela não publica nem promove automaticamente.

## Regra de release

Mudanças de acabamento devem preservar o motor. Alterações de UI/documentação não devem modificar matemática macro, Safety Core, Gate, scanner, Paper Trading ou regras de execução.

Antes de promoção:

1. compilação e Quality verdes;
2. source/runtime parity quando aplicável;
3. revisão do diff;
4. health check;
5. browser smoke desktop e mobile;
6. revisão humana.

## Próximas fases

As próximas fases dependem majoritariamente de terceiros/contas externas:

1. concluir revisão jurídica e privacidade;
2. validar licenciamento comercial das fontes;
3. escolher/conectar billing;
4. escolher/conectar TTS;
5. produzir mídia final da Academy;
6. assinar/submeter apps nativos, se desejado;
7. continuar acumulando evidência quantitativa do runtime.

Recursos futuros como COT/CFTC, futuros/opções e expansão técnica permanecem fora desta release até terem validação própria.

Execução real permanece fora desta release.
