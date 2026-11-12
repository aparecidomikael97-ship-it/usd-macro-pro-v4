# AtlasQuant Trader — CME SR3/ESR: disponibilidade real de ajustes (LAB, 10/11/2026)

**Estado:** controle temporal offline acrescentado ao piloto EUR/USD; **nenhuma cotação original de SR3/ESR foi coletada**, nenhum viés, probabilidade ou operação foi liberado.

## Fontes primárias / fatos verificáveis

- [CME — Access to Settlement Data FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html): preço de **ajuste exibido no site público** fica disponível **após a meia-noite do horário Central dos EUA (CT)**. Antes disso, dados por canais licenciados MDP / Google Pub/Sub / vendedores autorizados; DataMine oferece arquivos em canais específicos. Um campo de cotação sem canal de obtenção definido não comprova disponibilidade intradiária.
- [CME — Daily Bulletin](https://www.cmegroup.com/market-data/daily-bulletin.html): boletim **preliminar** por volta de **00:00 CT do próximo dia útil**; boletim **final** por volta de **10:00 CT do próximo dia útil**. A divulgação *aproximada* e o calendário de feriados não são prova de publicação de um relatório concreto.
- [CME — Globex Notice 13/11/2023](https://www.cmegroup.com/notices/electronic-trading/2023/11/20231113.html): desde janeiro/2024, antigas rotas FTP de liquidação foram descontinuadas; DataMine/site estão sujeitos a horários e termos. Arquivos após meia-noite gratuitos para consulta **não** equivalem automaticamente a permissão de coleta/republicação comercial.

## Correção realizada

- `atlasquant_trader_cme_settlement_release_gate_lab.py` **não** faz HTTP ou autenticação. Classifica como alegação plausível ou rejeita se um ajuste publico foi declarado **antes** da data mínima da fonte, considerando `America/Chicago` e DST. Canais: `CME_PUBLIC_WEBSITE_SETTLEMENT`, `CME_DAILY_BULLETIN_PRELIM`, `CME_DAILY_BULLETIN_FINAL`. **Não** supõe direito a feeds pagos.
- Para ser conservador, usa **próximo dia da semana (seg–sex)** como piso temporal de todos os canais, inclusive website. Em sexta-feira o piso cai na segunda; em situações em que um produto foi realmente divulgado antes, precisamos verificar o original: não liberar retroativamente. **Não é calendário oficial de pregão, não conhece feriados ou exceções.** Mesmo após o piso, dado permanece `NOT_AUTHENTICATED`.
- `atlasquant_trader_eurusd_sr3_esr_quarter_lab.py` agora exige `settlement_publication_channel` declarado para registros `quote_kind="SETTLEMENT"`. Rejeita preço de ajuste em horário impossível ou canal desconhecido. Cotação autodeclarada do tipo `TRADE` também **não** é autenticada pelo sistema.
- Testes sintéticos adicionais cobrem DST norte-americano, sexta–segunda, divulgação preliminar/final, relógios inválidos, dados divulgados depois do corte e bloqueio de ajuste antecipado.
- Resultado local: **31 testes de unidade aprovados** na soma das duas suítes SR3/ESR e da nova porta. **Isso testa regras, não dados de bolsa nem a performance de previsão.**

## Evidências que ainda faltam

1. Identificar arquivo/publicação CME de **SR3 e ESR no mesmo vencimento e dia de negociação** com volume de cada contrato e preço de ajuste da mesma revisão (preliminar/final), sem confundir número agregado por produto.
2. Obter bytes originais e horário de primeira captura comprovado, com SHA-256, origem e direitos de uso; distinguir `trade_date` (sessão da CME) de data UTC e hora do preço.
3. Provar que essas cotações realmente estavam públicas no instante relevante do backtest (point-in-time). Não inventar preços ou reconstruir o passado como se fosse visto naquele momento.
4. Definir transformação econômica e análise de basis: SOFR tem empréstimo garantido; €STR, não garantido; alinhamento trimestral não significa diferencial de política monetária nem direção garantida do EUR/USD.
5. Verificar autorização de redistribuição antes de disponibilizar dados para futuros clientes.

**Decisão:** continuamos no LAB; `AGUARDAR`, PR #1851 draft, sem atualização da interface, ordens, scheduler ou custo novo. Próximo marco: amostra legítima e pontual por contrato, se acessível sem gastos.