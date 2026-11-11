# AtlasQuant Trader — ligação macro G8 ao Precision Gate com custódia local de bytes — 11/11/2026

**GO-LAB / NÃO é previsão real, não é feed oficial, não é certificação de fontes, não é backtest e não autoriza sinais, pagamentos, operações ou deploy.** Branch `lab/trader-mt5-28fx-live-coverage-20261107`, PR #1851 em rascunho.

## Por que esta etapa importa

Antes, a matriz de 28 pares validava campos declarados de CPI/juros por moeda e horizonte, enquanto os seis filtros do Precision Gate tratavam uma hipótese sintética e fontes declaradas pelo chamador. Faltava uma **ligação executável de entrada** que verificasse os **mesmos oito grupos de recibos macro em D1 e W1**, exigisse ao menos os bytes locais referidos pelos hashes dos documentos, e impedisse que uma hipótese "aprovada" pelos outros filtros pulasse as fontes faltantes.

## Código novo e interfaces existentes reutilizadas

- `atlasquant_trader_fx_macro_precision_byte_join_lab.py`
- `test_atlasquant_trader_fx_macro_precision_byte_join_lab.py`
- Reutiliza **de verdade** `inspect_g8_macro_matrix_pit_lab` para `D1` e `W1`, ambos sobre o mesmo conjunto de documentos, com cortes distintos e usando o relógio de avaliação da hipótese. Não refaz o cálculo em paralelo para aceitar dados futuros silenciosamente.
- Reexecuta `inspect_fx_precision_orchestrator_lab`, com todos os **seis** controles: coerência D1/W1, fatores compartilhados D1, fatores compartilhados W1, regime, M15 custo/extensão e política seletiva de notícia/histórico.
- Entrada de custódia: `receipts_by_currency` e `original_source_bytes_by_currency`, ambos com **oito moedas exatas**; por moeda, CPI_YOY e POLICY_RATE. Compara `sha256(bytes)` com `record.source_sha256` e aplica limites de tamanho. Não persiste nem exporta arquivos.
- **Uma vintage por moeda e indicador nesta versão:** quando FLASH, FINAL e revisão coexistirem, o chamador precisará selecionar e guardar corretamente a vintage disponível em cada corte. A rotina **não inventa** uma solução para duplicidades.
- **Nunca inferir que o número digitado no recibo foi extraído do documento:** hash coincide com os bytes fornecidos, mas isso **não autentica publicador, validade HTTP/TLS, relógio de captura, página da primeira publicação, interpretação semântica de CPI e instrumentos de juros, ou permissão de redistribuição comercial.**
- Retém o censo de **todos os 28 pares**, não só os pares mais convenientes. Se um arquivo de EUR falta, os **sete pares EUR** ficam `LAB_PAIR_MACRO_WAIT_EVIDENCE`; os outros 21 não são bloqueados por esse motivo isolado.
- Uma fonte que chegou depois do corte `W1` mas antes de `D1` é aceita **somente como metadado diário**, não pode retroagir ao semanal.
- Se uma hipótese passar os seis filtros **e** todos os metadados dos dois cortes e arquivos da moeda-base/cotada forem íntegros, retorna SOMENTE `LAB_BYTES_BOUND_MACRO_PRECISION_RESEARCH_CANDIDATE_UNATTESTED`. Ainda `operational_bias=AGUARDAR`, `trade_authorized=false`, `publishable=false`, `calibrated_probability=null`.
- Sem candle oficial, sem bid/ask executável, sem comparação econômica efetiva, sem porcentagem de acerto, sem conexão MT5, sem chamada HTTP/worker, sem custos.

## Validação

**18 testes unitários integrados e sintéticos** (exercícios de lógica, não indicadores macro verdadeiros):
1. 16 blobs fictícios com hashes correspondentes e cobertura integral: 8 moedas/28 pares, D1/W1, seis filtros estruturais — **ainda NO-GO**.
2. Nenhum arquivo original: zero par com custódia, todos `AGUARDAR`.
3. Ausência de arquivo EUR: exatamente sete cruzamentos dependentes bloqueados, outros 21 têm os hashes disponíveis.
4. Alterar um byte do arquivo USD rejeita sete pares USD.
5. Hash igual não comprova o número CPI declarado.
6. Recibo CPI EUR faltante bloqueia sete pares.
7. Informação USD recebida entre os cortes W1 e D1 não entra no W1.
8. Publicação EUR posterior a ambos os cortes bloqueia sete.
9. Vintages duplicadas e não resolvidas bloqueiam a matriz.
10. Spread ruim reprova mesmo com documentos íntegros.
11. Direção contraditória à matriz reprova.
12. Blackout de notícia importante reprova.
13. Relógio ingênuo/antes da decisão reprova.
14. Moeda ausente no envelope bloqueia todo o censo.
15. Fonte extra inesperada bloqueia.
16. Arquivo original superior a limite bloqueia.
17. String no lugar de bytes originais bloqueia.
18. Arquivo CHF de juros faltante bloqueia sete.

**Validação do GitHub:** `.github/workflows/atlasquant-trader-d1w1-offline-lab.yml`, com testes reais de integração **Python 3.11 e 3.12**. Nenhum documento real de terceiro foi publicado como fixture.

## Prioridade seguinte: evidência REAL, sem enganar o sistema

1. Usar capturas reais originais, licenciadas, com origem/hora e integridade verificadas; registrar a vintage que o sistema realmente possuía em cada corte. Não preencher lacunas com versões baixadas depois.
2. Criar **extractors de CPI/juros** por emissor, checando unidade (YoY/MoM), período, série, revisão e método. **Até isso existir, documentos com hashes corretos continuam insuficientes para gerar uma pontuação macro bilateral.**
3. Para dois países, verificar comparabilidade de preços/juros, expectativas relativas e contexto de política monetária; inflação alta isolada não determina direção da moeda.
4. Comparar, num ensaio prospectivo, **macro baseline vs Precision Gate completo**, com saídas `AGUARDAR`, custo, cobertura e desempenho fora da amostra. Somente depois calibrar probabilidade.
5. A preparação para PPI de 13/11 é um ensaio já agendado; preservadas duas capturas de consenso pré-evento e janela de reação dos sete pares com USD. Não duplicar tarefas.
6. XAUUSD, índices EUA, WIN e WDO precisam de modelos próprios; a camada G8/28 não é prova para esses ativos.

**Estado:** GO-LAB, NO-GO publicação/integração operacional, HARD NO-GO operação real. Sem novos gastos.
