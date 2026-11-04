# AtlasQuant Trader — cobertura documental das duas moedas de cada par (LAB)

Checkpoint 04/11/2026 · PR #1811 · sem dependência da PR #1803.

## Avanço
A ponte BCE × dossiê macro agora apresenta, em cada par dos 28 e em
D1/W1/MN1, **quantos eventos documentais foram fornecidos** para a moeda
base e para a moeda cotada. A saída distingue:
- nenhuma alegação documental (NÃO quer dizer que não houve divulgação),
- alegações somente de uma das duas moedas,
- alegações para ambas, ainda **não autenticadas**.

O mesmo evento não é contado duas vezes quando repetido em múltiplos pares.
Compara também eventos citados em outros pares com a mesma moeda e mesmo
horizonte, mostrando a contagem de registros ausentes **dentro do próprio
dossiê**, com até oito exemplos de event_id. Essa diferença é alerta de
propagação documental, não prova de cobertura completa do calendário real.

## Proteções e limites
Toda saída mantém `basis_for_operational_bias=false`,
`counterevidence_verified=false`,
`macro_fundamentals_authenticated=false`,
`full_economic_calendar_coverage_verified=false` e
`operational_bias=AGUARDAR`.

Nenhuma dessas contagens mede força fundamental, relação causal ou
confiabilidade de fonte, nem representa cotações Forex independentes.
A ausência de eventos fornecidos não equivale a resultados iguais ao
consenso, mercado neutro ou inexistência de notícias. As três janelas
históricas são sobrepostas e não representam três confirmações.

Seis novos testes na suíte já executada por Quality verificam cenários
sem dados, com uma moeda, ambas as moedas, divergência de cobertura entre
pares, repetição sem dupla contagem e histórico mensal insuficiente.
Resultado remoto precisa ser conferido no novo commit.

Não executar Worker, Render, automações, serviço pago, publicação ou
ordens reais. O gate de segurança mantém HARD NO-GO.
