# AtlasQuant Trader — origem técnica e fuso dos candles D1 (LAB)

Data: 02/11/2026 | PR #1803 DRAFT | HARD NO-GO.

## Descoberta com evidências do repositório

A rotina existente **autopilot_v107.py** (sem execução nesta auditoria)
usava a função td_fetch(pair, "1day", 320) em ensure_daily_cache().
Esse caminho chama o endpoint Twelve Data /time_series com
symbol=par, interval=1day, outputsize=320, timezone=UTC, order=ASC,
e lê values[] com o validador de twelve_cache_v1108.py.
Em seguida grava o histórico em
dados/autopilot_daily_cache_v107.json.

O histórico público de commits desse arquivo mostra diversas revisões
em 17/09/2026 com a mensagem "V10.7 Autopilot: cache diário FX",
incluindo 4c79c510... (06:28 UTC). Isso apoia a LINHAGEM TÉCNICA,
mas NÃO prova que os bytes vieram de uma resposta intacta do
fornecedor, que o fornecedor permitia redistribuição ou que
cada candle histórico estava disponível na data rotulada.

Arquivos auditados:
- autopilot_v107.py: td_fetch (linhas ~359–422),
  ensure_daily_cache (~809–838), persistência (~1375–1379).
- twelve_cache_v1108.py: valid_records, pd.to_datetime(..., utc=True).
- dados/autopilot_daily_cache_v107.json: 7 pernas USD, 320 candles
  por par, 83 datas de sábado/domingo por par, sem meta.exchange_timezone.

## Falha de interpretação descoberta

A DOCUMENTAÇÃO do fornecedor informa que o parâmetro timezone
é aplicável só a intervalos intradiários e é **ignorado em 1day,
1week e 1month**. Para Forex, o artigo oficial de fusos descreve
Australia/Sydney como fuso padrão. Fontes:

- https://twelvedata.com/docs (time_series -> timezone)
- https://support.twelvedata.com/en/articles/5745849-timezones

**Isso NÃO prova que o cache específico está em Sydney.**
Ele descarta, porém, a suposição de que ter solicitado timezone=UTC
é suficiente para garantir timestamps D1 em UTC.

O validador antigo convertia datetime com utc=True. Para strings
sem fuso, essa conversão as INTERPRETA como UTC, sem fazer conversão
a partir de Australia/Sydney ou meta.exchange_timezone.

Consequências possíveis: horários ou datas de sessões deslocados,
alguns candles rotulados como sábado e, principalmente, erro de
disponibilidade temporal de informação para um backtest.

## Entregas desta revisão

1. A auditoria atlasquant_trader_fx_legacy_cache_audit_lab.py
   adicionou bloqueios permanentes:
   LEGACY_FX_D1_TIMEZONE_CONVERSION_UNATTESTED e
   LEGACY_D1_CLOSE_AVAILABILITY_UNVERIFIED.
   O histórico ainda não é adequado para viés atual ou acerto
   histórico oficial.
2. atlasquant_trader_twelve_d1_time_lab.py recebe **apenas
   amostras sintéticas** contendo meta.exchange_timezone e
   rótulos D1 locais originais. Converte IANA local -> UTC sem
   depender do timezone solicitado. Bloqueia timezone ausente,
   labels inválidos, duplicados, fora de ordem e instantes locais
   ambíguos/inexistentes no horário de verão.
3. Os rótulos convertidos NÃO são tratados como fechamento
   comprovado nem como hora de disponibilidade de preço. Não
   podem alimentar viés, Radar ou avaliador OOS.
4. Novos testes incluem Sydney no verão/inverno e mudanças de
   horário de verão; uma amostra do arquivo antigo sem
   metadados originais deve ser recusada.

## Próxima prova obrigatória antes de usar histórico

- Recuperar metadados históricos reais (exchange_timezone,
  convenções de sessão, opening/closing time) de fonte autorizada.
- Confrontar alguns candles com fonte independente e definir
  disponibilidade real antes de qualquer sinal histórico.
- Revisar direitos de uso comercial e custo antes de solicitar
  novas APIs ou históricos.
- Só após isso desenhar um protocolo de validação OOS de viés
  D1/W1/MN1; a força relativa matemática NÃO é probabilidade de acerto.

Sem chamadas pagas à Twelve Data, sem agendamento, Worker, deploy,
merge ou ordens. Nenhuma alteração aplicada ao aplicativo público.


## Gate adicional: horário de abertura não é preço conhecido

Ao receber dois labels locais sintéticos sucessivos em que
meta.exchange_timezone esteja presente, a função
assess_synthetic_d1_availability_lab exige:

- captured_at_utc e forecast_issued_at_utc com offset explícito;
  **captura <= emissão <= instante da pesquisa**;
- um label da barra SEGUINTE para estabelecer, apenas
  hipoteticamente, que o período anterior já poderia ter terminado;
- captura não anterior ao label convertido da barra seguinte;
- nunca usar a última barra da amostra como fechamento confirmado;
- a única data em que um valor pode ser alegado como recebido
  é a de captura declarada, **não** a do início histórico da barra.

Mesmo com essas condições, o resultado chama-se
LAB_CLOCK_HYPOTHESIS_NOT_ATTESTED, pois timestamps de
amostras sintéticas não comprovam hora oficial de publicação,
captura imutável ou direito sobre a cotação. As flags
can_feed_real_bias e can_feed_real_oos continuam falsas.

O teste de continuidade adiciona oito cenários adversos:
barra única, barra seguinte, captura antecipada, captura
posterior sem retroagir para o label de abertura, captura após
previsão, hora sem fuso, metadado de provedor ausente e
o cache antigo sem histórico de metadados.

Cuidado: um próximo label é uma fronteira de relógio, mas
**não é prova independente de fechamento**, disponibilidade,
correção dos preços ou viés. Não há backtest real nesta fase.
