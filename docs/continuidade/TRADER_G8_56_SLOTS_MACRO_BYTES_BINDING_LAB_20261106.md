# AtlasQuant Trader — vínculo dos 56 slots D1/W1 às evidências originais (LAB)

Data: 2026-11-06. Este trabalho amplia o protocolo prospectivo dos **28 pares
G8 × horizontes D1 e W1**, sem criar previsões, sem fontes inventadas e sem
ligar o Radar, Worker, coleta automática ou ordens.

## Lacuna corrigida

O validador de claims existente exige que uma entrada direcional traga
`evidence_sha256` (64 caracteres hexadecimais). Até esta revisão, ele apenas
testava o formato e a cronologia declarada: **qualquer hash sintaticamente
válido podia ser informado sem entregar seus dados macro correspondentes**.

O novo `atlasquant_trader_fx_g8_claims_macro_binding_lab.py` adiciona a etapa
de vínculo com o conteúdo original fornecido pelo pesquisador. Recebe:

1. O manifesto canônico de 56 slots, fixo e não editável.
2. O ledger de entradas ALTA/BAIXA/NEUTRO/AGUARDAR ligado ao SHA-256 do
   manifesto e já examinado por `inspect_g8_cohort_claims_lab`.
3. Um dicionário de **bytes JSON originais** de macro por `slot_id`, exigido
   para toda entrada ALTA, BAIXA ou NEUTRO; não é exigido para AGUARDAR.
4. Um horário de inspeção declarado, com fuso UTC verificável na estrutura.

Para cada entrada que precisa de dados, o validador verifica:

- SHA-256 recalculado dos bytes **idêntico** ao hash declarado no ledger;
- par canônico da evidência idêntico ao par do slot, com indicadores piloto
  **CPI_YOY** e **POLICY_RATE** para ambas as moedas, sem fontes estranhas;
- horário da decisão macro igual à criação declarada da previsão;
- data de publicação e coleta de **todos** os registros, inclusive os antigos
  não escolhidos, até o `data_cutoff_utc` da entrada;
- ausência de indicadores ausentes ou vencidos segundo a regra de frescor do
  validador macro já existente; JSON estrito, sem duplicações e sem NaN;
- vínculo somente para os slots declarados, sem evidência extra, ausente ou
  com tipo incorreto; limite total de entrada de 1 MB.

O resultado contém SHA-256 dos bytes do manifesto, do ledger e um digest
determinístico das associações `slot_id:hash`. Nenhum desses hashes sozinho
serve de prova de horário, origem oficial, licença, preço ou acerto.

## Separação explícita dos resultados

| Caso | Resultado de laboratório | Efeito no viés real |
|---|---|---|
| Entrada direcional com bytes coerentes | `LAB_SUBMITTED_CLAIMS_MACRO_BYTES_BOUND_UNATTESTED` | Nenhum |
| 56 entradas AGUARDAR, sem dados | `LAB_ONLY_ABSTENTIONS_NO_MACRO_EVIDENCE_NEEDED` | Nenhum |
| Bytes alterados, omitidos, fora de prazo ou de outro par | `LAB_BLOCKED` | Nenhum |
| Dados preenchidos só depois da janela | Mesmo que coerentes, **sem testemunha prospectiva externa** | Nenhum |

**Não são produzidos:** direção operacional, probabilidade calibrada, ranking
real de moedas, previsão executável ou histórico de acertos. Toda saída mantém
`fx_bias=null`, `validated_prediction_count=0`, `validated_accuracy=null`,
`operational_bias=AGUARDAR`, `trade_authorized=false`,
`can_feed_live_radar=false`, `publishable=false`,
`worker_enabled=false`, `scheduler_enabled=false`, custo novo `R$0`.

## Próximas comprovações obrigatórias

1. Evidência **externa e independente** de que o registro dos 56 slots, as
   previsões (se existirem) e a versão do modelo estavam congelados **antes**
   do horário-limite do estudo de 08/11, com recebimento atestado.
2. Prova da publicação original e da versão histórica de cada estatística
   econômica, pois o JSON ainda contém horários/origens **declarados pelo
   próprio pesquisador**, sem autenticação do órgão emissor.
3. Dados históricos independentes de preços de mercado e convenção temporal
   confiável para D1/W1, avaliando **todas** as posições de estudo, incluindo
   abstenções e resultados ausentes. Sem seleção posterior de vencedores.
4. Avaliação prospectiva, fora da amostra, do modelo macro — ainda experimental
   e sem calibração — antes de qualquer alegação de 80–90% de acerto.

Os testes desta etapa usam apenas entradas **sintéticas**. Nenhuma previsão
real foi criada ou registrada. A política permanece **GO-LAB condicional /
HARD NO-GO para operação real**.
