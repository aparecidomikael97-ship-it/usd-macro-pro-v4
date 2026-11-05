# AtlasQuant Trader — proteção da entrega ZIP de preços M1 (LAB)

**Data da etapa:** 2026-11-05. **Custo novo:** R$ 0. **Estado:** somente testes offline, sem cotações reais importadas nesta etapa.

## Contexto

O HistData anuncia download manual gratuito de dados Forex M1 e tick. Seu FAQ explica que os downloads oferecem informações sobre lacunas nas observações. O formato Generic ASCII M1 publicado é Bid OHLC em horário EST fixo UTC−05:00 **sem** ajuste por horário de verão. As referências primárias são:

- https://www.histdata.com/download-free-forex-data/
- https://www.histdata.com/f-a-q/
- https://www.histdata.com/f-a-q/data-files-detailed-specification/

O acesso FTP/SFTP oferecido pelo fornecedor é **pago** e não faz parte do trabalho. Não houve contratação, download automático, scraping de área protegida nem atribuição de licença de uso comercial a um arquivo gratuito.

## Entrega técnica

O módulo `atlasquant_trader_histdata_zip_receipt_lab.py` recebe **bytes de ZIP já fornecidos e um nome local informado**. Exige um único membro `DAT_ASCII_<PAR>_M1_<AAAAMM>.csv`, podendo haver um único `.txt` simples como relatório acessório. Não exige nem inventa nome oficial do ZIP externo. Lê o conteúdo apenas na memória e delega a verificação de minutos e candles M15 ao leitor `atlasquant_trader_histdata_m1_bid_window_lab.py` existente.

Proteções:

- Valida tamanho máximo do ZIP, do CSV e do `.txt`, taxa de compressão, quantidade de entradas e extensão.
- Bloqueia caminhos internos, arquivos executáveis, entradas repetidas, links simbólicos, arquivos criptografados, formatos de compressão não permitidos, ZIP truncado e falha de CRC.
- Não extrai nada em disco. SHA-256 do ZIP, do CSV e do eventual `.txt` servem para futura comparação de cópias, **não são assinaturas digitais de origem**.
- O relatório `.txt` **não é interpretado como auditoria independente** e não pode liberar a fonte.
- Qualquer lacuna M1 preserva `LAB_BLOCKED`, sem preenchimento. O leitor mantém o horário fixo EST do formato documentado.
- Mesmo um ZIP íntegro mantém `downloaded_source_authenticity_verified=false`, `market_data_product_license_verified=false`, `historical_point_in_time_eligible=false`, `trade_authorized=false`, `can_feed_live_radar=false`, `worker_enabled=false`, `scheduler_enabled=false`, `publishable=false`, `fx_bias=null`, `operational_bias=AGUARDAR`.

## Testes e evidências

Foram preparados **18 novos testes sintéticos de ZIP** para integridade, corrupção, tamanho, caminhos perigosos, arquivo extra, ausência de minuto, entrada duplicada, fuso/horários mantidos pelo leitor subordinado e persistência do bloqueio de operação. Junto aos 18 testes de M1 anteriores e outros contratos econômicos, a regressão local deve ser repetida antes da entrega no GitHub.

**Não foi arquivada uma captura real do HistData** nesta alteração. O próximo passo continua sendo verificar uma amostra real, sua data de publicação/disponibilidade e direitos de reutilização; o presente contrato é uma defesa contra arquivos não confiáveis, não um backtest ou viés comprovado. Preços Bid sem Ask/spread não bastam para estimar resultado executável.

**Ramo:** mesma Draft PR #1815, sem afetar a PR #1816. **LAB/HARD NO-GO:** sem merge, deploy, Render, Worker, cron, trades ou despesa adicional.
