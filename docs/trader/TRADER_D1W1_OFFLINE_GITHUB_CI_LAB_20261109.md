# AtlasQuant Trader — CI isolado para os contratos de viés D1/W1

**Estado:** laboratório; sem integração de ordens, MT5, contas, notícias ou produção.

## Motivo

Na branch da PR #1851 os testes Python foram executados em ambiente local, mas não havia workflow específico do AtlasQuant Trader. Criamos `.github/workflows/atlasquant-trader-d1w1-offline-lab.yml` para executar a mesma família de contratos no GitHub Actions a cada alteração relevante de uma PR, inclusive a PR #1851 cuja branch de destino é `lab/trader-mt5-g8-closed-bars-readonly-20261107` (ou por execução manual quando o workflow estiver disponível para disparo).

## Escopo

- Python **3.11 e 3.12**, para comparar as duas versões utilizadas no desenvolvimento e no PC do usuário.
- **19 módulos de testes** por versão, usando `unittest`, cobrindo o manifesto 28 FX x D1/W1, horários e horário de verão em Nova York, captura documental MT5, relógio, lacunas, eventos macro, política monetária, filtros de regime, seleção e comparação sem omissões.
- Apenas bibliotecas padrão de Python; não há `pip install`, nem importação/consulta ao terminal MetaTrader 5 durante o workflow.
- Permissões GitHub mínimas: `contents: read`; checkout sem credenciais persistidas; nenhum segredo de broker, execução de ordens, deploy, merges, Workers ou chamadas de rede a mercados.
- `timeout-minutes: 8` por job; cancelamento de runs anteriores do mesmo pull request. Há consumo de minutos de CI, mesmo que o GitHub ofereça runners gratuitos em repositórios públicos; nenhum serviço novo foi contratado.
- O teste contém **dados sintéticos**. Não certifica assertividade real, calendário do servidor, vintage econômico, autenticação Pepperstone nem pré-compromisso temporal de previsões.

## Base real da PR

A PR #1851 não aponta para `main`: o GitHub informou a base `lab/trader-mt5-g8-closed-bars-readonly-20261107`. Por isso **não** filtrar `pull_request.branches` para `main`; o filtro principal é a lista de caminhos de arquivos.

## Execução e interpretação

O workflow só passa a existir no GitHub após seu commit na PR. A definição YAML foi validada localmente; **a conclusão do workflow só pode ser afirmada depois de uma execução observada no GitHub Actions**. O workflow pode ser bloqueado por permissões/configuração da plataforma; na ausência de um run, registrar “não executado”, nunca declarar sucesso de CI.

A rotina **não** publica indicadores, altera UI, agenda tarefas ou desbloqueia sinais. `operational_bias=AGUARDAR`, `trade_authorized=False` e `validated_directional_accuracy=None` permanecem invariáveis. O AM12 segue como dependência separada para os dados reais.
