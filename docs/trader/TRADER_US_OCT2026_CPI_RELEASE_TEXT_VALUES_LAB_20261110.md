# AtlasQuant Trader — CPI EUA outubro/2026 divulgado, extração textual e vedações (10/11/2026)

**LAB / NÃO PUBLICADO / NENHUM SINAL / NENHUMA ORDEM / ZERO CONTRATAÇÃO.** Prioridade Trader: macro e viés seletivo para os 28 pares G8, índices e ouro (trilhas separadas).

## Evidência oficial pesquisada hoje

Página original do órgão emissor: [BLS — Consumer Price Index, October 2026, archive 10 Nov 2026](https://www.bls.gov/news.release/archives/cpi_11102026.htm), nota USDL-26-1685, com embargo até **10/11/2026 08h30 Eastern Time** (13h30 UTC, já em EST).

O texto da fonte informa:
- **CPI-U geral: +0,4% no mês (sazonalmente ajustado)**.
- **CPI de todos os itens exceto alimentos e energia: +0,3% no mês (sazonalmente ajustado)**.
- **Não há taxa anual válida do CPI-U geral para out/2026**, porque o BLS não coletou dados da pesquisa de out/2025 durante a interrupção de financiamento, e não publicou índices de out/2025 para a maioria das séries. Algumas subcategorias são exceções; não extrapolar.
- **Não confundir** +0,4% SA MoM, +0,2% NSA MoM e variação de 12 meses indisponível.
- A fonte oficial e o [calendário BLS de 2026](https://www.bls.gov/schedule/2026/) confirmam a data de divulgação. **A hora declarada de embargo não demonstra instante de captura original do primeiro byte.**

**Prova disponível nesta rodada:** consulta documental do texto público ao órgão emissor, sem cópia autenticada do HTML original nem testemunho independente da primeira divulgação. A tentativa direta de obter o arquivo bruto neste ambiente não foi bem-sucedida. Não anunciar hash de dados oficiais que não possuímos.

## Entrega de código

`atlasquant_trader_us_oct2026_cpi_release_text_guard_lab.py` + `test_atlasquant_trader_us_oct2026_cpi_release_text_guard_lab.py`.

O parser laboratorial somente recebe bytes HTML de um chamador, hash SHA-256 informado e horário de captura afirmado (sem acesso de rede próprio). Ele:
1. exige fonte URL exata, status HTTP 200, content-type HTML, período de divulgação plausível e captura anterior ao corte;
2. extrai do **texto fornecido** headline CPI-U mensal SA e núcleo mensal SA, recusando números duplicados ou trechos em scripts;
3. exige menção explícita de out/2025 faltante e da ausência de comparações anuais out/2026;
4. reconhece somente os **sete cruzamentos USD** para fins de cobertura, preservando 21 pares sem USD;
5. **não** transforma simples URL declarada/hash local em origem BLS autenticada; saída continua `operational_bias=AGUARDAR`, sem surpresa de consenso, score, precisão, trading ou publicação;
6. os testes são **13 casos sintéticos**, não reexecução de HTML real, preços de corretora ou backtest.

**Regressões previstas:** números duplicados ou fora de faixa; corpo alterado após hash; fonte/mime inválidos; captura anterior ao embargo ou após corte; ausência de informação oficial de índice anual; horário ingênuo; texto colocado somente em script; metadados que parecem BLS mas poderiam ter sido inventados.

## Juros: bloqueio de integração pago

A [CME esclarece](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/1892122625/CME%2BGroup%2BPublic%2BWebsite%2BDistribution%2BREST%2BAPI) que a API de snapshots de liquidações usa **OAuth, entitlement e licença de redistribuição específica**, enquanto a [CME DataMine](https://www.cmegroup.com/datamine/datamine-api.html) requer conta/API ID e direitos sobre os arquivos. O acesso manual a tabela pública não autoriza ingestão contínua nem redistribuição comercial. Contratos SR3 e ESR continuam em pesquisa sem inventar preços.

## Próximo P0

Realizar **captura de primeira mão** do HTML oficial numa máquina/navegador autorizado, registrar data/hora UTC real, status, cabeçalhos, SHA-256 e arquivo bruto em armazenamento privado; depois executar o parser **sobre esses bytes**, sem reconstituir o passado antes da captura. Separadamente, obter consenso MoM com fonte, data e janela **anteriores** ao evento, e medir previsão fora da amostra. Não calcular surpresa por subtração de uma manchete cujo momento de pesquisa não foi auditado. Sem isso, manter `AGUARDAR`.

### Status
Fonte pública identificada, números documentados, parser novo com validação sintética, sem prova de fonte bruta nem aumento de precisão. Flow v1.1 continua congelado.
