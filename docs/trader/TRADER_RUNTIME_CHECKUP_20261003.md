# TRADER RUNTIME CHECKUP — VEREDITO

Base main pós-#554: `1306a5642b101ab36c3dce232737531ca01d2d79`. Branch: `fix/trader-resident-data-sidebar-20261003`.

O runtime automático existe e persiste sete pares. O retorno precoce da interface deixava a apresentação desconectada. O hotfix antecipa o loader compacto existente (4 segundos por tentativa, cache 45 segundos) e hidrata somente apresentação. Nenhum motor, provider, peso, gate ou credencial foi alterado. Snapshot recente não renova técnico antigo.

## Evidência read-only

Branch `atlasquant-runtime`: status `2026-10-03T22:04:59.520477+00:00`; snapshot runtime `2026-10-03T22:04:57.892654+00:00`. Healthy e headless OK; `MARKET_CLOSED`. A execução observada não comprova uptime contínuo.

| Artefato | Blob SHA auditado |
|---|---|
| dados/autopilot_status_v107.json | 0871f660237804e40d5682d0c7aef3bf705ec087 |
| dados/atlasquant_home_snapshot_v1.json | a546ee443f7e504655a3c694fd5a9cf478e4669c |
| dados/twelve_series_v1108.json | 0b39dfe03a4e6906b65a8ac62383af6660eff869 |
| dados/master_market_map_v102.json | ecf264290087b05bedc7a6efc1d9ea5187c02607 |

## Checkpoint

Estados refletem a execução e o código auditados; mercado fechado e histórico não equivalem a sinal atual.

| COMPONENTE | ARQUIVO | ESTADO | AUTOMÁTICO | FONTE | COTA | PERSISTÊNCIA | CONSUMIDOR UI | FRESCOR | PROBLEMA | AÇÃO |
|---|---|---|---|---|---|---|---|---|---|---|
| Scanner 7FX | autopilot_v107.py | STALE_MARKET_CLOSED | cron | Twelve/cache | 480/dia | scanner/status runtime | home/Scanner/Radar | 1514–1721 min; 0 frescos | mercado fechado | mostrar últimos vieses e bloqueios |
| Budget | twelve_budget_v1108.py | RUNNING | por chamada | contador | 480/dia,28/h,6/62s | budget runtime | auditoria | usado 0; restante 480 no dia observado | não extrapolar para outro dia | preservar |
| Cadências | autopilot_quota_guard_v111.py | RUNNING | scheduler | plano existente | 55/115/235 min; prioridade 25/55 | cache/status | Autopilot | política existente | nenhuma alteração | preservar |
| Quota saver | autopilot_v107.py | RUNNING | habilitado | M15→H1/H4 | derivação sem HTTP extra | cache | análise existente | buckets completos/contíguos | não substituir timeframe exato em Paper | preservar |
| Cron | .github/workflows/autopilot-v107.yml | RUNNING | minutos 7,37 | Actions | mesmos limites | runtime branch | Autopilot | execução 22:04 UTC | cron não prova uptime | não editar |
| Home snapshot | atlasquant_fast_startup.py; atlasquant_trader_resident.py | RUNNING_BUT_DISCONNECTED_FROM_UI | produtor automático | snapshot validado | zero Twelve extra | home snapshot | Trader | snapshot ≠ técnico | st.stop antes da hidratação | reconectar |
| Signal Lifecycle | atlasquant_signal_lifecycle.py | STALE_MARKET_CLOSED | sim | referência técnica | zero extra | 7 pares;206 transições | home/detalhe/Radar | 6 EXPIRED;AUD NO_SIGNAL | snapshot novo não renova sinal | ranking exige CONFIRMED e validade futura |
| Arquitetura 28FX | atlasquant_scanner_queue.py | IMPLEMENTED_NOT_LIVE | contrato de fila | universo oficial | expansão não autorizada | resultados do worker | Radar | 7 runtime;21 sem técnico | continuous_worker_configured=false | não ativar 28 live |
| Quota Shadow | atlasquant_quota_shadow.py | RUNNING | sim | 500 amostras;364 mercado aberto | observação | shadow runtime | painel legado | 177 bloqueados;48,63% | validated=false;manual review não elegível | não aumentar cota |
| Ticker | atlasquant_compact_cockpit.py | RUNNING_BUT_DISCONNECTED_FROM_UI | leitura residente | ação/último viés | zero extra | snapshot | faixa Trader | por ativo e por técnico | PRÉVIA genérica ocultava evidência | distinguir atual/histórico/ausente |
| Mini-gráficos | twelve_cache_v1108.py | IMPLEMENTED_NOT_LIVE | cache do coletor | candles fechados | zero extra na UI | shared series={} | ticker | nenhum candle nesse artefato | não há série real para desenhar | permanecer sem gráfico; aceitar cache válido |
| DXY | fast_boot ranking/macro_eua | RUNNING | macro existente | força USD;FRED separado | zero extra | inputs/home | ticker/Macro | timestamp macro independente | DTWEXBGS não é spot DXY | força USD; preço/variação — |
| Índices | atlasquant_radar_board.py | IMPLEMENTED_NOT_LIVE | produtor live não localizado | DXY,US30,NAS100,SPX500,IBOV,WIN,WDO | nenhuma coleta nova | fast_boot.indices ausente | Índices | sem live | história só contém consumidores | universo neutro explícito |
| Criptos | atlasquant_radar_board.py | IMPLEMENTED_NOT_LIVE | produtor live não localizado | BTC/USD,ETH/USD,SOL/USD | nenhuma coleta nova | fast_boot.cryptos ausente | contrato/área cripto | sem live | não usar pesos Forex | classe separada e neutra |
| Market Map | master_panel_v102.py;market_map_core_v10.py | STALE_MARKET_CLOSED | Autopilot | master com7 contexts | cota existente | master_market_map_v102.json | Market Map/legado | contextos 02/10;map_current=false | mapa histórico | projeção dos packs; sem load duplicado |
| Macro/Fed | inputs fast_boot | RUNNING_BUT_DISCONNECTED_FROM_UI | headless/coleta | FRED/narrativa persistida | zero Twelve na UI | inputs/home | Macro/Fed | datas de observação FRED | shell sem contexto | resumo residente e acesso legado |
| Paper Trading | autopilot_paper_v112.py;paper_trading_v112.py | RUNNING | simulação | checklists | nenhuma ordem real | paper runtime | legado/auditoria | 7 checklists bloqueados | 0 trades | preservar |
| Model Paper | autopilot_model_paper_v1.py | RUNNING | simulação | setups | nenhuma ordem real | model runtime | legado/auditoria |387 candidatos;381 contexto/6 timeframe bloqueados |0 abertos/fechados | preservar timeframe exato |
| Setup Audit | autopilot_setup_audit_v114.py | RUNNING | sim | Paper | zero extra | audit runtime | legado/auditoria | AGUARDANDO AMOSTRA |0 trades auditados | não fabricar métricas |
| News Global | autopilot_v107.py | RUNNING | sim | agregação existente | política existente | news runtime | notícias/legado |22:04:38 UTC;219 histórias | disponibilidade não valida técnicos | preservar |
| News Nowcast/EODHD | autopilot_news_nowcast_v1.py | EXTERNAL_AUTH_BLOCKED | habilitado/cooldown | EODHD |1 request;retry360 min | provider state/status | notícias/auditoria |AUTH_ERROR HTTP401 | credencial/entitlement externo | documentar; não alterar chave |
| Decision/Flight | autopilot_v107.py | RUNNING | sim |7 packs | zero ordem |shadow389;Flight750(+7) |auditoria |persistência OK |sem promoção automática | preservar |
| Live event journal | status runtime/código existente | RUNNING |sim |eventos do coletor |provider_calls_added=false |500 eventos/120 heartbeats |auditoria |BUILDING_EVIDENCE |continuous_24h_confirmed=false |read-only;zero alteração AION |
| Coleta legada | .github/workflows/coleta_automatica.yml;coleta_automatica_v86.py | RUNNING |17:18 seg–sex America/Cuiaba |FRED/NewsAPI/EODHD |sem Twelve extra na UI |runtime |inputs/legado |agenda implementada |sobreposição macro não autoriza remoção | manter |

## Histórico, wiring e limites

Histórico completo consultado. `68157e5` introduziu o retorno da referência antes do bootstrap; fluxo ainda presente na main pós-#554. Os produtores não foram removidos pela #554. Snapshot/ranking/freshness, Macro/Fed e contexto dos packs não chegavam ao shell antes de `st.stop()`.

`90a3da9` adiciona consumidores `fast_boot.get("indices", [])`/`cryptos`. `48b326a` adiciona visão executiva com `index_ranking()`/`crypto_ranking()` sem observações live. Busca Git de introduções de chaves e produtores não encontrou coletor validado dessas classes. Não há restauração segura de produtor sem criar integração nova.

EODHD: workflow injeta `secrets.CHAVE_EODHD`; Autopilot propaga a variável; Nowcast lê a variável e passa `api_token`. Ausência seria NOT_CONFIGURED; observação foi AUTH_ERROR/401. Nenhum segredo impresso. A causa externa exata exige validação da conta.

Desktop: sidebar168 px; tablet701–1000:148 px; ícones18 px; quebra normal e rolagem interna. **24 acessos** da main preservados nos dois modos. Mobile: **Funções do Trader · 24 / Ver todas as funções · inclui avançadas**. Iniciante muda orientação, não remove módulos. Hover/focus não altera geometria.

Home mostra elegíveis confirmados ou os sete últimos vieses persistidos, com status temporal, referência/validade, H4/H1/M15, gate, prioridade e qualidade. Técnicos expirados não ganham posição nem Top10. Market Map mostra projeção já produzida nos packs: W1/D1, zona, níveis, risco, timestamp/map_current. Master completo auditado read-only; nenhum segundo fetch ao abrir a página. Acesso legado preservado.

Séries opcionais passam por `read_series`: candles fechados, timestamp e integridade. Adapter não chama `cached_series` nem coleta Twelve. Cache auditado vazio: nenhum gráfico no replay. DXY força USD não recebe preço ou direção inventados; broad dollar FRED fica identificado no Macro.

## Validação e evidências

Contratos: 286 testes e48 subtestes; scanner/cota/frescor:137 testes e24 subtestes; workflows/coverage:25 testes e2 subtestes; conferência final de apresentação/admin/boot:128 testes e4 subtestes. Suíte Quality completa:4160 testes, OK,1 skip previsto. Chromium completo:6 testes passaram; nova conferência direcionada do hotfix registrada no Draft PR. Compilação e git diff --check passaram. Contagens sobrepostas não são somadas. Nenhum teste removido. Fixtures positivas comprovam CONFIRMED com validade futura; negativos comprovam snapshot novo com técnico vencido ou não confirmado sem ranking. Home/Scanner/Radar/Fed/Market Map são renderizados com requests bloqueado em testes.

`visual_review/` contém cliques Streamlit, fixtures identificadas e replay do snapshot real com relógio de revisão explicitamente fixado no timestamp do artefato, sem modificar dados. Replay não é cotação live. Tamanhos1280×720,1440×900,1024×768,390×844; matriz existente também768×1024. Capturas: home/ticker/sidebar, menu mobile, Iniciante, Scanner, Radar, Fed, Market Map, Índices, cripto, Painel Mestre e detalhe/retorno.

Arquivos protegidos Autopilot/budget/cache/quota guard/quota shadow/workflow idênticos à base. Zero alterações AION Core/journal store/governance/auth/RBAC/providers/execução. SEM MERGE. SEM DEPLOY. SEM TRADE REAL. SEM AUMENTAR COTA. SEM ATIVAR 28FX LIVE SEM EVIDÊNCIA. SEM INVENTAR DADOS.
