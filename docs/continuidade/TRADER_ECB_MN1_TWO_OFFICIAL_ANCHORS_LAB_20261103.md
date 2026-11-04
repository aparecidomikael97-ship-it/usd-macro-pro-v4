# AtlasQuant Trader — dois pontos reais oficiais para MN1 (03/11/2026)

**Escopo: retrospectivo, informativo, sem sinal e sem previsões anteriores.**

O histórico BCE SDMX arquivado em 02/11 contém 6 datas, insuficientes para medir MN1. O download do CSV oficial de 01/09 a 02/11 ainda não pôde ser feito neste ambiente. Como alternativa DOCUMENTAL LIMITADA, reunimos dois dias oficiais separados por 32 dias:

- **01/10/2026**: referências reproduzidas do BCE pelo Diário Oficial da União Europeia em 02/10, C/2026/5148: https://eur-lex.europa.eu/eli/C/2026/5148/oj. Unidade: quantidade de moeda por 1 EUR; GBP está em **0,85373**, e não na apresentação resumida arredondada a 0,8537.
- **02/11/2026**: referências publicadas no Banque de France: https://www.banque-france.fr/en/statistics/rates-and-prices/exchange-rates-daily-parities-2026-11-02. As sete referências coincidem numericamente com o CSV BCE já versionado (SHA-256: 308439eb0230551fd7f80fa134a4c92829c81d8fcddaf94425bcb891c6e96038), sem provar captura anterior à data do arquivo.

Os 14 valores no JSON documental são TRANSCRIÇÕES de páginas oficiais, não os bytes completos da publicação de outubro. O módulo fixa as fontes, datas e os 14 números e calcula, apenas a posteriori, 28 retornos de referência em pontos-base para **MN1 após 32 dias**. Neutralidade em 5 pontos-base é política de laboratório, não limiar calibrado. Há sete referências EUR originais por data; os **21 pares sem EUR são cruzamentos algébricos, não cotações independentes**.

**Permite:** medir apenas o movimento ocorrido entre dois pontos de referência oficiais. **Não permite:** construir série diária de 32 dias, medir volatilidade/drawdown, confirmar dados spot executáveis, comparar com previsões emitidas em 01/10 (nenhuma foi emitida), provar disponibilidade ponto-no-tempo, desempenho OOS, probabilidade calibrada ou 90% de acerto. Verificação documental em 03/11 não é recibo independente com horário ou assinatura BCE.

O teste de integração confere o dia 02/11 contra os bytes do arquivo original BCE já salvo no repositório. A coleta completa permanece planejada no documento TRADER_ECB_G8_LONGER_HISTORY_CAPTURE_LAB_20261103.md.

**Governança:** PR #1803 permanece DRAFT/LAB/HARD NO-GO. Nenhuma chamada paga, API agendada, Render, UI, Worker, ordem, corretora, merge ou deploy.
