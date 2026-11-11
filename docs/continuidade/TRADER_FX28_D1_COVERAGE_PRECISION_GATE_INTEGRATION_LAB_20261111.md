# AtlasQuant Trader — cobertura D1 como 7ª barreira do motor de vieses (LAB, 11/11/2026)

## O problema

A PR #1851 já continha a auditoria `atlasquant_fx_d1_shared_calendar_gate_lab.py`, que reconhece ausência isolada e datas de cobertura parcial entre os 28 pares G8. Mas o `atlasquant_trader_precision_gate_orchestrator_lab.py` calculava um candidato com seis estágios sem consultar essa barreira. Portanto uma matriz D1/W1 sinteticamente coerente podia produzir um **candidato interno de pesquisa** mesmo se um instrumento D1 estivesse ausente no inventário daquele dia.

Isso não implicava operação real porque o orquestrador sempre retorna `AGUARDAR`. Era, porém, uma brecha de qualidade da **amostra do estudo**.

## Implementação

Adicionados ao `ResearchPacket` três campos: `d1_coverage_trading_date`, `d1_coverage_present_symbols` e `d1_coverage_observed_at_utc`. Por compatibilidade, os campos têm valores padrão `None`, mas sua ausência **bloqueia** o 7º estágio.

A função `inspect_fx_precision_orchestrator_lab` agora:
1. Exige que a data D1 declarada seja **anterior** à data UTC da decisão e não tenha mais de quatro dias de defasagem. Esse limite é um filtro conservador de pesquisa, **não** confirmação do horário de fechamento real da corretora.
2. Rejeita cobertura observada depois da decisão; exige carimbo com timezone e posterior ao início da data declarada.
3. Reexecuta a porta `inspect_d1_date_coverage_lab` sobre a lista de símbolos, em vez de aceitar um relatório de aprovação fornecido pelo chamador.
4. Só considera o 7º estágio estruturalmente aceito se os **28 símbolos** canônicos estiverem declarados presentes, sem repetição, omissões ou ativos extras.
5. Se o 7º estágio falha, `research_candidate_direction=null`, `state=LAB_PRECISION_ABSTAIN`, `operational_bias=AGUARDAR`.
6. Mesmo com os sete estágios sintéticos aprovados, o estado permanece `LAB_PRECISION_RESEARCH_CANDIDATE_UNATTESTED`: **nenhum sinal real ou probabilidade de sucesso é liberado**.

## Testes

A suíte do orquestrador foi atualizada para sete estágios e acrescentou cenários de:
- perda isolada do GBP/NZD (27/28), sem falsear a matriz completa;
- cobertura 0/28 ou parcial (8, 18 e 26 pares);
- data D1 ausente, atual, futura ou antiga;
- timestamp de cobertura posterior à decisão;
- duplicação ou troca do ativo por XAU/USD;
- caso 28/28 sintético sem confundir completude documental com prova de fonte.

## Evidências locais e limites

Em 11/11/2026, o AM12 reavaliou os 28 arquivos D1 e **14.000 candles**. Confirmou cinco datas com cobertura parcial ou ausente: 25/12/2024 (18/28), 01/01/2025 (8/28), 30/09/2025 (27/28, falta GBP/NZD), 25/12/2025 (0/28) e 01/01/2026 (0/28). Os arquivos e SHA-256 dos manifestos bateram, mas a hora de criação e o fornecedor dos preços **não foram autenticados independentemente**.

A nova proteção usa presença de símbolos declarada pelo chamador e não abre os arquivos por si só; **não confere a autenticidade dos preços**. A ligação com um leitor verificado e com hashes de fonte e horário real de barra ainda permanece pendente. O resultado de laboratório jamais se converte automaticamente em sinal de trade, atribuição causal, histórico point-in-time ou performance validada.

**Escopo:** 28 FX G8 D1/W1, LAB somente. XAU/USD e índices têm suas próprias regras e não são incluídos como 29º par. Sem merge, deploy, ordens, custo ou publicação.
