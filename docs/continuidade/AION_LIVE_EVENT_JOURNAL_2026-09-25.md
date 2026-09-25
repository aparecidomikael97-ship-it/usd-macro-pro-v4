# AION — Live Event Journal & Background Watch

Data de consolidação: 2026-09-25

## Objetivo

Complementar o Live Event Intelligence já existente com histórico persistente e
prova auditável de continuidade do Autopilot, sem criar um segundo classificador
de notícias.

## Arquitetura

O classificador oficial continua sendo `atlasquant_aion_live_events.py`.

Esta camada adiciona somente:

- histórico deduplicado de eventos;
- primeiro e último avistamento;
- quantidade de vezes observadas;
- pico de urgência e pico de nível de alerta;
- heartbeats do ciclo background;
- prova fail-closed de continuidade aproximada de 24 horas;
- fila interna de candidatos a entrega futura;
- sincronização opcional com o Checkpoint Mestre.

## Runtime

Arquivo persistido pelo Autopilot:

`dados/aion_live_event_journal_v1.json`

O Autopilot reutiliza o mesmo snapshot de notícias já obtido pelo ciclo normal.
O Event Journal não adiciona consulta ao provedor.

Falha do journal é observável no status, mas não é transformada em execução de
mercado nem em fallback pago.

## Prova de continuidade

O sistema NÃO pode afirmar monitoramento 24/7 apenas porque o motor existe ou
porque alguns ciclos recentes rodaram.

`continuous_24h_confirmed=True` exige simultaneamente:

- cobertura mínima de aproximadamente 23 horas (1.380 minutos);
- pelo menos 40 heartbeats recentes;
- heartbeat mais recente com idade máxima de 75 minutos;
- maior lacuna entre ciclos de no máximo 90 minutos.

Antes disso o estado permanece:

- NOT_STARTED;
- BUILDING_EVIDENCE; ou
- STALE.

CONTINUOUS_24H confirma somente a continuidade observada pelos heartbeats
persistidos. Não garante disponibilidade futura e não prova que o Render/app
interativo está atualizado.

## Histórico deduplicado

Cada evento preserva:

- event_id;
- tipo/categoria;
- headline;
- verdade do evento;
- fontes e moedas;
- urgência atual;
- pico de urgência;
- alerta atual;
- pico de alerta;
- primeiro avistamento;
- último avistamento;
- quantidade de observações.

O journal não reclassifica a notícia. Ele registra o resultado do Live Event
Intelligence oficial.

## Fila interna de entrega

Alertas WATCH / HIGH_REVIEW / URGENT_REVIEW podem gerar candidato interno com:

- event_id;
- headline;
- truth_state;
- urgência;
- necessidade de revisão humana.

A fila é somente preparação para futura integração.

Regras fixas:

- external_channel_connected = false;
- external_delivery_allowed = false;
- automatic_notification_sent = false;
- market_action_authorized = false;
- real_orders_enabled = false.

Nenhuma mensagem é enviada por WhatsApp, Telegram, e-mail ou push nesta camada.

## Checkpoint Mestre

Novo namespace:

`live_event_journal`

Contém:

- `events`;
- `heartbeats`;
- `digest`.

A Central AION oferece sincronização explícita do histórico runtime para a
memória de trabalho. O usuário ainda precisa usar o fluxo normal de salvar o
Checkpoint Mestre.

## Interface

A Central passa a mostrar:

- estado do background watch;
- número de heartbeats;
- horas de cobertura;
- maior lacuna;
- eventos deduplicados no runtime;
- candidatos na fila interna;
- histórico já guardado no Checkpoint.

A aba Trading mostra o mesmo radar em modo somente leitura, sem botão de
persistência.

## Travas

- segundo motor de classificação: NÃO;
- chamada extra a provedor: NÃO;
- notificação externa: NÃO;
- fallback pago: NÃO;
- alteração de score/peso: NÃO;
- autorização de trade: NÃO;
- ordem real: BLOQUEADA.
