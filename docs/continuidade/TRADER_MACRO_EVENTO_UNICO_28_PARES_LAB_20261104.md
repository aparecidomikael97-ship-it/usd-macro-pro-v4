# AtlasQuant Trader — um evento macro, uma versão documental (LAB)

Checkpoint 04/11/2026; branch de pesquisa ECB #1811, sem integração com PR #1803.

## Risco corrigido
Um mesmo evento (por exemplo, CPI EUA) pode aparecer em vários pares que
contêm USD e em D1/W1/MN1, que são janelas sobrepostas. Se cada cartão
exibir valor ou horário diferente para o mesmo `event_id`, o usuário
poderia receber explicações contraditórias sobre a força da moeda.

## Regra de consistência cruzada
- O adaptador em LAB revalida cada observação sintética, horário de consenso
  anterior à divulgação, diferencial actual–consenso, rótulo acima/abaixo.
- Um `event_id` mantém uma impressão digital **apenas lógica** de moeda,
  horário UTC normalizado, data de consenso, indicador, unidade, valor
  anterior (quando presente), consenso, realizado, surpresa e classe.
- Se um evento se repetir com qualquer um desses atributos diferente em
  outro par ou horizonte, o dossiê todo é `LAB_BLOCKED`.
- Repetições coerentes permanecem permitidas, mas **não contam como
  confirmações independentes**.
- Datas distintas de fuso com o mesmo instante real são equivalentes.
- Saída deixa explícitos `distinct_unattested_macro_events` e
  `cross_pair_macro_event_consistency_checked`.

Importante: essa checagem NÃO autentica o conteúdo original nem garante
que todos os pares receberam todos os eventos. Também não demonstra
que CPI, juros, emprego ou notícia causou determinada cotação.

## Testes
Cinco casos novos: repetição coerente, valores conflitantes, divergência
de metadados/horários, fusos equivalentes e eventos distintos. Quality
do GitHub deve validar esse novo SHA antes de considerar a etapa aprovada.

Regras preservadas: oito moedas G8, 28 pares, D1/W1/MN1, viés sempre
`AGUARDAR` sem evidências confiáveis, sem preço independente, sem
notícias/calendário autenticados, sem cron, Render, AION, Worker, ordem,
deploy, merge ou custos novos.
