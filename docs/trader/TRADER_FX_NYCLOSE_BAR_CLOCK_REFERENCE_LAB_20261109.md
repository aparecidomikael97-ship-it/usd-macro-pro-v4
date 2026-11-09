# AtlasQuant Trader — auditoria do carimbo horário D1/W1 contra a referência New York close

**Data:** 09/11/2026. **Estado:** investigação técnica somente leitura, sem acesso ao AM12 nesta rodada. Não foi consultada a conta, não houve captura de candles, emissão de sinais, ordens, merge ou deploy. A PR #1851 continua rascunho. Custos adicionais: R$ 0.

## Divergência documental que justifica esta etapa

Segundo a página pública de horas de mercado da **Pepperstone**, o servidor usa GMT+2 durante o horário padrão dos EUA e GMT+3 no horário de verão dos EUA, para alinhar os candles diários ao dia de negociação de Nova York. Isso *não comprova* que a conta/servidor MT5 usado no snapshot do AM12 é Pepperstone nem que os timestamps dos arquivos correspondam ao começo da sessão.

Fonte pública: https://pepperstone.com/en-gb/about-us/trading-hours

A referência da API Python do **MetaTrader 5** diz que barras são retornadas com horários UTC: https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py . No checkpoint anterior do projeto, os arquivos locais consultados incluíam os exemplos abaixo, entre outros:

| Timestamp de abertura reportado no snapshot | Carimbo em Nova York | Comparação com referência NY 17h |
| --- | --- | --- |
| D1 `2026-11-05T00:00:00Z` | Quarta-feira 04/11 19:00 EST | **Divergente:** 2 horas depois das 17h NY |
| W1 `2026-10-25T00:00:00Z` | Sábado 24/10 20:00 EDT | **Divergente:** não é domingo às 17h NY |
| Referência inverno `2026-11-08T22:00:00Z` | Domingo 08/11 17:00 EST | Compatível, apenas como padrão |
| Referência verão `2026-03-08T21:00:00Z` | Domingo 08/03 17:00 EDT | Compatível, apenas como padrão |

**Interpretação:** esses exemplos indicam uma **incompatibilidade a investigar**, NÃO a prova de que as velas estão erradas. É necessário conhecer o **servidor real**, a convenção de rotulagem D1/W1 do terminal, a origem dos timestamps Unix e as sessões efetivas. Não ajustar timestamps por -2 h ou qualquer outro deslocamento sem evidência; não reclassificar uma vela como correta só porque o padrão NY-close coincide.

## Código e limites

`atlasquant_trader_fx_nyclose_clock_audit_lab.py` fornece `FxClockSample` e `audit_fx_nyclose_clock_lab`. Aceita amostras UTC D1/W1 fornecidas pelo chamador, com hash SHA-256 **alegado** do CSV e instante de captura **alegado**; usa o banco IANA `America/New_York` para aplicar as mudanças oficiais de horário de verão. Confere duplicação, universo dos 28 pares, fuso, sequência temporal, amostras dos dois períodos e o relógio de Nova York.

Saídas: `LAB_SESSION_CLOCK_REFERENCE_DISCREPANCY_REVIEW`, `LAB_NYCLOSE_REFERENCE_MATCH_UNATTESTED` ou `LAB_BAR_CLOCK_BLOCKED`. **Todas** mantêm `operational_bias=AGUARDAR`, `trade_authorized=False`, `publishable=False`, `validated_directional_accuracy=None`, `broker_calendar_verified=False` e `pepperstone_server_association_verified=False`. Uma amostra coincidente também não autentica broker nem atesta mercado ponto-no-tempo.

O módulo **não** recebe preços, não chama o MetaTrader, não grava arquivos, não acessa credenciais e não ajusta datas. É um diagnóstico isolado para evitar que a primeira rodada prospectiva use uma convenção de horário ainda não verificada. Não substituir as regras de auditoria de lacunas por este diagnóstico.

## Verificações realizadas

```bash
PYTHONPATH=.:_testdeps python -m unittest -q \
  test_atlasquant_trader_fx_nyclose_clock_audit_lab
```

**22/22 testes locais sintéticos aprovados**, incluindo referência do inverno/verão, troca de horário de verão, timestamps documentais D1/W1 do checkpoint, sábado vs domingo, relógio sem fuso, amostra futura, hash inválido, duplicatas, cobertura parcial e proibição de sinais. O diretório `_testdeps` contém uma cópia mínima do universo oficial **somente para executar os testes localmente**; **não** integra a PR. Esses testes não autenticam o servidor nem medem acerto.

## Próxima prova concreta — AM12 online

1. Em modo **somente leitura**, conferir `terminal_info()` e a identificação do servidor sem registrar login, credenciais ou dados de conta; conferir `symbol_info()` e os horários de abertura D1/W1 de **uma pequena amostra** dos 28 pares, sem repetir a coleta inteira.
2. Comparar o mesmo símbolo em `copy_rates_from_pos` e no arquivo compactado já arquivado, com convenção do servidor observada; registrar ambas as fontes e horário de consulta, sem alterar os CSVs.
3. Se o feed for de outro servidor, conservar a informação verdadeira e definir a regra **daquele feed**, não impor por conveniência o calendário público da Pepperstone.
4. Só depois fixar as janelas dos 56 alvos D1/W1, registrar plano e decisões com hashes pré-evento e avaliar os resultados prospectivos.

**Não calcular assertividade com dados que ainda não tenham fonte, horário e período comparáveis.**
