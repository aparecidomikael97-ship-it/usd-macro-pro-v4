# AtlasQuant Trader — BLS CPI-U: trava contra futuro no histórico (LAB)

## Motivação

O parser de CPI-U dos EUA já calcula uma taxa aproximada de 12 meses
usando duas observações mensais da série `CUUR0000SA0` e não gera viés.
Mas uma resposta de API consultada **hoje** não pode ser retroativamente
tratada como informação disponível **ontem**, mesmo que o JSON contenha
observações antigas.

## Proteção adicionada

`atlasquant_trader_us_bls_cpi_snapshot_asof_lab.py` recebe:

- bytes da resposta BLS, fornecidos pelo chamador;
- recibo de captura explicitamente **não autenticado** com URL, método,
  status, tipo, comprimento, SHA-256 e início/fim alegados da coleta;
- mês-alvo; instante de decisão e instante de avaliação, ambos com timezone.

Regras:

1. Confere comprimento e SHA-256 dos bytes sem confiar em um hash isolado
   como prova de origem ou de primeira divulgação.
2. Exige URL da série `CUUR0000SA0`, GET/200/JSON sem redirecionamento
   alegado, recibo com campos exatos e janela de coleta de até 120 segundos.
3. Se o término **alegado** da captura for posterior ao instante da decisão,
   retorna `LAB_BLS_CAPTURE_NOT_VISIBLE_AT_DECISION` e **não expõe o valor
   derivado**.
4. Mesmo com captura anterior ao corte, retorna apenas
   `LAB_BLS_CAPTURE_SELF_CONSISTENT_AND_NONFUTURE_UNATTESTED`;
   `historical_point_in_time_eligible=false`,
   `publisher_first_release_authenticated=false`,
   `eligible_to_feed_macro_bias=false` e `AGUARDAR`.

Esses tempos são fornecidos por quem capturou e **não têm relógio ou
origem atestados independentemente**. Portanto, a trava evita um tipo de
lookahead óbvio, mas não certifica uma base histórica P-I-T.

## Verificação

`python -m unittest discover -q -p 'test_atlasquant*.py'`:
**183/183 testes locais aprovados**. Dez testes novos simulam captura antes
e depois da decisão, limite exatamente no término, hash alterado, janela
inválida, host e metadados indevidos, clocks sem timezone, e mês homólogo
ausente. Não houve consultas HTTP, escrita, custo ou operação no MT5.

## Bloqueio restante

**Não foi capturada nenhuma resposta real nova do BLS.** O módulo permanece
um contrato offline sinteticamente testado. Não cadastrar USD como
documentado no inventário bilateral, não calcular probabilidade ou acurácia
e não publicar na interface.

Fonte oficial para o protocolo:
https://www.bls.gov/developers/api_signature_v2.htm
https://www.bls.gov/developers/api_faqs.htm

Próximo passo é obter uma captura oficial por uma via autorizada e preservar
os bytes de modo verificável, sem contornar HTTP 403 nem atribuir histórico
P-I-T a um snapshot atual.

Sem merge, deploy, worker, cobrança ou trade.
