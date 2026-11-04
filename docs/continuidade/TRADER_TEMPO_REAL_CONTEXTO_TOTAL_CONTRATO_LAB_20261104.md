# AtlasQuant Trader — atualizacao automatica e contexto causal G8 (LAB, 04/11/2026)

## Requisito do proprietário

Mikael exige no mínimo **três atualizações completas por dia**, detecção de
mudanças importantes do calendário/notícias com menor atraso possível e
explicação de **por que uma moeda está forte ou fraca**, no contexto de macro,
micro, geopolítica, política monetária, expectativas, notícias e força relativa
das 8 moedas/28 pares Forex. Vieses independentes D1, W1 e MN1.

**Precisão:** três atualizações diárias não são tempo real. Um relógio de
verificação a cada 5 minutos também não prova atraso máximo de 5 minutos:
publicação, origem, cache, rede, execução, persistência e interface precisam
ser medidos separadamente. A frase `TEMPO REAL` só aparece após medição e
homologação explícita dos SLAs, cobertura e direitos de fonte.

## Contratos novos, sem execução externa

1. `atlasquant_trader_monitoring_cadence_lab.py`: preserva as três janelas
   de calendário já desenhadas no Painel Mestre (**06:35, 10:45 e 17:15,
   horário de Brasília**) e mostra a conversão para Mato Grosso. Projeta
   verificação geral a cada 15 minutos e, durante janela de duas horas antes
   e depois de eventos com hora oficial, meta de 5 minutos. **São alvos de
   projeto e não jobs ativados.** Limites de acesso/permissões ainda pendentes.
2. `atlasquant_trader_official_change_detection_lab.py`: compara duas
   capturas documentais rotuladas, identifica evento adicionado, horário
   alterado, cancelamento explicitamente declarado e revisão de documento.
   Exige fonte oficial permitida, relógios ordenados, identificador estável,
   hash declarado com formato válido, sem falsos `actual` nem promoção live.
3. Para cada mudança, identifica os **sete pares** que contêm a moeda afetada,
   hora anterior/nova, link da fonte, prioridade de revisão e necessidade de
   confirmação humana/automática independente.
4. Uma notícia que desapareceu de uma consulta parcial **não** é considerada
   cancelada. Uma fonte fora do prazo sinaliza `STALE_OBSERVATION`, e uma
   captura de 5 minutos atrás **não** é prova de entrega em tempo real.

Os testes usam dados sintéticos que ilustram, entre outras situações, uma
reprogramação de evento. O algoritmo **não** acessa a internet, não dispara
notificações, não atualiza o aplicativo, não programa execução, não escreve
no servidor e não envia ordens.

## Fontes oficiais candidatas gratuitas

- [BLS RSS](https://www.bls.gov/feed/): emprego, CPI, PPI, produtividade.
- [Federal Reserve RSS](https://www.federalreserve.gov/feeds/feeds.htm):
  decisões e comunicados monetários, dados e discursos.
- [BCE RSS](https://www.ecb.europa.eu/home/html/rss.en.html):
  decisões, comunicados e estatísticas (verificar feed e direitos por canal).
- BoE, ONS, Statistics Canada, ABS, RBNZ e outros bancos centrais via páginas,
  feeds ou APIs oficiais **após** confirmar formatos, mudanças de agenda,
  termos de uso e janelas de atualização.

Feed de notícias e calendário são **fontes diferentes**. Um RSS que publica a
notícia depois do anúncio não necessariamente expõe o reagendamento antes dele.
Sem fonte de notícias com cobertura, direitos e latência comprovados, o sistema
não pode prometer notícias globais instantâneas ou contexto geopolítico total.

## Como deve explicar a força das moedas

Cada cartão USD/EUR/GBP/JPY/CHF/AUD/CAD/NZD deverá carregar evidências
com `observado_em`, `publicado_em`, `válido_para`, `fonte`, `confiabilidade`,
`atraso`, `anterior`, `consenso`, `real` e `revisão` quando essas informações
existirem. O resumo causal deve separar:

1. **Inflação e política monetária:** surpresa versus expectativa anterior,
   trajetória provável de juros, diferença de juros **esperada**, não apenas
   taxa atual.
2. **Emprego, atividade e microeconomia:** crescimento, salários, produção,
   demanda e dados em conflito (incluindo revisões).
3. **Geopolítica e notícias:** fatos com autoria/data/origem verificável,
   canais de transmissão (energia, comércio, risco), hipóteses e limites.
4. **Força relativa:** comparar moeda-base e cotada no mesmo horizonte,
   com preços observados independentes quando licenciados, sem tratar taxa
   BCE diária derivada como preço negociável M15.
5. **Contraprovas:** notícias contrárias, eventos próximos, incerteza,
   atrasos, lacunas e hipótese de reversão/invalidação.

O resultado operacional continua **`AGUARDAR`** enquanto não houver dados
originais verificados, explicação rastreável, OOS por horizonte/par e segurança
de fonte. Rankings não são probabilidade e o objetivo de 90% não está provado.

## Etapas para executar de verdade — ainda não autorizadas/atendidas

- Implementar e testar **fetchers reais** HTTP(S)/RSS/ICS/JSON por fonte com
  ETag/Last-Modified, timeouts, retry/backoff, validação do corpo, limites e
  rastreabilidade do payload original.
- Persistir observações e revisões duravelmente, com idempotência,
  comparação antes/depois e trilha de auditoria; fontes não atualizadas
  bloqueiam o rótulo live.
- Escolher um executor 24h com orçamento e revisão de direitos/licenças.
  GitHub Actions agendadas podem atrasar ou ser descartadas sob carga e
  executam schedules no branch padrão: **não comprovam latência crítica**.
  Referência: [GitHub Docs](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows).
- Medir no mínimo 7 dias a latência de cada feed, falhas, revisões não
  detectadas, períodos fora do ar e custo. Sem isso não há SLA real.
- Liberar no Radar somente após preflight independente, aprovação do
  proprietário, testes de integração e respeito ao HARD NO-GO do AION.

## Validação local

```sh
python -m unittest -q \
  test_atlasquant_trader_official_change_detection_lab.py \
  test_atlasquant_trader_monitoring_cadence_lab.py \
  test_atlasquant_trader_macro_event_exposure_lab.py \
  test_atlasquant_trader_macro_event_exposure_v2_lab.py \
  test_atlasquant_trader_bias_calendar_exposure_link_lab.py \
  test_atlasquant_trader_bias_priority_bridge_lab.py \
  test_atlasquant_trader_macro_pit_documentation_link_lab.py \
  test_atlasquant_trader_g8_country_macro_catalog_lab.py
```

**Resultado local em 04/11: 121 testes OK.** Estado: GO-LAB apenas, sem
serviço ativo, sem assinatura nova, sem Render, sem AION Worker e sem ordens.
