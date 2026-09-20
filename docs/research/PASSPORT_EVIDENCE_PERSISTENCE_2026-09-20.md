# AtlasQuant — Passaporte, Escada de Evidências e Persistência · 20/09/2026

Este bloco conecta o Passaporte do Operacional às etapas de validação que já
existem no AtlasQuant e cria um histórico de pesquisa separado do código.

## Escada de Evidências

O Passaporte agora pode cruzar:

1. Backtest;
2. estabilidade temporal;
3. walk-forward/OOS;
4. sensibilidade a custos e slippage;
5. robustez de parâmetros pré-definidos;
6. Forward/Paper;
7. Shadow;
8. revisão humana.

A última etapa continua obrigatoriamente humana. A escada não é probabilidade
de lucro e não promove um setup.

Os critérios quantitativos seguem a mesma linha conservadora da Validação
Privada: amostra histórica, amostra Forward/Paper, expectativa observada,
profit factor, drawdown, regimes, sessões, diferença Backtest × Forward,
estabilidade, OOS, fricção e parâmetros.

## Backtest e Comparador

Cada backtest individual cria uma Escada de Evidências em memória. Como um
backtest isolado ainda não possui todos os diagnósticos, as etapas ausentes
aparecem como pendentes.

No Comparador dos cinco operacionais, o AtlasQuant já aproveita os resultados
de:

- estabilidade temporal;
- walk-forward;
- fricção;
- robustez de parâmetros quando ela é executada.

Os cinco Passaportes permanecem independentes.

## Paper/Forward

No Admin, o Diário Paper/Forward pode ser importado e relacionado ao Passaporte
do operacional. Backtest e Paper são mantidos como fontes distintas.

O sistema mede a diferença de expectativa entre as duas amostras. Diferença
grande é uma lacuna de evidência, não uma autorização para reajustar parâmetros
automaticamente.

## Shadow

A Escada consegue consumir o resumo do Shadow Mode já existente. Shadow pode
ser usado como evidência adicional, sem alterar a regra de promoção manual.

## Histórico persistente

Novos módulos:

- atlasquant_research_evidence_store.py
- atlasquant_research_evidence_capture.py

O histórico usa o arquivo:

dados/atlasquant_operational_evidence_v1.jsonl

e somente pode ser gravado na branch dedicada de runtime. Tentativa de gravar
em main/atlasquant-dev falha fechada.

O Backtest registra evidência primeiro na sessão, sem fazer leitura/escrita
remota. No Admin, o histórico pode ser hidratado e persistido no Runtime de
forma idempotente.

Cada registro possui record_id determinístico para evitar duplicatas.

## Monitor de mudança do Passaporte

Novo módulo:

- atlasquant_passport_drift.py

O Admin compara os dois snapshots mais recentes de cada operacional e destaca
mudanças relevantes em expectativa observada, profit factor, drawdown,
qualidade dos dados, diferença Backtest × Paper e regressão do estado de
evidência.

Esses alertas significam apenas **revisar**. Eles não provam mudança
institucional e não alteram setup, Gate, pesos ou execução automaticamente.

A ordenação temporal normaliza timestamps com Z/offset para evitar comparar
snapshots fora de ordem.

## Cobertura × suficiência

A Escada separa duas ideias:

- **cobertura** — a etapa de evidência existe;
- **suficiência** — a etapa atende aos critérios conservadores de revisão.

Shadow permanece opcional por padrão. Quando não é exigido, sua ausência não
reduz a cobertura das etapas obrigatórias.

## Segurança

- nenhuma ordem real;
- nenhuma conexão de corretora adicionada;
- nenhuma promoção automática;
- nenhuma alteração automática de estratégia;
- nenhuma mudança automática de pesos/gates;
- nenhuma evidência faltante é fabricada;
- histórico de pesquisa não é gravado em branch de código;
- cobertura de evidência não é apresentada como probabilidade de ganho.

Próximo passo: alimentar automaticamente o histórico com evidência prospectiva
do Paper/Setup Audit, reduzindo a necessidade de importar manualmente o diário,
e depois cruzar essa evidência com o Detector de Mudança de Comportamento sem
reotimização automática.
