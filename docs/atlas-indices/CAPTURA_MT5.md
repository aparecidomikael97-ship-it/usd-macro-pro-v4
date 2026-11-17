# Captura de candles Pepperstone MT5 — contrato documental

**Estado:** LAB / SOMENTE LEITURA PLANEJADA / HARD NO-GO. **Não há exportador autorizado por este arquivo.**

## 1. Escopo

Fonte candidata: MT5 Demo Pepperstone; ativos EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, US500, NAS100 e XAUUSD. Timeframes **H1, D1, W1**. H1 ajuda a inspecionar fronteiras de sessão; D1 e W1 avaliam o viés.

A integração futura deverá ser **script local**, somente leitura, sem senha, sem número de conta nos arquivos, sem ordem e sem transmissão externa de dados. O MT5 deve estar aberto e a instância correta ser conferida.

**[CONFIRMADO POR ANÁLISE ESTÁTICA — conforme auditoria documental anterior]** Exportadores de laboratório da PR #2010 já exploravam OHLC, volume, spread e hashes, mas nenhum atendia integralmente o contrato único de oito ativos. Um caminho antigo com nomes fixos e os.replace pode substituir capturas. A reutilização requer auditoria dedicada, PR própria e autorização.

## 2. Dados por candle e manifesto

| Campo | Objetivo |
|---|---|
| symbol_exact, timeframe | Identificar o ativo e H1/D1/W1 |
| broker_server_name, instrument_spec_id | Fonte e contrato |
| open, high, low, close | OHLC observado |
| tick_volume, real_volume se houver, spread com unidade | Dados reportados, sem inventar valores |
| bar_state, bar_time_raw, bar_time_server | Estado e timestamp original |
| server_utc_offset_at_capture, calendar_version | Interpretar calendário e fuso |
| capture_at_utc, bar_close_at_utc | Elegibilidade temporal |
| clock_sync_status, clock_sync_evidence | Conferir precisão do relógio |
| batch_id, record_id, file_sha256 | Rastreabilidade dos arquivos |
| terminal_version, exporter_version | Reprodutibilidade |

Manifesto: lote, tipo PREVISÃO/RESULTADO, horários de início/fim, corte, quantidades esperadas/recebidas/válidas/ausentes, erros, hashes dos **bytes exatos armazenados**, tamanhos, versão e contrato.

## 3. Regra de elegibilidade

**Lote PREVISÃO:** finalizar antes do corte, apenas com dados capturados antes dele. **Lote RESULTADO:** coletar depois da vela avaliada terminar. Não sobrescrever previsão original.

**Corte:** 5 minutos antes da abertura D1/W1 autenticada para aquele instrumento. A vela que termina no início do próximo dia **ainda não estava fechada cinco minutos antes**. A última fechada elegível pode ser de dois dias/sessões atrás.

A posição 0 do MT5 costuma ser vela em formação; excluir posição 0 é proteção insuficiente sem checagem do calendário e do horário de fechamento. Somente velas comprovadamente fechadas entram no histórico fechado do método e dos três baselines. Nunca usar abertura, máxima, mínima ou fechamento que ainda não estivesse disponível no corte.

## 4. Tempo, fim de semana e revisões

Não assumir GMT+2/GMT+3 fixos. Registrar offset observado em **cada captura** e verificar carimbos H1/D1/W1 com sessões por ativo, datas de vigência, feriados e sextas especiais. A observação visual anterior sugeriu UTC+2, **não autenticado**.

Lacuna: registrar ativo, timeframe, instante esperado e falha, sem criar OHLC artificial. Vela de domingo/feriado: marcar para auditoria segundo calendário, não excluir automaticamente. Revisão: comparar duas capturas por servidor+símbolo+timeframe+timestamp original e registrar ambos os estados (OHLC, spread, volumes), preservando o primeiro arquivo.

## 5. Integridade e anterioridade

Cada execução usa lote novo, arquivos exclusivos e SHA-256 dos bytes armazenados. Hash verifica integridade dos bytes, não autenticidade de corretora nem relógio. Antes do congelamento, o lote PREVISÃO precisará de compromisso externo com timestamp verificável; o mecanismo de publicação automática exige autorização específica e nenhuma credencial poderá aparecer nos artefatos.

Uma publicação depois do corte implica **LOTE INVÁLIDO — PROVA DE ANTERIORIDADE AUSENTE**. Se MT5 estiver desligado, desconectado, demo indisponível, fuso desconhecido, candle obrigatório ausente ou captura tardia: **ABSTER-SE** ou lote inválido, com falha contabilizada; nunca reconstruir previsão depois do movimento.

## 6. Segurança e governança

O futuro exportador utilizará initialize() **sem login, senha ou servidor como parâmetros de autenticação**, somente para aproveitar o terminal já aberto, verificando qual instância respondeu. Nenhuma chamada de ordem, modificação de posição/conta, instalação, transmissão HTTP própria, rotina persistente ou agendamento sem autorização posterior.

Na auditoria, conferir código e dependências, lista efetiva de funções, todos os arquivos produzidos, ausência de dados de conta, preservação de originais, hashes, calendário, relógio e caminho de execução. A PR desta documentação **não** concede permissão para instalar pacote MetaTrader5, executar exportador, subir dados à nuvem ou publicar hash real.

**Pendências:** históricos H1/D1/W1, contratos e horários completos, sincronismo de relógio, validade da demo, especificações e calendário real dos oito ativos, aprovação técnica e permissões de eventual integração.

**Estado:** DOCUMENTO / LAB / AGUARDAR / HARD NO-GO.