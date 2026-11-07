# AtlasQuant Trader — CPI AUD/NZD série/frequência, piloto LAB V2 — 07/11/2026

**Prioridade P0:** Macro das duas moedas para viés W1/D1. **Status:** módulo auxiliar ISOLADO, sem integração automática, código testado localmente; não habilita operação/Worker/deploy/alerta/cobrança.

## Por que foi necessário

No contrato G8 anterior, o CPI da Nova Zelândia é trimestral e foi corretamente colocado em quarentena para competências de 2027: o Stats NZ planeja acrescentar uma série mensal mantendo também a trimestral. O contrato V1 não tem identidade da série e não pode interpretar corretamente essa mudança.

A Austrália oferece CPI mensal completo e estatísticas trimestrais. Um CPI `AUD_MONTHLY` não deve ser apresentado como diretamente equivalente ao `NZD_QUARTERLY` apenas porque ambos medem inflação anual.

## Contrato separado V2

`atlasquant_cpi_series_contract_lab.py` tem catálogo de nomes **internos** (não códigos oficiais de série) e verifica:
- país AUD/NZD, identificador de série, frequência MONTHLY/QUARTERLY e competência;
- mês de encerramento de trimestre e vigência hipotética da série mensal NZD a partir de 2027;
- datas de publicação/captura/decisão com relógio UTC, sem look-ahead;
- idade da competência e idade do release com limites **experimentais**, sem validar que o calendário ocorreu;
- URL em domínio do órgão correspondente, forma do SHA e valor numérico finito, sem confundir URL/flags com autenticação;
- exigência das duas moedas, rejeição de chave extra e divergências entre país/frequência/série;
- classificação `LAB_CPI_FREQUENCY_MISMATCH` para AUD mensal × NZD trimestral; mesma frequência `LAB_CPI_SAME_FREQUENCY_UNATTESTED` **não garante comparabilidade metodológica** e não libera número econômico para score.

**Crucial:** o módulo V2 é um *companheiro* de pesquisa, NÃO remove quarentena V1 da PR #1847 nem opera por cima da auditoria G8. Não há dado real autenticado na execução dos testes nem score de direção.

## Prova e limites

- Executado localmente com Python 3.13: **19/19 testes unitários sintéticos PASS**, `py_compile` OK; comparação dos Git blob SHA dos dois arquivos testados com os salvos no GitHub: correspondem.
- Testes cobrem duas frequências, mistura inadequada, troca de moeda, trimestre inválido, série mensal NZD antes de 2027, revisão velha, capturas/releases futuros, schema, SHA e URLs inválidas, duplicação, dados não numéricos, falta de moeda e resposta sempre `AGUARDAR`.
- **Não é teste de acerto, autenticação de vintages, prova de histórico, demonstração de valor preditivo, nem cobertura de 28 pares**.
- A cobertura dos outros 27 pares e das séries monetárias permanece na fila P0; o catálogo desta versão piloto é exclusivamente AUD/NZD.

## Próxima implementação ordenada

1. Identificar e comprovar códigos reais de séries/definições, vintage e periodicidade por órgão; reconciliar ABS e Stats NZ, incluindo o início efetivo do CPI mensal NZD em 2027.
2. Adicionar metadados de série/frequência ao envelope G8 de forma versionada e compatível; não substituir o contrato anterior por uma suposição.
3. Completar macro bilateral (CPI e taxa de juros com natureza do instrumento/expectativas), depois medir W1/D1 por dados historicamente disponíveis e backtests walk-forward.
4. Somente quando a capacidade estiver calibrada, alimentar o seletor 0–10; mantêm-se microeconomia, geopolítica, nowcast de notícias e notícia × posição como camadas adicionais.

**Governança:** nenhuma alteração das três abas, dos planos de negócios/AION, da produção, de ordens ou do orçamento. Fonte: [Stats NZ CPI](https://www.stats.govt.nz/indicators/consumers-price-index-cpi/) e [ABS monthly CPI](https://www.abs.gov.au/about/our-organisation/corporate-reporting/abs-corporate-plan/2026-27/changes-forward-work-program); URLs indicativas, sem atestação histórica independente.
