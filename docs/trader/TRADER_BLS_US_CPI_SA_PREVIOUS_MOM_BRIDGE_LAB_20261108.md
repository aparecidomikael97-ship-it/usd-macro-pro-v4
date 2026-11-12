# AtlasQuant Trader — ponte CPI mensal ajustado do BLS (LAB)

**Data:** 08/11/2026. **Status:** interpretador de bytes de pesquisa, offline,
sem download executado nesta etapa, fontes originais não autenticadas.

## Por que separar as séries?

Para comparar uma projeção de **CPI mensal com ajuste sazonal** com um valor
anterior, a série precisa ter a mesma definição. A API BLS expõe diferentes
índices:

| Série BLS | Significado | Uso correto neste projeto |
| --- | --- | --- |
| `CUSR0000SA0` | CPI-U, todos os itens, média das cidades EUA, **ajustado sazonalmente**, valor do índice | Calcular **contexto documental** da variação mensal ajustada a partir de meses consecutivos |
| `CUUR0000SA0` | CPI-U, todos os itens, média das cidades EUA, **sem ajuste sazonal**, valor do índice | Série separada; pode apoiar estudo YoY, sujeito a índices existentes, sem servir de MoM ajustado |

O índice de nível (base 1982–84 = 100) **não é percentual de inflação**.
Uma variação percentual derivada do índice atual não é necessariamente
idêntica ao primeiro resultado publicado pelo órgão, devido a revisões e
arredondamentos.

Referências oficiais:

- [BLS — como identificar as séries CPI](https://www.bls.gov/cpi/factsheets/cpi-series-ids.htm)
- [BLS — cálculo de variações percentuais](https://www.bls.gov/cpi/factsheets/calculating-percent-changes.htm)
- [BLS — dados ajustados e revisões](https://www.bls.gov/cpi/seasonal-adjustment/using-seasonally-adjusted-data.htm)
- [BLS — API pública, consulta simples](https://www.bls.gov/developers/api_unix.htm)
- [BLS — características da API e atraso](https://www.bls.gov/bls/api_features.htm)

## Código e regras

- `atlasquant_trader_bls_cpi_sa_previous_bridge_lab.py`
- `test_atlasquant_trader_bls_cpi_sa_previous_bridge_lab.py`

`parse_current_bls_cpi_sa_index_lab` valida um JSON **fornecido pelo chamador**
e exige uma única série `CUSR0000SA0`, meses válidos em ordem decrescente,
índices positivos, sem duplicatas ou meses futuros. `M13` (média anual) não
é mês de inflação. Valor faltante `"-"` não é zero nem interpolado.

`bridge_previous_cpi_sa_mom_before_event_lab` exige:

1. Dados alegadamente observados **antes** da previsão.
2. Previsão capturada **antes** do horário de divulgação informado.
3. A última observação na resposta deve corresponder ao **mês anterior ao
   evento**, não ao mês do evento.
4. Os **dois índices consecutivos** para calcular a variação mensal anterior.

Exemplo exclusivamente de estrutura, com valores fictícios nos testes:
índice de setembro 336,298 e agosto 334,131 → variação aritmética aproximada
de 0,6% após arredondamento a uma casa decimal. Esse valor **não é uma
captura real de fonte nesta execução**, nem previsão de outubro, nem
certificação do valor divulgado pelo BLS.

## Proibições e bloqueios preservados

- A API pública não fornece, nesta consulta, prova de **qual era o primeiro
  valor publicado** nem um histórico de revisões com datas de primeira
  disponibilização. É indispensável guardar a resposta bruta em cada captura
  e comparar com comunicados oficiais.
- A documentação BLS alerta que índices sazonalmente ajustados podem ser
  revistos por até cinco anos. O histórico atual não comprova um backtest
  *point-in-time* sem uma cadeia de versões preservada.
- O BLS documenta atraso possível de cerca de **um dia** entre publicação e
  disponibilidade na API. Portanto, **não prometer atualização imediata a cada
  notícia** a partir dessa API; na divulgação, a fonte de primeiro resultado
  deve ser tratada separadamente.
- Nenhuma integração HTTP foi ligada; a função aceita bytes passados por
  chamador. Não foi criada previsão real para o CPI de outubro/2026.
- Sem consenso autenticado, resultado oficial pós-evento autenticado,
  probabilidades calibradas, sinal de alta/baixa ou assertividade.

Todos os estados continuam `AGUARDAR`, sem ordens, publicação, alertas,
worker, scheduler, conexão MT5 ou custo novo. O próximo passo é capturar uma
resposta real com prova de origem e timestamp, preservando o original, e
**não** reutilizar o valor atual como se já estivesse disponível no passado.
