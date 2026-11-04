# AtlasQuant Trader — Vintages macro por instante de disponibilidade (LAB)

Data: 02/11/2026 · PR #1803 DRAFT · HARD NO-GO

## Erro histórico que precisamos impedir

Uma leitura econômica pode ser publicada inicialmente e depois
revisada. O dado final baixado hoje NÃO é necessariamente aquele
que o mercado conhecia quando fizemos um viés D1 no passado.

Exemplo INTEIRAMENTE SINTÉTICO: CPI esperado 3,0%,
publicado inicialmente 3,1%, revisado dias depois para 2,9%.
Para uma previsão emitida depois da primeira publicação
mas ANTES da revisão:
- o resultado inicialmente conhecido é 3,1%;
- a surpresa da divulgação original é 3,1 - 3,0 = +0,1 ponto;
- **2,9% não poderia ser usado na previsão**;
- depois da revisão, 2,9% é contexto de revisão,
  não uma nova "surpresa original" de -0,1 ponto.

O dado anterior e o consenso também devem ter sido
capturados antes do cutoff da previsão. Uma notícia que
já deveria existir, mas cujo dado ainda não tinha sido
recebido, não recebe preenchimento inventado.

## Entrega isolada

atlasquant_trader_macro_vintages_asof_lab.py recebe:
1. Um snapshot LAB_SYNTHETIC_MACRO_PRE compatível com o
   módulo anterior de consenso/indicadores.
2. Uma sequência de registros LAB_SYNTHETIC_MACRO_VINTAGE
   do MESMO evento, com sequência 0=INITIAL e
   seguintes=REVISED, cada qual com valor, fonte,
   horário de publicação e de captura.
3. Instante de emissão de viés e instante de avaliação
   com offset explícito.

Valida: identidade, ordem e numeração das revisões,
fonte, valor finito, primeira divulgação vs. calendário,
captura posterior à publicação, recibos cronológicos
e disponibilidade do consenso ANTES do cutoff.

Depois decide sem dados futuros:
- **SCHEDULE_ONLY:** release ainda é futuro; sem actual
  ou surprise;
- **RECUSA:** divulgação já deveria existir mas ainda
  não houve captura do primeiro resultado;
- **INITIAL:** usa apenas o primeiro resultado;
- **REVISED:** expõe o último valor REVISADO que já
  tinha sido CAPTURADO, como contexto separado.

A evidência compatível com o congelamento do viés D1
continua sendo a publicação ORIGINAL. Uma revisão
posterior não é passada automaticamente como se fosse
o valor inicialmente divulgado ou a surpresa daquele
dia. Um componente futuro poderá tratar revisões como
um novo tipo de notícia macro, mas só após regra própria
de interpretação e validação.

Dados de revisão posteriores ao cutoff não são expostos
na saída de pesquisa daquele cutoff.

## Testes

test_atlasquant_trader_macro_vintages_asof_lab.py contém
28 testes artificiais: consenso inicial, revisões,
publicação sem recebimento, seleção por horário,
falta/duplicação/reordenação, falhas de timestamp e
fonte, números inválidos, divulgação posterior,
retroatividade, integração com freeze D1 e bloqueio
de usar revisão como publicação original.

## O que ainda NÃO foi feito

Os registros e horários são inventados nos testes. O
arquivo histórico **real** com comunicado original,
consenso/vintage anterior, revisões, horários de
publicação, horário de captura e cadeia de custódia
ainda não foi obtido ou validado. O simples SHA-256
sem testemunha externa também não prova antiguidade.

Não se demonstrou previsão, diferencial econômico entre
duas moedas, retorno spot ou assertividade dos 28 pares.
Para evolução com dados reais, verificar fontes/termos,
preservar comunicados originais sem sobrescrever os
revisados, registrar a captura em horário confiável e
avaliar o viés exclusivamente com o que era conhecido
à época. Se alguma fonte original estiver ausente,
informar SEM DADO em vez de preencher retroativamente.

Continua LAB/HARD NO-GO: sem merge/deploy,
Worker, cron, API paga, novas despesas, trades,
alterações no Trader publicado ou acesso a dados
privados/contas de negociação.
