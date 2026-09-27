# Pendências que dependem de Mikael

Este arquivo registra somente decisões, credenciais ou recursos externos que o
agente não pode resolver com segurança. Nenhum item bloqueia o restante do
trabalho local.

## Scanner técnico dos 28 pares

- **Credencial/provedor de candles:** o repositório usa Twelve Data para H4,
  H1 e M15, mas a credencial não está disponível no ambiente de desenvolvimento.
  A interface e o pipeline permanecem fail-closed: pares sem candle aparecem
  como `SEM DADOS`/`BLOQUEADO`, sem confiança artificial.
- **Worker contínuo:** confirmar posteriormente onde o coletor periódico dos 28
  pares deve executar e qual orçamento/cota do provedor pode consumir. Nenhum
  job externo foi ativado e nenhum secret foi alterado.

## Laboratório

- **PPR:** fornecer definição objetiva, campos de entrada, invalidação, saída e
  versão das regras. Até isso acontecer, PPR permanece `BLOQUEADO`.

## Identidade e voz

- **Nome do Administrador:** se desejar a saudação literal “Mikael”, configurar
  futuramente `AION_ADMIN_DISPLAY_NAME=Mikael`. O agente não altera secrets.
- **Voz de Mikael:** fornecer gravação autorizada, consentimento de uso, idiomas
  e provedor escolhido. Até lá, o provider deve aparecer como “não configurado”.

## Vendas

- **Visibilidade para USER:** decidir se o item “Vendas” deve ficar visível com
  aviso de acesso restrito ou ser ocultado. A autorização SALES/ADMIN permanece
  obrigatória independentemente da escolha visual.

## Serviços externos e publicação

- Contas, tokens e decisões de provedores para vídeo, transcrição, voz,
  marketplaces, afiliados e tracking.
- Aprovação humana antes de qualquer publicação, compra, pagamento, anúncio,
  contratação, merge ou deploy.
