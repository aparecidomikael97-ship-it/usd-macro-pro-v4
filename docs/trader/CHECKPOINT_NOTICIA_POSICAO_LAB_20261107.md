# AtlasQuant Trader — Notícia × Posição Aberta (resgate do Checkpoint Mestre)

**Estado:** EM IMPLEMENTAÇÃO / LAB isolado — **NÃO VALIDADO PARA PRODUÇÃO**.
**Prioridade preservada:** viés W1/D1 dos 28 pares; M15 como confirmação; abas Início, Radar e Painel Mestre.

## Origem da decisão

- Checkpoint oficial: `docs/trader/CHECKPOINT_MESTRE_FOCO_TRES_ABAS_20261104.md`, etapa de separar surpresa vs consenso, risco de evento, fonte e horário, sem inventar causalidade.
- Fundação existente: `atlasquant_news_nowcast.py` prevê a classe **do dado** acima/em linha/abaixo do consenso; `atlasquant_news_backtest.py` só mede essa previsão com walk-forward.
- Fundação existente: `atlasquant_position_event_manager.py` já diferencia notícia favorável/contrária/neutra/incerta à posição em pre/post-evento e exige revisão humana.
- Registro da regra recuperada com Mikael em 07/11/2026: caso a notícia favoreça o lado da posição, considerar a manutenção; caso confronte a tese, reavaliar saída/stop; **jamais fechar ou manter cegamente** por causa de um único headline.

## Etapa implementada neste Draft

Novo módulo de auditoria read-only `atlasquant_position_news_audit_lab.py`, que:

1. Recebe posição LONG/SHORT e par base/cotada; deriva exposição correta a cada moeda.
2. Aceita um release com período, unidade, anterior, consenso, atual, tolerância, horários separados e URLs de referência.
3. Classifica **surpresa do indicador** (atual versus consenso, não versus anterior) pela rotina já existente.
4. Só exibe **hipótese de alinhamento com a posição** quando timestamps não têm look-ahead e revisão de fonte, consenso, revisões e contexto foi declarada.
5. Se o evento condicional favorece a tese, apresenta `REAVALIAR_MANUTENCAO_COM_RISCO`; se conflita, `REAVALIAR_SAIDA_STOP_E_TESE`. Na falta de prova, `AGUARDAR_EVIDENCIA`.
6. Mantém sempre `broker_command=None`, sem saída/entrada automática, com `probability_of_move_against_position=None`.

## Bloqueios que ainda impedem uso real

- Histórico point-in-time de consenso *da própria divulgação* ainda não possui cobertura/auditoria geral.
- Falta histórico pareado de **reação do preço por ativo, horizonte e regime** para calibrar probabilidade de movimento contrário. Acertar o indicador **não** equivale a acertar o par.
- Não há autenticação independente de fonte apenas por URL/flags; exigir documentos originais, vintages e cadeia de custódia.
- Não há integração com o fluxo vivo de posições/MetaTrader ou com o painel publicado.
- O Guardian de risco, slippage, spread, stops e autorização de execução não foram integrados/homologados.

## Testes e critérios para avançar

- Testes sintéticos por lado LONG/SHORT, notícia sobre moeda base/cotada, surpresa distinta do efeito da moeda, ausência de dados e bloqueio temporal.
- Backtest futuro em duas tarefas **separadas**: (a) prever o dado; (b) estimar reação de preço/risco de tese. Medir abstenções e custo de erro além dos acertos.
- Somente após fontes, modelo de reação calibrado, revisão humana e homologação específica avaliar sinal no Painel Mestre. Nada neste Draft autoriza merge, deploy, Worker, contratação, ordem real ou intervenção na posição de Mikael.

**Próximo foco retoma o combinado:** completar evidência macro bilateral G8 (inflação, política monetária, consenso e vintage), depois reagir a notícias com os fatos disponíveis.

## Reafirmação 07/11 — Previsão do próprio resultado da notícia

O proprietário voltou a confirmar a estratégia anterior: **antes da divulgação**
de CPI/NFP/PCE etc., estimar com séries históricas e sinais antecedentes a
probabilidade de **ABAIXO / EM LINHA / ACIMA** do consenso, além de uma
estimativa do número. Exemplo inteiramente hipotético: CPI anterior 4,0%;
consenso 4,1%; a questão é prever a distribuição do resultado a publicar,
não confundir 4,0% anterior com o consenso 4,1% e não presumir preço em alta.

**Já existe:** `atlasquant_news_nowcast.py` faz suavização de frequências
históricas ABOVE/INLINE/BELOW e propõe número `consenso +
surpresa_média_de_análogos`. `atlasquant_news_backtest.py` mede walk-forward,
acerto de classe, erro numérico, Brier e calibração aparente por mês e indicador.
O código atual **não usa o valor anterior diretamente na fórmula**: poderá
entrar como indicador antecedente apenas após método justificado e calibrado.

**Teste fictício de contrato:** 50 releases com surpresas fabricadas e consenso
4,1% produziram cerca de 39,62% abaixo, 20,75% em linha, 39,62% acima,
estimativa 4,1% e `calibrated=False`. Walk-forward sintético gerou 10
previsões e apenas 20% de acerto de classe; **nenhum desses percentuais
mede capacidade preditiva real**. São testes de comportamento de software.

**Falta antes de alimentar o viés D1/W1:** obter conjunto licenciado/verificável
do consenso e suas revisões com carimbo pré-release, valores originalmente
divulgados, data de efetiva publicação (não só a data agendada), histórico
substancial por indicador e série, separação treino/teste temporal e walk-forward
fora da amostra. Calibrar e comparar contra o baseline simples do consenso;
sem ganho sustentado e cobertura suficiente, mostrar `AGUARDAR` e percentuais
operacionais indisponíveis. Prever o dado **não** é prever a reação do preço,
e nenhuma das duas autoriza automaticamente manter/fechar uma posição.
