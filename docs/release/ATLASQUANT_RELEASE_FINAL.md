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
- Academy textual estruturada.

## Segurança operacional

O estado atual preserva:

- ordens reais desativadas;
- conexão com broker desativada;
- promoção automática desativada;
- alteração automática de pesos/Gate desativada;
- score não é apresentado como probabilidade de lucro;
- dados ausentes, inválidos ou stale falham de forma conservadora.

## Validação quantitativa

Resultados históricos e paper não constituem previsão de resultado futuro. Performance, calibração, estabilidade e Shadow acumulam evidência para revisão humana. Amostra insuficiente não autoriza promoção automática.

## Distribuição

A PWA cobre instalação pelo navegador em Android, iPhone/iPad, Windows, macOS e Linux.

Google Play e Apple App Store continuam etapas separadas. Exigem empacotamento, assinatura, contas de desenvolvedor e processo de publicação/revisão das lojas.

## Comercialização pública

Uso privado e prontidão comercial são estados diferentes. Antes de venda pública, o Commercial Launch Guard exige evidência explícita para termos/privacidade/riscos, licenciamento comercial das fontes de dados, suporte, Academy mínima, cobrança/assinatura, distribuição e controles administrativos.

O AtlasQuant não certifica automaticamente requisitos jurídicos, licenças externas, cobrança ou publicação em lojas.

## Arquitetura de branches

- `main`: código/release estável;
- `atlasquant-runtime`: evidência e estado operacional mutável;
- branches de integração/release: mudanças revisáveis antes de entrar no `main`.

Dados operacionais mutáveis não devem voltar a ser usados como motivo para commits contínuos no `main`.

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

1. acabamento visual e simplificação da navegação sem remover funções;
2. atualização do branding/documentação legada;
3. acumulação de evidência quantitativa;
4. requisitos externos de comercialização;
5. empacotamento nativo de lojas, se desejado;
6. recursos futuros (COT/CFTC, futuros/opções e expansão técnica) somente após validação própria.

Execução real permanece fora desta release.
