# AION — Live Event Intelligence

Data de consolidação: 2026-09-25

## Objetivo

Criar a fundação para o AION acompanhar eventos macroeconômicos, notícias e
risco geopolítico usando somente evidências que já chegam ao AtlasQuant.

Este bloco não cria um coletor web novo e não afirma que existe vigilância 24/7
em produção. O motor classifica o que o runtime atual fornece.

## Fontes nesta fundação

- Currency News persistido do AtlasQuant;
- proveniência do snapshot de notícias;
- próximo evento macro já resolvido pelo calendário;
- Reliability Guardian e Source Mesh como contexto de qualidade.

## Contrato de verdade

### Notícias

Uma manchete/reportagem observada recebe estado INFERENCE quando a proveniência
do snapshot é confirmada.

Isso significa: o AtlasQuant observou uma reportagem. Não significa que o AION
confirmou de forma independente que o evento descrito aconteceu exatamente
como escrito.

### Agenda macro

Um evento agendado pode ser CONFIRMED apenas quando há proveniência explícita
do calendário.

Agenda confirmada não confirma a futura reação do mercado.

### Impacto

Todos os canais de impacto são HYPOTHESIS.

Exemplo para escalada geopolítica:
- petróleo: pressão de alta possível;
- ouro: fluxo defensivo possível;
- USD: fluxo defensivo possível;
- JPY/CHF: fluxo defensivo possível;
- índices: pressão negativa possível.

O motor descreve mecanismo econômico provável. Ele não gera sinal de trade.

## Frescor

Snapshot de notícias antigo não gera breaking alert.

Regras iniciais:
- snapshot de notícias: máximo 120 minutos;
- notícia individual para alerta: máximo 180 minutos.

Os limites podem ser refinados no Laboratório com evidência, nunca alterados
silenciosamente pelo próprio AION.

## Deduplicação

Eventos de notícia usam story_id quando disponível. A mesma história repetida
em várias moedas é consolidada em um único evento com moedas relacionadas.

## Alertas

Estados:
- NONE
- WATCH
- HIGH_REVIEW
- URGENT_REVIEW

URGENT_REVIEW significa prioridade de revisão humana, não confirmação total do
fato e não autorização operacional.

Eventos frescos podem entrar no Pulso Executivo como P1/P2 para chamar atenção
do administrador.

## Monitoramento contínuo

Campos de segurança:
- continuous_runtime_required = True
- continuous_runtime_confirmed = False
- automatic_notification_sent = False
- notification_requires_integration = True

Somente um runtime contínuo validado poderá mudar a verdade operacional de
monitoramento 24/7. Código na main não é prova de vigilância contínua.

## Travas

- notificação externa automática: DESATIVADA;
- publicação automática: DESATIVADA;
- mudança automática de score: DESATIVADA;
- sinal de trade: NÃO;
- ordens reais: BLOQUEADAS.
