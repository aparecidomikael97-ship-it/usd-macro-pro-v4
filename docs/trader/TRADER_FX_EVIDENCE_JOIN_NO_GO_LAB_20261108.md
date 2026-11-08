# AtlasQuant Trader — junção de evidências W1/D1, macro, eventos e preço (LAB)

**Data:** 08/11/2026. **Status:** `AGUARDAR` / **NO-GO operacional**.

O arquivo `atlasquant_trader_evidence_join_lab.py` reúne três pesquisas
existentes sem ativá-las no aplicativo:

1. **Macro bilateral:** executa `inspect_g8_macro_matrix_pit_lab` nos cortes
   históricos independentes de D1 e W1, com as mesmas oito moedas e os
   28 pares. Fonte publicada/capturada depois do corte não pode ser reutilizada
   retroativamente. Completude declarada dos metadados **não prova** a
   autenticidade do original nem a comparabilidade de CPI e juros.
2. **Preço:** executa `window_decision` para as velas D1/W1 do par com nomes
   de símbolo canônicos. Não usa barra ainda aberta; preserva qualquer salto
   do calendário como barreira. Continuidade das velas **não valida** o
   calendário da corretora, os horários históricos P-I-T ou um backtest.
3. **Seleção rara e notícias:** executa `assess_selective_bias_lab`, incluindo
   confirmação repetida, alinhamento W1/D1, restrição da mesma direção,
   blackout de notícias, invalidade do contexto macro anterior a uma
   divulgação importante e falta de valor real do evento.

O novo módulo é **uma lista de motivos para não liberar o viés**, não um
algoritmo que calcula a direção. Um resultado hipotético em que todas as
entradas sintéticas parecem concordar ainda devolve:

```text
state = LAB_CROSS_LAYER_EVIDENCE_DIAGNOSTIC_NO_GO
operational_bias = AGUARDAR
candidate_direction_for_publication = None
calibrated_direction_probability = None
validated_directional_accuracy = None
publishable = False
trade_authorized = False
```

Os bloqueios estruturais continuam explícitos: originais macro e valores
bilaterais sem atestado independente, preços e calendário da corretora não
atestados, cobertura dos eventos/valores reais não certificada, resultados
futuros e calibração não auditados. Flags e hashes do chamador não equivalem
a provas externas. A junção não executa HTTP, MT5, ordens, worker, deploy,
agendamento, publicação ou cobrança.

## Escopo separado para índices

`WIN`, `WDO`, `US500`, `NAS100`, `US30` são recusados nesta junção
específica. Esses ativos terão seu próprio modelo macro e definição
instrumental; não é correto reaproveitar artificialmente o modelo bilateral
de duas moedas para prever índice. O filtro seletivo anterior continua
preparado para aceitar identificadores de índices em **pesquisa isolada**,
mas não existe liberação de viés para eles.

## O que falta para avançar de verdade

- Capturar e atestar fontes macro originais da **base e da cotada**,
  comparar unidades/periodicidades e registrar primeira disponibilidade.
- Tratar cada notícia com identidade, unidade, **consenso prévio**, valor
  anterior congelado antes do anúncio e **resultado realizado depois**.
  A pesquisa documental do CPI americano permanece separada; uma previsão
  de surpresa macro não é previsão direta do EUR/USD ou WIN.
- Verificar os fechamentos das barras com o calendário real do broker,
  os gaps históricos (inclusive GBPNZD) e o símbolo/contrato exato.
- Medir resultados prospectivos por par, horizonte e direção, em janelas
  históricas distintas, sem calibrar usando os próprios dados de avaliação.
- Só posteriormente considerar integração ao Radar/Painel Mestre, com
  autorização explícita para mudanças operacionais.

## Testes

`test_atlasquant_trader_evidence_join_lab.py`: **14/14 casos sintéticos**
aprovados. Incluem a cobertura de 28 pares, futuro indevido, ausência de
receita macro de uma moeda, gap no preço, barra não fechada, notícia sem valor
real, bloqueio de índices e não divulgação de uma direção.

Execução selecionada com mais nove módulos relacionados:
**160 testes coletados, 159 aprovados e 1 pulado**, sem falhas. O teste
pulado depende do arquivo real de velas do AM12, que **não estava disponível
neste ambiente**. Isso não equivale a passar a suíte completa ou atestar o
histórico real do broker. A integração permanece experimental, na PR draft,
sem merge nem alteração ao aplicativo publicado.
