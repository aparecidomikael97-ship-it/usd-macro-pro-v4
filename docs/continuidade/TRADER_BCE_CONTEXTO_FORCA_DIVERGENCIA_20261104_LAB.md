# AtlasQuant Trader — contexto de força por horizonte, ainda sem causa comprovada

Checkpoint LAB de 04/11/2026; a prioridade continua sendo **viés de 28 pares,
força/fragilidade das oito moedas, macro, micro, geopolítica, notícias e calendário**.
FVG/OB e sinais de M15 não são objeto desta etapa.

## Acrescentado na PR #1811 (BCE isolado)

`atlasquant_trader_ecb_horizon_context_lab.py` transforma a matriz documental
de referências D1/W1/MN1 em 28 explicações por par e oito fichas por moeda:

- Expõe **quem superou quem no passado** em cada horizonte, com valores e datas.
- Distingue concordância retrospectiva, **divergência entre horizontes**,
  mudanças estáveis e histórico insuficiente. Mesmo quando há concordância,
  as janelas são **sobrepostas e não constituem três provas independentes**.
- Lista as moedas mais fortes e mais fracas no período de referência, **sem
  inventar um primeiro/último colocado único quando há empate**.
- Lista, para cada moeda, os assuntos **a investigar com fonte**: política
  monetária/expectativas, inflação, emprego, atividade/micro, geopolítica,
  notícias verificadas, calendário/revisões e contraprovas.
- Mostra `NAO_DEMONSTRADO_PELO_BCE` em "por que está forte/fraca" e
  `AGUARDAR` nos três vieses operacionais. Não atribui falsamente força
  cambial à notícia apenas por ela existir.

**Exemplo sintético de teste:** uma sequência artificial de quatro datas faz
EUR/USD cair em D1, subir em W1 e cair no mês móvel MN1. A saída aponta
`DIVERGENCIA_HISTORICA_ENTRE_HORIZONTES`, sem decidir pela compra/venda.
Os dados do exemplo são **inventados exclusivamente para teste**.

## Ainda não temos

- Preços e spreads Forex independentes verificáveis para as 28 combinações.
- Causas macroeconômicas e geopolíticas demonstradas por documentos originais
  autenticados e associados ao momento conhecido pelo mercado.
- Calendário/notícias coletados automaticamente em três horários reais com
  provas de execução, revisão e atualização.
- Acurácia estatística fora da amostra, limites e autorização de trading.

As sete taxas diretas do euro do BCE geram 21 cruzamentos derivados. São
referências diárias informativas, não cotações executáveis. A janela MN1 é
**30 dias corridos móveis**, não o mês de calendário fechado.

## Qualidade local

Comando executado no conjunto do BCE no workspace:

```bash
python -m unittest -q \
  test_atlasquant_trader_ecb_horizon_context_lab.py \
  test_atlasquant_trader_ecb_three_horizon_matrix_lab.py
```

Resultado: **21 testes verdes (10 novos + 11 anteriores)** em 04/11/2026.
O CI remoto não está implícito nesse número: deve ser confirmado no SHA da PR.

Não houve Render, Worker, cron, cobrança, publicação, merge nem operação real.
PR #1803 (macro/notícias/calendário) permanece separada. A integração entre
ela e o BCE exige revisão explícita de contratos e de origem das evidências.
