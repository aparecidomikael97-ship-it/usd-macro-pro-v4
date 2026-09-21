# AtlasQuant — Model-specific Paper Ledger · 20/09/2026

Este bloco transforma os candidatos explícitos dos detectores ICT em uma coleta
Paper prospectiva separada por operacional.

## Objetivo

Comparar Backtest × Paper/Forward sem olhar o resultado para decidir depois se
uma operação "era FVG", "era OTE" etc.

A identidade do operacional nasce no detector e permanece congelada.

## Operacionais iniciais

- FVG;
- OTE;
- CRT;
- AMD / PO3.

Cada candidato possui:

- candidate_id — snapshot daquela leitura;
- episode_id — identidade estável da mesma estrutura/zona;
- setup_id;
- source_model e source_timeframe;
- par e direção;
- captured_at;
- status/score do detector;
- evidência observável do modelo.

## Episode ID

O Autopilot pode repetir o mesmo estado em várias varreduras. Para não fabricar
dezenas de trades iguais, o Paper usa episode_id construído com a estrutura
estável do setup.

Exemplos:

- FVG: zona low/high;
- OTE: zona + swing;
- CRT: anchors + lado da varredura;
- AMD: range de acumulação + lado da manipulação.

Mudança apenas de horário de captura, score ou preço corrente não cria outra
operação do mesmo episódio.

## Duas camadas de observação

Todo candidato confirmado entra na coorte de pesquisa.

Depois o AtlasQuant verifica o contexto global:

1. dados atuais e suficientes;
2. Decision Integrity;
3. hard blocks;
4. soft blocks;
5. Gate;
6. risco de evento/contexto.

Se o modelo apareceu, mas o contexto global bloqueou:

- o candidato não é escondido;
- status = BLOCKED_CONTEXT;
- nenhum trade Paper é aberto.

Isso permite comparar futuramente:

- setup bruto;
- setup + filtro/contexto global.

## Entrada e saída

Para candidatos qualificados:

- entrada espera candle M15 posterior ao captured_at;
- ATR é calculado apenas com candles anteriores à entrada;
- stop = 1 ATR;
- alvo = 2R;
- stop e alvo no mesmo candle = LOSS conservador;
- máximo = 96 M15 / 24h;
- fricção conservadora é aplicada depois, separada do resultado bruto.

Essas regras são de pesquisa e não significam que serão as regras finais de
execução de cada operacional.

## Ledger separado

Arquivos runtime:

- dados/model_paper_trades_v1.csv
- dados/model_paper_summary_v1.json

O Paper genérico V11.2 continua separado para não quebrar o histórico anterior.

## Admin / Passaporte

A Central Admin pode ler:

- Paper Audit genérico;
- Model Paper explícito.

Os registros válidos são convertidos em evidência Forward/Paper por setup e
cruzados com o Passaporte correspondente.

Evidência de FVG nunca é usada para completar OTE/CRT/AMD e vice-versa.

## Segmentação

O resumo já separa:

- operacional;
- sessão;
- candidatos observados;
- bloqueados por contexto/dados;
- pendentes;
- abertos;
- fechados;
- wins/losses;
- R observado.

Essa base também prepara o Radar por perfil de horário (Ásia/Londres/Nova York).

## Segurança

- real orders = OFF;
- broker connection = OFF;
- auto strategy selection = OFF;
- auto promotion = OFF;
- setup inference from outcome = OFF;
- nenhuma chamada extra de market data pelo Model Paper;
- usa scanner/cache já coletado;
- ausência de evidência não é preenchida por chute.
