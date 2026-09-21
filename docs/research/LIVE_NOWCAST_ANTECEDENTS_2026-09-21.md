# AtlasQuant — Live Nowcast Antecedents + Prospective Ledger · 21/09/2026

Este bloco conecta a fundação de Pré-Notícia/Nowcast a antecedentes econômicos
reais já publicados e cria coleta prospectiva automática no Autopilot.

## Objetivo

Antes de um release principal, o AtlasQuant passa a congelar um snapshot com:

- evento alvo;
- consenso;
- valor anterior;
- antecedentes disponíveis naquele instante;
- score agregado dos antecedentes;
- eventual distribuição empírica ABOVE / INLINE / BELOW quando já houver
  histórico suficiente;
- timestamp da captura;
- proveniência dos dados;
- campos de segurança.

Depois do release, o primeiro valor actual observado fecha o registro.
Revisões posteriores não reescrevem a previsão original nem o primeiro
resultado observado.

## Alvos iniciais

- Payroll / NFP;
- CPI;
- Core CPI;
- PCE;
- Core PCE.

## Antecedentes iniciais

### Payroll

- ADP Employment Change;
- Initial Jobless Claims;
- ISM Manufacturing Employment;
- ISM Services Employment.

A polaridade de Claims é invertida: claims acima do consenso normalmente
significam mais fragilidade no trabalho e, portanto, não podem receber o mesmo
sinal de ADP acima do consenso.

### CPI / Core CPI

- PPI;
- Core PPI;
- Import Prices.

### PCE / Core PCE

- CPI;
- Core CPI;
- PPI;
- Core PPI.

Headline e núcleo são separados para não contar o mesmo evento duas vezes.

## Score antecedente

Cada evento já realizado é comparado ao consenso que existia para aquele
release.

A surpresa é normalizada por uma escala de pesquisa e limitada a [-1,+1].
Depois os sinais são combinados por pesos transparentes.

Estado dos pesos nesta versão:

- weights_calibrated = false;
- política = TRANSPARENT_RESEARCH_HEURISTIC_V1;
- alteração automática = OFF.

Esses pesos são ponto de partida para pesquisa, não conclusão estatística.

## Regra point-in-time

Um antecedente só pode entrar se estava definitivamente disponível no momento
do snapshot.

Para timestamps com timezone explícito:

- scheduled_at < captured_at.

Para timestamps EODHD sem timezone documentado:

- o evento antecedente precisa estar em um dia anterior à captura;
- o alvo precisa estar em um dia posterior à captura;
- evento no mesmo dia não é usado para afirmar timing pré-release.

Isso reduz cobertura, mas evita look-ahead escondido.

## Timezone EODHD

A documentação pública do Economic Events informa o campo date com data e
hora, mas não documenta o timezone na descrição do campo.

Por isso o AtlasQuant não presume que um timestamp ingênuo está em UTC para
liberar captura no mesmo dia.

Política:

FAIL_CLOSED_SAME_DAY_WHEN_UNDOCUMENTED.

## Ledger prospectivo

Arquivo runtime:

- dados/news_nowcast_predictions_v1.csv

Uma linha por:

event_id + capture_day.

Assim, um mesmo Payroll pode ter snapshots em dias diferentes antes do release.
No histórico final, somente o snapshot mais próximo do release é usado como uma
observação independente daquele evento.

Isso evita inflar artificialmente a amostra contando três snapshots do mesmo
Payroll como três releases.

## Fechamento do evento

Quando o provider passa a devolver actual:

- todas as capturas daquele release recebem o primeiro actual observado;
- surprise_class vira ABOVE / INLINE / BELOW;
- closed = true;
- actual_seen_at é congelado;
- revisão posterior não altera o primeiro resultado capturado.

## Histórico empírico

O Live Nowcast só começa a mostrar distribuição empírica quando tiver histórico
fechado suficiente.

Enquanto isso:

- sinais antecedentes podem existir;
- signal_score pode existir;
- nowcast_state = INSUFFICIENT_HISTORY;
- percentuais ABOVE / INLINE / BELOW permanecem vazios.

O sistema não inventa confiança.

## Provider e orçamento

O Autopilot usa EODHD Economic Events como fonte desta etapa.

Para evitar chamadas excessivas:

- intervalo padrão entre consultas = 6 horas;
- uma consulta traz janela passada + futura;
- paginação é limitada e auditável.

Quando a primeira página de 1000 registros enche:

- é solicitada uma segunda página em offset 1000.

Se as duas páginas vierem cheias:

- estado = TRUNCATED_PROVIDER_DATA;
- o Nowcast não usa aquele conjunto;
- nenhuma previsão é fabricada.

## Runtime

Novos arquivos:

- autopilot_news_nowcast_v1.py
- atlasquant_nowcast_antecedents.py
- atlasquant_live_nowcast.py

Arquivos persistidos:

- dados/news_nowcast_predictions_v1.csv
- dados/news_nowcast_summary_v1.json
- dados/news_nowcast_provider_state_v1.json

Status do Autopilot:

- news_nowcast_v1.

## Integração com o Autopilot

Fluxo:

1. scanner/autopilot principal;
2. Paper genérico;
3. Model Paper por operacional;
4. Setup Audit;
5. Live News Nowcast sidecar.

Falha do News Nowcast nunca habilita ordem, nunca altera Gate e nunca mascara o
retorno estrutural do Autopilot principal.

## O que ainda NÃO acontece

- Nowcast não muda peso do macro automaticamente;
- Nowcast não muda Radar automaticamente;
- Nowcast não executa trade de notícia;
- acerto do dado não é convertido em previsão de candle;
- reação de preço não foi calibrada;
- pesos dos antecedentes ainda não estão calibrados;
- dados históricos reconstruídos não são tratados como vintage oficial.

## Próximos passos

1. deixar o runtime acumular previsões prospectivas;
2. mostrar o Live Nowcast no Admin;
3. comparar score antecedente vs resultado por indicador;
4. calibrar peso/escala com walk-forward;
5. estudar separadamente reação do preço;
6. somente depois avaliar integração controlada ao Radar.

## Segurança

- real orders = OFF;
- broker connection = OFF;
- trading news = OFF;
- look-ahead = OFF;
- auto weight change = OFF;
- market reaction prediction = OFF;
- profit probability = nenhuma.
