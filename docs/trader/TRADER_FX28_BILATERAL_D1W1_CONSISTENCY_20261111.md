# AtlasQuant Trader — simetria dos 28 pares e concordância D1 × W1 (11/11/2026)

**LAB / pesquisa offline / sem cotação de mercado / sem viés operacional / sem operações.** Esta etapa amplia a auditoria do núcleo do Radar, com foco em consistência, seletividade e transparência da matriz G8.

## Por que a checagem importa

O universo G8 contém **8 moedas** e **28 pares únicos**. Uma mesma informação de USD pode afetar os **7 cruzamentos USD**; esses efeitos não são 7 notícias independentes nem 7 validações independentes da estratégia. A relação matemática bilateral não prova causalidade, lucratividade, probabilidade ou direção efetiva do preço.

A matriz usa *pontos sintéticos de hipótese*. Diferença de pares representada como **pontos da moeda-base menos pontos da moeda-cotada**; para uma inversão de orientação a diferença precisa inverter o sinal. Em qualquer triângulo coerente: pontos(A/B) + pontos(B/C) = pontos(A/C). O teste local confirma essas identidades para dados declarados, **não a qualidade econômica dos dados**.

## Parte 1: auditoria de simetria FX28

Arquivo: `atlasquant_trader_fx28_bilateral_symmetry_guard_lab.py`; testes: `test_atlasquant_trader_fx28_bilateral_symmetry_guard_lab.py`.

- Confere exatamente **8 moedas e 28 pares** canônicos e a consistência entre os seus números/labels.
- No caso sintético completo, executa **28 testes de inversão implícita** e **56 triângulos matemáticos**; não recebe pares invertidos não-canônicos como um 29.º instrumento.
- Respeita duas janelas preliminares de *idade do escore sintético*: D1 até 12h e W1 até 3 dias. **Essas janelas não foram calibradas por resultados de mercado e não substituem validação da data/hora de origem de cada indicador macro**.
- Moeda com escore vencido exige `AGUARDAR` **nos 7 pares que a contêm**; outros cruzamentos não são automaticamente bloqueados.
- Um hash hexadecimal fornecido pelo chamador não autentica, por si, que a fonte seja oficial. `operational_bias=AGUARDAR` sempre.
- **15 testes sintéticos** aprovados localmente e na CI.

## Parte 2: conferência simultânea D1 × W1 dos 28 pares

Arquivo: `atlasquant_trader_fx28_d1w1_consensus_guard_lab.py`; testes: `test_atlasquant_trader_fx28_d1w1_consensus_guard_lab.py`.

- Executa primeiro a auditoria bilateral completa, **em dois instantes históricos separados** (corte W1 não posterior ao corte D1).
- Exige que ambas as matrizes possuam **os 28 pares canônicos**: nenhuma seleção silenciosa de apenas os exemplos mais favoráveis.
- Para cada par, retorna somente um estado de pesquisa:
  - `CONCORDANTE_HIPOTESE`: labels direcionais relativos D1 e W1 coincidem;
  - `CONFLITO_D1_W1`: labels relativos apontam lados diferentes;
  - `NEUTRO_EM_UM_HORIZONTE`: pelo menos um deles não tem direção sintética acima do limiar;
  - `AGUARDAR_DADOS`: pelo menos um horizonte sem escore/label utilizável.
- **NENHUM dos quatro estados gera trade, certeza, probabilidade calibrada ou sinal publicado.** Até a concordância dupla é somente um filtro teórico; pode estar igualmente errada se a macro original estiver errada.
- Em teste com USD D1 vencido: seus 7 cruzamentos ficam em `AGUARDAR_DADOS`, enquanto os 21 outros são avaliáveis. Em teste com pontos diários e semanais opostos para USDJPY: `CONFLITO_D1_W1`, nunca sinal.
- O pipeline compara datas e assinaturas de dados reclamadas, mas **não autentica os hashes contra o conteúdo de emissores ou o momento em que o mercado recebeu os dados**.
- **12 testes sintéticos da etapa D1/W1 + 15 da simetria inicial = 27 testes locais aprovados**. Ambos os arquivos também integram `.github/workflows/atlasquant-trader-d1w1-offline-lab.yml` em Python 3.11 e 3.12.

## Limites e decisão

Não existe, nesta etapa, um sistema real de *currency strength* macro calibrado, nem pontuações reais verificadas para a totalidade G8; números dos testes são **fictícios**. Critérios não cumpridos para produção: proveniência original, métricas macro comparáveis em ambas as moedas, período/horário de divulgação, regime, calendário econômico e geopolítica, reação de preços MT5, pesquisa prospectiva fora da amostra e custos de execução. Querer alta assertividade não é prova de 80% ou 90% de acerto.

**Prioridade prática a seguir:** conectar estas verificações apenas como *auditoria de consistência documental* às vintages macro D1/W1 que já existem, sem inventar escore; depois medir impacto incremental em coortes prospectivas. A macro bilateral e a abstenção continuam antes de OB/FVG/scanners. PPI de 13/11 tem duas fontes de consenso capturadas antes do evento, com conferências de 12/11 e 13/11 já agendadas; evitar duplicação de notificações.

**Estado:** GO-LAB, NO-GO publicação/integração operacional, HARD NO-GO operações reais; `new_cost_brl=0`. Branch `lab/trader-mt5-28fx-live-coverage-20261107`, PR #1851 segue em rascunho. Script Flow PRO v1.1 guardado e não alterado.
