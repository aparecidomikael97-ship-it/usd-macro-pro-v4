# AtlasQuant — Checklist de Publicação em Lojas

**PREPARAÇÃO INTERNA — PWA PRONTA NÃO É PUBLICAÇÃO NATIVA.**

## Google Play / Android
- Definir pacote/app id.
- Gerar pacote assinado a partir de pipeline reprodutível.
- Preparar ícone, screenshots, descrição, classificação etária e política de privacidade.
- Validar requisitos de dados, permissões e billing quando aplicável.
- Testar instalação/upgrade em dispositivos reais.
- Submeter e registrar resultado da revisão.

## Apple App Store / iOS/iPadOS
- Definir bundle id e conta/certificados.
- Gerar build assinado e validar em TestFlight.
- Preparar metadados, screenshots, privacidade e classificação.
- Revisar regras de login, assinatura e conteúdo financeiro.
- Submeter e registrar resultado da revisão.

## Desktop
A PWA cobre instalação via navegador em Windows/macOS/Linux. Empacotadores nativos, assinatura de código e lojas de desktop são etapas separadas.

Nenhuma loja deve ser marcada como pronta antes de existir pacote assinado e evidência de publicação/revisão correspondente.
