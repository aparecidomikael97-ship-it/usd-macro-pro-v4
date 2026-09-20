# AtlasQuant — Paper com atribuição explícita de operacional · 20/09/2026

Este bloco prepara o Paper/Forward para alimentar o Passaporte do Operacional
sem adivinhar qual setup gerou uma operação.

## Regra central

Um trade Paper só pode contar como evidência de um operacional quando o
`setup_id` estava explicitamente presente na origem do sinal, ou quando existe
uma marcação manual com proveniência explícita.

O AtlasQuant **não** transforma automaticamente:

- FVG detectado;
- estado de ICT/SMC;
- score alto;
- gain/loss;
- reação de preço posterior;

em "este trade pertence ao setup X".

Isso evita viés retrospectivo.

## Paper Trading

O Paper V11.2 passa a preservar, quando disponíveis:

- setup_id;
- setup_attribution;
- data_quality_pct;
- regime D1/W1 capturado no sinal;
- sessão ativa capturada no sinal.

Atribuições nativas usam `EXPLICIT_INPUT`. Trades sem setup permanecem
`UNATTRIBUTED`.

O resumo por setup só usa proveniência confiável
(`EXPLICIT_INPUT` / `MANUAL_TAG`).

## Setup Audit V11.4

O audit prospectivo preserva setup/proveniência e prefere sessão/regime já
congelados no próprio trade. O Market Map do momento da auditoria é apenas
fallback para registros antigos.

O resumo informa quantos trades fechados possuem atribuição explícita, mas
continua sem selecionar estratégia ou habilitar trading real.

## Bridge Paper → Forward

Novo módulo:

- `atlasquant_paper_setup_bridge.py`

Ele converte apenas operações fechadas e explicitamente atribuídas para o
formato do Diário Forward/Paper.

Para entrar na evidência, o registro também precisa ter:

- setup reconhecido;
- resultado R finito;
- qualidade de dados válida;
- sessão e regime;
- direção;
- entrada, stop e alvo válidos.

O bridge publica `setup_inference_used=False`.

## Runtime → Admin

O Admin tenta ler, de forma somente-leitura, o arquivo runtime:

- `dados/paper_setup_audit_v114.csv`

A leitura é permitida apenas na branch dedicada de runtime. `main` e
`atlasquant-dev` continuam bloqueadas para esse uso.

Se existirem trades explicitamente atribuídos, o Admin pode cruzá-los com o
Passaporte correspondente automaticamente. Evidência de um setup nunca é
reaproveitada em outro setup.

O Diário Forward/Paper manual continua disponível como fallback e, quando o
nome não coincide, exige associação humana explícita.

## Estado atual

A infraestrutura está pronta para receber `setup_id` explícito.

Os trades Paper antigos/genéricos que não possuem setup_id **não são
retroativamente classificados**. Para automatizar a coleta por operacional, os
geradores/modelos específicos deverão enviar o setup_id no instante em que
criarem o sinal Paper.

## Segurança

- nenhuma inferência retrospectiva de setup;
- nenhuma promoção automática;
- nenhum winner automático;
- nenhum ajuste automático de parâmetros;
- nenhuma ordem real;
- nenhuma conexão nova com corretora;
- runtime é somente leitura neste bridge;
- evidência de Paper continua separada de Backtest e OOS.
