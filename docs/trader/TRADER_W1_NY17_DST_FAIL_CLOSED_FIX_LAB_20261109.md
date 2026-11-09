# AtlasQuant Trader — correção de janela W1 na mudança do horário de verão de NY (LAB)

**09/11/2026, etapa somente em laboratório.** Não foi feita leitura no AM12 (offline), nenhuma compra/venda, alteração do MT5, deploy, merge, assinatura, automação ou publicação de viés. Os 28 pares seguem no estado operacional **AGUARDAR**. Esta etapa não mede a assertividade real.

## Erro de método que a revisão encontrou

Três módulos anteriores tratavam o fechamento semanal W1 como `abertura_utc + 604800 segundos` (7 dias): o planejamento do manifesto prospectivo, a leitura de resultados MT5 e o benchmark pareado. Para semanas abertas no **domingo às 17h em America/New_York**, a troca do horário de verão dos EUA desloca a hora UTC em uma hora. Assim, o intervalo entre dois domingos às 17h NY pode ter **167 horas na entrada do horário de verão** ou **169 horas na saída**. É incorreto conferir resultados W1 nesses períodos usando um fechamento fixo de 168h, sem comprovação do servidor da corretora.

Exemplos apenas de relógio, **não candles reais**:

| Situação | Abertura de referência em UTC | Fechamento NY17 posterior | Duração |
|---|---|---|---|
| Março 2026, início DST | 01/03 22:00 UTC | 08/03 21:00 UTC | 167 h |
| Outubro/novembro 2026, fim DST | 25/10 21:00 UTC | 01/11 22:00 UTC | 169 h |

## O que foi corrigido

Foi criado `atlasquant_trader_w1_ny17_dst_guard_lab.py`, um detector **condicional** que identifica um W1 aberto no domingo às 17h NY e que atravessa a mudança de offset no intervalo nominal. Ele não corrige datas, não faz consultas e **não prova que o servidor Pepperstone utiliza a referência NY17**. Caso falte a base IANA de fusos horários, responde de forma inconclusiva e o código consumidor bloqueia.

A integração impede uso silencioso da duração fixa em três etapas:

1. `atlasquant_trader_fx_trial_census_lab.py`: impede congelar 56 oportunidades quando o W1 pretendido cruza DST sob a referência NY17, com `W1_NY17_DST_CLOSE_REQUIRES_BROKER_VERIFICATION`.
2. `atlasquant_trader_mt5_closedbar_outcome_lab.py`: rejeita obter rótulos de resultado da vela semanal nesse caso, antes de abrir arquivos do MT5.
3. `atlasquant_trader_regime_increment_benchmark_lab.py`: rejeita a comparação pareada se algum W1 tiver fechamento semanal nominal de 168h que atravessa DST segundo NY17. A ponte `atlasquant_trader_mt5_paired_outcome_bridge_lab.py` herda o bloqueio: uma única oportunidade não resolvida interrompe **todo** o cálculo.

Os registros cuja abertura não corresponde à referência NY17 não são deslocados nem proclamados corretos: seguem na fila separada de **auditoria de horários do servidor**, já incluída no pré-voo. As semanas ordinárias continuam sendo tratadas como antes, **sem que isso represente certificação do calendário**.

## Testes executados

Suíte combinada local: **149/149 testes sintéticos PASS**, executados com os arquivos exatos dos módulos em estudo e uma dependência de teste isolada que reproduz a lista canônica de 28 pares. Inclui 9 casos de regressão novos (5 para o detector, 3 verificações diretas nos consumidores e 1 na ponte). O código de dependência simulado não será enviado ao GitHub. Reproduzir os testes no repositório e CI ainda será necessário.

```bash
PYTHONPATH=.:_testdeps python -m unittest -q \
  test_atlasquant_trader_w1_ny17_dst_guard_lab \
  test_atlasquant_trader_fx_trial_census_lab \
  test_atlasquant_trader_mt5_closedbar_outcome_lab \
  test_atlasquant_trader_regime_increment_benchmark_lab \
  test_atlasquant_trader_mt5_paired_outcome_bridge_lab \
  test_atlasquant_trader_fx_census_github_anchor_lab \
  test_atlasquant_mt5_d1w1_minimal_clock_probe_lab
```

## Pendências reais

- AM12 online para comparar em modo somente leitura os rótulos da API MT5 com o histórico já arquivado e com a origem efetiva do feed, sem recolher as 84 séries novamente.
- Uma política documentada do calendário **do servidor utilizado**, incluindo DST, feriados, domingo, duração de vela e horário de fechamento semanal; a referência pública NY17 não substitui essa validação.
- Quando houver período real validado, revisar os contratos W1 para aceitar a duração de sessão correta e **testar** a mudança em conjunto, sem reescrever históricos. Até lá, falhar fechado.
- Dados macro bilaterais e previsões pré-registradas com hora externa antes do movimento; nada pode ser considerado precisão observada sem esses controles.

**Estado operacional invariável:** `AGUARDAR`, sem probabilidade calibrada, sem acurácia demonstrada, sem negociação e sem custos adicionais.
