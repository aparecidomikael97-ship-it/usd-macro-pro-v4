# AtlasQuant Trader — ciclo documental CPI FLASH → FINAL → REVISION (LAB)

Referência local: 09/11/2026 (America/Cuiaba). Pesquisa offline; nenhuma conexão de dados, previsão ou ordem liberada.

## Por que importa

O CPI mensal pode ter uma **estimativa preliminar** (`FLASH`) próxima ao mês de referência e uma divulgação **definitiva** (`FINAL`) posterior. Um valor **revisado** (`REVISION`) constitui uma terceira categoria e não pode ser retroativamente usado para um viés calculado antes de sua publicação. O Eurostat descreve publicações preliminares e finais em https://ec.europa.eu/eurostat/web/hicp/information-data. A mera classificação manual do evento não prova que o banco central ou órgão estatístico o publicou naquele momento.

## Contrato implementado

Sem alterar as chaves das entradas legadas, `atlasquant_trader_g8_macro_asof_lab.py` e a matriz `atlasquant_trader_g8_macro_matrix_pit_lab.py` agora reconhecem o campo **opcional** `publication_stage` nas linhas:

| Indicador | `publication_stage` | Regra documental |
| --- | --- | --- |
| `CPI_YOY` | `FLASH` | Pode ter mês de referência igual ao da publicação, mas **não** completa a exigência de CPI final: `FLASH_ONLY_UNATTESTED`. |
| `CPI_YOY` | `FINAL` | Só pode ser o mês anterior (ou mais antigo) ao da publicação alegada. |
| `CPI_YOY` | `REVISION` | Bloqueia com `REVISION_VINTAGE_UNATTESTED` até haver prova do histórico original e da revisão. |
| `POLICY_RATE` | `POLICY_DECISION` | A decisão pode ser datada dentro do mês de referência. |
| Legados sem o campo | `UNSPECIFIED` | Compatibilidade sintética antiga mantida, sem transformar o rótulo ausente em prova de publicação final. |

- A cadeia `FLASH → FINAL` para uma mesma moeda/indicador/período passa como **metadata claim**, com seleção da `FINAL`, **somente** se a divulgação e a captura alegadas de `FLASH` antecederem as de `FINAL`.
- Dois registros de mesma etapa e período, etapas invertidas, mistura de etapa legada e etapa explícita no mesmo mês, fonte errada ou campo malformado bloqueiam a validação.
- Uma única moeda com `FLASH` sem `FINAL` deixa exatamente seus sete cruzamentos Forex com cobertura macro incompleta; uma revisão sem atestação rejeita esses cruzamentos. Os 28 pares usam o mesmo conjunto por moeda, sem valores numéricos no resultado.
- `publication_stage` e timestamps seguem sendo **declarações do chamador**. Hash, link ou rótulo não autenticam o órgão emissor, primeira publicação, série econômica ou versão vista na data histórica.

## Validação

`python -m unittest -q test_atlasquant_trader_g8_macro_asof_lab test_atlasquant_trader_g8_macro_matrix_pit_lab test_atlasquant_trader_g8_event_relevance_lab test_atlasquant_trader_g8_issuer_custody_chain_lab`

**98/98 testes locais PASS**, exclusivamente sintéticos nesta rodada. Incluem prévia isolada, sequência prévia→final, ordem invertida ou empate de captura, revisão, etapa inválida, propagação aos sete cruzamentos e preservação dos vetos de operação. Nada foi reexecutado no PC AM12 nem no GitHub Actions nesta rodada.

## Próximo P0

Ligar cada evento à versão original oficial, à hora de primeira divulgação e à captura histórica imutável com prova verificável; identificar a série (incluindo indicador, unidade, período, país, flash/final/revisão) e só então estudar surpresa econômica e calibração por ativo/horizonte.

Todos os resultados permanecem `operational_bias=AGUARDAR`, sem `D1/W1/MN1` negociável, acurácia comprovada, execução MT5, publicação, merge, scheduler, worker ou custo novo.
