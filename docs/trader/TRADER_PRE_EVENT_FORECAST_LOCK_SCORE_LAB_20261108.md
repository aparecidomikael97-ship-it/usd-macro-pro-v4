# AtlasQuant Trader — previsão pré-evento congelada e avaliação posterior (LAB)

**Data:** 08/11/2026. **Estado:** pesquisa local, sem operação, publicação, custo ou agendamento ativado.

## Objetivo

Preservar a previsão registrada **antes** do resultado de uma notícia econômica e
avaliar, **depois**, se o valor previsto pelo modelo ficou mais perto do resultado
do que o consenso dos analistas e o valor anterior. Não transformar a notícia em
sinal automático de compra/venda.

## Arquivos

- `atlasquant_trader_event_forecast_lock_lab.py` — funções puras, sem HTTP,
  persistência ou worker.
- `test_atlasquant_trader_event_forecast_lock_lab.py` — testes sintéticos de
  ordem temporal, integridade, identificação, métricas e estado seguro.

## Como funciona

1. **Antes da divulgação:** receber evento, moeda, indicador, período, unidade,
   valor anterior, consenso, estimativa opcional do modelo, versão, datas de
   disponibilidade e declarações opcionais de hash das fontes.
2. **Congelar:** rejeitar dados capturados após o instante de análise, notícia
   já divulgada, série/unidade incompatível ou dados não numéricos. Serializar
   a previsão com campos ordenados e calcular SHA-256 de seu conteúdo.
3. **Aguardar:** o resultado real permanece **desconhecido** antes da
   divulgação. Não existe preenchimento presumido.
4. **Depois da divulgação:** aceitar apenas uma **alegação** de valor real cuja
   publicação e captura tenham datas compatíveis; verificar identidade da
   série, mês e unidade; calcular erros absolutos e surpresa aritmética.

## Exemplo 100% sintético (não é previsão real para outubro)

| Campo | Valor fictício |
| --- | ---: |
| CPI anterior mensal | 0,6% |
| Consenso | 0,3% |
| Previsão do modelo de laboratório | 0,35% |
| Resultado fictício posterior | 0,4% |
| Erro absoluto do modelo | 0,05 ponto percentual |
| Erro absoluto do consenso | 0,1 ponto percentual |
| Erro absoluto do anterior | 0,2 ponto percentual |

Esse exemplo **não** constitui acerto histórico, estimativa real, taxa de
assertividade ou probabilidade de direção de mercado.

## Limites de confiança que não podem ser omitidos

- Um hash SHA-256 prova apenas consistência do conteúdo recebido, **não** prova
  que o registro foi criado antes da divulgação: é possível editar o conteúdo
  e recalcular outro hash. É necessário testemunho externo imutável da hora de
  publicação, por exemplo commit/documento carimbado e conservado antes do
  evento, para prova auditável de *previsão ex ante*.
- `previous_source_sha256_claim` e `consensus_source_sha256_claim` ainda são
  alegações. Não provam sozinhos o texto original, o emissor, a metodologia do
  consenso ou o horário verdadeiro em que a informação estava disponível.
- `ActualClaim` é **alegação posterior**; o módulo não baixa nem autentica a
  publicação oficial ou suas eventuais revisões. Exige conferência posterior
  contra o original do órgão emissor.
- `model_version` é uma etiqueta; hiperparâmetros e treinamento não foram
  atestados por terceiro, nem está demonstrado que não houve *data leakage*.
- Comparar o erro absoluto de um único evento **não mede assertividade**.
  Backtest honesto precisa de muitos eventos, janelas fora da amostra,
  vintages de dados, métricas pré-definidas e comparação com consenso e
  previsão ingênua; também são necessários resultados de eventos difíceis.
- Um CPI acima/abaixo do consenso não determina automaticamente alta/baixa
  do USD nem de um índice: reação depende das expectativas, composição,
  juros e posicionamento do mercado.

## Resultado entregue

Estados retornados: `LAB_FORECAST_BLOCKED`,
`LAB_PRE_EVENT_FORECAST_LOCKED_DOCUMENTARY_ONLY` e
`LAB_POST_EVENT_DESCRIPTIVE_SCORE_UNATTESTED`.

Em **todos** os estados: `operational_bias=AGUARDAR`, `fx_bias=None`,
`index_bias=None`, probabilidade calibrada ausente, acurácia validada ausente,
operações/alertas/workers/agendamentos proibidos e custo adicional igual a zero.

## Próximas etapas, ainda não implementadas

1. Integrar fontes oficiais do valor divulgado e originais verificáveis do
   consenso/valor anterior com carimbo temporal confiável.
2. Registrar previsões verdadeiras **antes** de cada evento, sem olhar o futuro;
   preservar método, código e parâmetros.
3. Avaliar várias divulgações com *walk-forward*, erros por indicador e
   comparação com consenso; analisar incerteza sem prometer 80% ou 90%.
4. Somente após validação, estudar reação no câmbio/índices e eventual
   contribuição para o viés diário/semanal, com regra de abstenção.

**Checkpoint Mestre preservado:** AtlasQuant Trader tem prioridade; AION e
Negócios permanecem congelados; não ativar worker/deploy/operação real ou
contratar fonte paga sem nova decisão do usuário.
