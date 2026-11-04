# AtlasQuant Trader — três revisões/dia e prontidão do contexto G8 (LAB)

**Decisão de Mikael em 04/11/2026:** a fase atual usará apenas **três
atualizações completas por dia**, sem API, assinatura, Render ou custo novo.
Um eventual upgrade para uma atualização **a cada uma hora** será avaliado
no futuro e requer aprovação explícita. As propostas anteriores de
rechecagens extras a cada 5/15 minutos ficam **suspensas**.

## Horários planejados (mantidos do Painel Mestre)

| Revisão | Horário de Brasília | Mato Grosso (2026) |
|---|---|---|
| Antes do pregão | 06:35 | 05:35 |
| Meio do dia | 10:45 | 09:45 |
| Fechamento | 17:15 | 16:15 |

Os horários são propostas de execução já existentes e **não têm job ativado**.
O período entre as revisões pode conter notícias e revisões não detectadas;
não rotular o dado como atual/intradiário sem comprovante. O sistema deve
mostrar a hora efetiva da última captura e sinalizar pendência/atraso.

## Contratos implementados neste checkpoint

1. `atlasquant_trader_monitoring_cadence_lab.py` passa à V2, com modo
   `THREE_DAILY_REVIEWS_ONLY`, sem alvo de polling extra. A opção de 60 minutos
   existe só como referência futura e mantém aprovação/custo pendentes.
2. `atlasquant_trader_g8_context_completeness_3x_lab.py` recebe **capturas
   sintéticas** de até três turnos diários, com lista de fontes documentais
   por moeda. Exige 8 moedas × 9 dimensões de contexto (72 verificações por
   captura), identifica lacunas e a última consulta documental acima de 48h.
3. Cria explicações de **insuficiência de dados por par** para os 28 Forex e
   três horizontes. Nenhuma dimensão isolada é convertida em ALTA/BAIXA;
   mantém todos `D1/W1/MN1 = AGUARDAR` até dados auditados e validação OOS.
4. Mesmo se as três capturas documentais forem fornecidas e todos os links
   aparecerem, `three_daily_updates_verified=false`, `sources_attested=false`,
   `real_bias_verified=false`: **declaração de captura não é prova de execução
   automática, disponibilidade de valores, licença ou autoria**.
5. Recusa horários futuros/fora da data, slots duplicados ou fora de ordem,
   falsificação de confirmação real, URL oficial adulterada, ausência de
   alguma dimensão/moeda ou status inventado.

## Nove dimensões mínimas do contexto

| Grupo | O que será necessário demonstrar para cada moeda |
|---|---|
| Inflação | Divulgação, consenso anterior, revisão, núcleo e leitura dos juros |
| Emprego | Desemprego, vagas, salários, revisões e reação da política monetária |
| Atividade | PIB, PMI/ISM, consumo, produção e estágio do ciclo econômico |
| Juros esperados | Banco central, expectativa futura, diferencial e surpresa |
| Microeconomia | Produção, setores, comércio, empresas e transmissão ao câmbio |
| Geopolítica | Fato com fonte/dia, commodities, risco, comércio e hipóteses contrárias |
| Notícias | Publicação/observação da fonte, relevância e atualizações posteriores |
| Calendário | Evento, hora/fuso, alteração, risco de divulgação e expectativa |
| Força relativa FX | Dados de preço independentes por moeda/par/horizonte, sem usar cruzamento BCE diário como candle M15 |

Uma lista completa de documentos não representa, por si, força verdadeira;
precisamos dos valores, vintages, contraprovas, resposta do mercado e testes
fora da amostra. **Ranking não é probabilidade.** A meta de 90% não está
homologada e não poderá ser exibida como acerto real.

## Próximo caminho

- Coletores oficiais não pagos, dentro dos termos dos fornecedores, com
  ETag/Last-Modified, hora original, hash, deduplicação e histórico de revisões.
- Três execuções reais comprovadas por dia com relógio, logs, retries
  controlados, armazenamento durável e orçamento global aferido.
- Integração ao dossiê causal (macro, micro, geopolítica, notícias, calendário
  e força relativa) e backtest OOS por D1/W1/MN1, sem publicar no Radar
  enquanto não houver qualidade e autorização suficientes.
- Só futuramente discutir serviço 24h/atualização horária, custo, SLA e
  licença comercial — **não contratar automaticamente**.

## Testes LAB

```sh
python -m unittest -q \
  test_atlasquant_trader_g8_context_completeness_3x_lab.py \
  test_atlasquant_trader_monitoring_cadence_lab.py \
  test_atlasquant_trader_official_change_detection_lab.py \
  test_atlasquant_trader_macro_event_exposure_lab.py \
  test_atlasquant_trader_macro_event_exposure_v2_lab.py \
  test_atlasquant_trader_bias_calendar_exposure_link_lab.py \
  test_atlasquant_trader_bias_priority_bridge_lab.py \
  test_atlasquant_trader_macro_pit_documentation_link_lab.py \
  test_atlasquant_trader_g8_country_macro_catalog_lab.py
```

**131 testes locais aprovados em 04/11/2026.** PR #1803 deve seguir DRAFT,
sem deploy/Render, sem Worker AION, sem ordens e sem custo adicional. CI
remota e fontes reais ainda não homologadas.
