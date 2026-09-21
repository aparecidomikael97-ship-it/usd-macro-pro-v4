# AtlasQuant — Pré-Notícia / Nowcast + Backtest de Indicadores · 20/09/2026

Este bloco cria a fundação auditável para a ideia aprovada de estimar, antes do
release, se um indicador econômico tende a vir acima, em linha ou abaixo do
consenso — e depois medir se a estimativa realmente funcionou.

## Separação obrigatória

O AtlasQuant trata como problemas diferentes:

1. **prever o dado econômico**;
2. **prever a reação do preço**;
3. **decidir se existe contexto operacional**.

Acertar Payroll acima do consenso não significa acertar EUR/USD, DXY ou índice.
A reação depende de salários, desemprego, revisões, Fed, juros, precificação,
posicionamento e risco.

A primeira versão deste bloco mede somente o item 1.

## Anterior, consenso e atual

O calendário passa a ensinar:

- **Anterior** — última leitura publicada disponível antes do novo release;
- **Consenso** — expectativa agregada antes da divulgação;
- **Atual** — leitura divulgada agora.

A surpresa é sempre comparada ao consenso, não apenas ao número anterior.

## Guia específico por indicador

Novo módulo:

- `atlasquant_indicator_scenarios.py`

Famílias iniciais:

- CPI / Core CPI;
- PCE / Core PCE;
- Payroll / NFP;
- desemprego;
- salários;
- Jobless Claims;
- ADP;
- PPI;
- PMI / ISM;
- PIB / GDP.

Cada família explica ABOVE / INLINE / BELOW com ressalvas próprias.

Não existe regra universal "acima = dólar sobe".

Exemplo: desemprego acima do consenso normalmente sinaliza trabalho mais fraco;
Jobless Claims acima normalmente também aponta fragilidade. Já inflação acima
tem uma leitura macro diferente.

## Sinais antecedentes

Novo módulo:

- `atlasquant_news_nowcast.py`

Cada sinal antecedente possui:

- nome;
- timestamp observado;
- direção padronizada de -1 a +1;
- peso;
- fonte;
- detalhe.

Qualquer antecedente observado **depois** do snapshot pré-release é rejeitado.

O score combinado é uma média ponderada transparente. A transformação de ADP,
Claims, ISM Employment etc. em contribuição padronizada ainda precisa ser
calibrada com histórico; esta fundação não inventa pesos econômicos finais.

## Nowcast empírico

Para um novo release:

1. seleciona somente releases históricos do mesmo indicador;
2. exige que eles já tivessem acontecido antes do momento da previsão;
3. procura análogos pelo score antecedente;
4. usa frequência empírica suavizada de ABOVE / INLINE / BELOW;
5. estima o número pelo consenso atual + surpresa média dos análogos.

Se não existe amostra histórica mínima:

- estado = `INSUFFICIENT_HISTORY`;
- percentuais = nenhum;
- estimativa = nenhuma.

O sistema não fabrica "64% acima" quando não há base.

## Percentuais do nowcast

Os percentuais são:

**frequências empíricas de classes do dado em amostras semelhantes.**

Eles NÃO são:

- probabilidade de gain;
- probabilidade do candle subir;
- certeza da notícia;
- autorização para aumentar risco.

O campo `calibrated` permanece falso até existir evidência de calibração
adequada.

## Backtest walk-forward de notícias

Novo módulo:

- `atlasquant_news_backtest.py`

Para cada release histórico, o AtlasQuant volta ao snapshot pré-release e usa
somente releases que já tinham acontecido naquele momento.

Métricas:

- acerto de ABOVE / INLINE / BELOW;
- Brier score multiclasses;
- confiança média;
- gap confiança × acerto;
- erro numérico absoluto;
- resultado por indicador;
- resultado por mês.

Isso permite a leitura pedida no produto:

**"neste mês o modelo acertou 8 de 10 releases"**,

sempre acompanhada de:

**"isso é taxa de classificação do dado; não é taxa de gain."**

## Laboratório Admin

Novo módulo:

- `atlasquant_news_research_panel.py`

O Admin recebe um modelo CSV de histórico point-in-time e consegue rodar o
walk-forward sem alterar pesos do sistema.

Colunas centrais:

- indicator;
- scheduled_at;
- captured_at;
- consensus;
- actual;
- signal_score;
- tolerance;
- unit.

Snapshot capturado depois da divulgação é rejeitado.

O laboratório mostra resultado geral, mensal e por indicador, além das
previsões individuais e releases sem amostra suficiente.

## Calendário didático

O calendário econômico ganhou uma área educativa que explica:

- anterior;
- consenso;
- atual;
- ABOVE / INLINE / BELOW;
- ressalva específica de cada indicador reconhecido.

Indicador desconhecido falha fechado: o AtlasQuant não aplica uma direção
genérica.

## Estado desta etapa

Pronto:

- contratos point-in-time;
- nowcast empírico;
- walk-forward;
- métricas/calibração inicial;
- scorecards mensais;
- laboratório Admin;
- guia de cenários do calendário.

Ainda não pronto:

- coleta histórica automática de todos os consensos;
- criação automática do score antecedente por indicador;
- modelo separado da reação do preço;
- integração automática do nowcast ao Radar;
- ajuste automático de peso.

## Próxima etapa recomendada

1. criar adaptadores de antecedentes por indicador;
2. começar por Payroll, CPI/PCE e Jobless/ISM;
3. persistir cada previsão antes da divulgação;
4. depois do release, fechar o registro com actual + revisões;
5. acumular calibração real;
6. somente então estudar se a camada de reação de preço agrega valor.

## Segurança

- look-ahead = proibido;
- real orders = OFF;
- trade de notícia automático = OFF;
- alteração automática de peso = OFF;
- profit probability = nenhuma;
- acerto do dado != acerto do mercado.
