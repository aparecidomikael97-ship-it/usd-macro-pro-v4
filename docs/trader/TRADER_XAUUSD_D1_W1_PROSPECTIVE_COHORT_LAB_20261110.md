# AtlasQuant Trader — coorte prospectiva XAU/USD D1/W1 (LAB)

**Checkpoint: 10/11/2026. Nenhum prognóstico real foi emitido ou avaliado.**

## Objetivo: medir a decisão que existia ANTES da vela futura

Os módulos de coleta, auditoria e ligação de preços com contexto macro do
XAU/USD já estão preparados. O novo
`atlasquant_trader_xauusd_prospective_cohort_lab.py` acrescenta o protocolo
para registrar **duas oportunidades obrigatórias por rodada**: uma D1 e uma
W1. Cada oportunidade precisa ter uma decisão `UP`, `DOWN` ou `ABSTAIN`.
Os `ABSTAIN` não desaparecem do denominador de oportunidades.

### Etapa A — congelamento local da hipótese

- `freeze_gold_two_horizon_cohort_lab(...)` exige um identificador da rodada,
  uma versão fixa do modelo, janelas futuras de D1 e W1, horários alegados de
  planejamento/congelamento e **as duas decisões**.
- Evidência da previsão deve anteceder sua emissão e o congelamento deve
  anteceder o início de **ambas** as velas futuras. Direção requer hash de
  evidência; abstinência exige motivo documentado e não pode carregar hash
  de emissão direcional.
- Salva a representação JSON canônica e SHA-256 somente **na saída da função**;
  não grava arquivos nem envia dados. O usuário ou pipeline futuro precisará
  manter um recibo externo realmente emitido ANTES do evento. Um hash local
  pode ser refeito retrospectivamente e **não é prova temporal independente**.

### Etapa B — conferir o desfecho posteriormente

- `assess_gold_two_horizon_outcomes_lab(...)` revalida o JSON e seu SHA,
  audita uma pasta XAU/USD **posterior** e procura as velas D1 e W1
  previamente declaradas pelo horário exato de abertura.
- A vela alvo deve estar fechada segundo o horário nominal declarado antes
  do instante alegado de coleta. Dados ausentes, arquivo adulterado ou
  alvo posterior à coleta bloqueiam a **rodada inteira** — não permitem
  escolher apenas o alvo que saiu certo.
- Para cada lado direcional declarado, compara `UP`/`DOWN` com a **corpo da
  vela** (abertura para fechamento). `FLAT` não vira acerto. `ABSTAIN` é
  registrado sem entrar na contagem de previsões emitidas.
- A saída informa exclusivamente correspondências **documentais de teste**.
  Não calcula probabilidade nem divulga taxa de acerto validada.

**Limitações explícitas:** janelas D1=24h e W1=168h são nominais;
mudanças de horário de sessão/DST da Pepperstone exigem verificação
independente e podem bloquear a coorte. Os dados do MT5, relógio do terminal,
fonte macro, momento real do congelamento, custos, corretora e independência
estatística continuam não atestados.

## Testes realizados

- `test_atlasquant_trader_xauusd_prospective_cohort_lab.py`: **19/19 testes**,
  usando apenas dados sintéticos e uma API MT5 falsa. Cobrem os dois slots,
  `AGUARDAR`, acerto e erro *documentais*, ausências sem subamostragem,
  horários tardios, hash alterado, hash refeito sem testemunha externa,
  dados futuros ainda abertos, arquivo corrompido e ausência de escritas.
- Regressão `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **381/381 testes locais aprovados**.

## Estado e próximos passos

Mesmo com uma coorte sintética totalmente resolvida:

`external_prediction_timestamp_authenticated=false`,
`complete_opportunity_roster_externally_anchored=false`,
`out_of_sample_accuracy_validated=false`, `validated_accuracy=null`,
`calibrated_probability=null`, `operational_bias=AGUARDAR`,
`trade_authorized=false`, `can_feed_live_radar=false`.

**Próxima dependência real:** coletar XAU/USD na Pepperstone autorizada,
certificar calendário e horário do servidor, guardar um plano/decisão antes
dos alvos sob testemunha temporal independente e, somente depois do fechamento
das velas, alimentar esta contabilidade. Com volume suficiente de coortes,
avaliar taxa de abstinência, cobertura, precisão fora da amostra, dependência
entre observações e custo/slippage. Nenhuma promessa de 80%/90% antes disso.

Sem merge, deploy, worker, publicação, custo novo ou ordem de trade.
