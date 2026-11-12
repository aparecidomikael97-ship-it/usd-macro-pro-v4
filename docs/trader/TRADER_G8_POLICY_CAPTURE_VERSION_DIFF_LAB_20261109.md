# AtlasQuant Trader — diferenças entre capturas locais de documentos de política G8 (LAB)

Data de referência: 09/11/2026 (Cuiabá). Escopo: pesquisa, **sem** negociação, automação ou publicação.

## Lacuna e correção

O recibo local da cadeia de custódia já vinculava cada captura pelo `record_sha256` e verificava bytes por `body_sha256`. Porém, uma segunda captura idêntica recebe **outro hash de recibo** (nova hora, sequência e elo), o que não significa que o documento tenha mudado. Também seria incorreto afirmar que qualquer mudança nos bytes prova uma *revisão publicada pelo banco central*: o servidor pode alterar formatação, cookies, HTML dinâmico e respostas intermediárias.

`atlasquant_trader_g8_issuer_custody_chain_lab.py` agora devolve, apenas após validar integralmente os elos, quatro métricas locais:

- `distinct_body_hashes_local`: quantidade de valores SHA-256 distintos de corpos **apresentados pelo chamador**.
- `body_change_transitions_local`: quantidade de passagens consecutivas de um hash de corpo para outro.
- `identical_recaptures_local`: número de capturas consecutivas com o mesmo hash de corpo.
- `last_body_sha256_local`: hash do corpo informado na última captura validada.

Exemplo estritamente sintético, cadeia de bytes `A → A → B → A`: quatro recibos, dois corpos distintos, duas transições de bytes e uma recaptura idêntica. Isso **não** comprova duas versões editoriais nem revisões de conteúdo econômico; só distingue snapshots locais. Uma cadeia invalidada continua com contadores zerados, estado bloqueado e `AGUARDAR`.

## Restrições e segurança

- `original_publisher_revision_attested=False` em **todos** os resultados. Hashes locais e carimbos informados pelo chamador não autenticam domínio, TLS, data efetiva de divulgação, momento da primeira publicação nem versões históricas do emissor.
- Os campos de status HTTP e datas de coleta são alegações do chamador, não resultados de acesso à rede. Nenhum documento oficial foi baixado por este código.
- Uma mudança bruta de bytes pode ser layout, mídia ou conteúdo dinâmico, não surpresa do BC; futuro reconhecimento de revisão econômica exigirá extração semântica, comparação de campos relevantes e prova independente da origem/publicação.
- Nenhum resultado alimenta o viés macro D1/W1, a matriz 28 pares, score de probabilidade, entrada MT5 ou sinal operacional. Todos permanecem `operational_bias=AGUARDAR`, `historical_point_in_time_eligible=False`, `trade_authorized=False`.
- Sem consulta de conta ou ordens, alteração do MT5, deploy, merge, worker, agendamento, compra de serviço ou gastos.

## Validação local

- `python -m unittest -v test_atlasquant_trader_g8_issuer_custody_chain_lab`: **14/14 PASS**.
- `python -m unittest -q test_atlasquant_trader_g8_issuer_custody_chain_lab test_atlasquant_trader_g8_macro_asof_lab test_atlasquant_trader_g8_macro_matrix_pit_lab test_atlasquant_trader_g8_event_relevance_lab`: **85/85 PASS**.
- Testes novos: recaptura idêntica; retorno ao corpo anterior (A → B → A); mistura de recaptura e alteração; manutenção dos vetos de origem/revisão e viés. Todos **sintéticos** nesta rodada, sem validação pelo AM12 ou pelo GitHub Actions.

Próximo bloqueio P0: prova independente de captura/publicação original e períodos observacionais dos indicadores por emissor, com registros históricos auditáveis anteriores ao instante de decisão. Até lá, abstenção.
