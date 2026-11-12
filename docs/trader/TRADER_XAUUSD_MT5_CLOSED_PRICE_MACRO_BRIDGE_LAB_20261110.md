# AtlasQuant Trader — ponte de preço XAU/USD auditado para macro (LAB)

**Checkpoint: 10/11/2026. Apenas dados sintéticos; sem execução no MT5 real.**

## Lacuna fechada

O projeto já tinha: (1) coletor XAU/USD de 3.700 velas fechadas,
(2) auditor de arquivos locais SHA/CSV e (3) portão de prontidão de drivers
de ouro: juros reais dos EUA (`FRED_DFII10`), dólar amplo
(`FRED_DTWEXBGS`) e preço de ouro MT5.

A nova ponte `atlasquant_trader_xauusd_mt5_driver_join_lab.py` conecta
**o arquivo M15 auditado** ao terceiro driver sem permitir que um caller
substitua o preço por uma alegação de origem supostamente Pepperstone.

## Fluxo e proteções

1. Reexecuta `audit_xauusd_closedbar_archive_lab` e exige
   `LOCAL_XAUUSD_ARCHIVE_INTEGRITY_PASS_UNATTESTED` para **3.700 velas**.
   Reabre o CSV M15 com limite de descompressão e reconfere o hash, evitando
   mudança silenciosa do arquivo entre auditoria e consulta.
2. Extrai somente os **últimos dois fechamentos M15 consecutivos** do lote,
   com horário alegado de abertura em grade de 15 minutos. Rejeita a vela
   ainda aberta: abertura + 15 minutos deve ser anterior ou igual ao instante
   **alegado** de coleta.
3. Rejeita captura posterior à decisão, lote com mais de **1 hora** na
   decisão ou último fechamento com atraso de mais de **45 minutos** em
   relação à coleta. Não transforma lacunas de sessão em continuidade falsa.
4. Não arredonda números do preço com precisão incompatível com o formato
   decimal aceito pelo portão macro: bloqueia e pede tratamento explícito.
5. Cria exatamente **dois recibos alegados** `GoldDriverClaim` de preço
   com hash do CSV, horários de fechamento derivados e timestamp local de
   coleta, sem alegar autenticação da corretora ou disponibilização externa.
6. Aceita separadamente até quatro **alegações** macro dos outros dois drivers.
   Chama o portão existente de três drivers, inclusive suas verificações de
   release/capture antes da decisão; recusa a injeção de um recibo de ouro
   vindo do caller. Se as alegações estão completas, o estado continua
   `LAB_XAUUSD_PRICE_MACRO_CLAIMS_ONLY_NO_GO`.

### Critério de produto preservado

Não há compra, venda, probabilidade, viés operacional, sinal, score,
publicação, schedule, worker nem integração com o radar.
`broker_identity_authenticated=false`,
`historical_point_in_time_verified=false`,
`out_of_sample_gold_accuracy_validated=false`,
`operational_bias=AGUARDAR`, `trade_authorized=false`.

Mesmo um CSV e manifesto cujo hash bate pode ter sido reescrito antes da
auditoria, e os horários do terminal podem não estar autenticados.
Além disso, os quatro recibos macro sintéticos não são dados oficiais
capturados em tempo real. Essas lacunas **não** autorizam viés direcional.

## Verificação

- Novo `test_atlasquant_trader_xauusd_mt5_driver_join_lab.py`:
  **13/13 testes** (duas velas fechadas, macro ausente/completa apenas como
  alegação, ataque de preço injetado, arquivo ausente, vela aberta, timestamps
  não consecutivos, preço obsoleto, coleta posterior à decisão, macro futuro,
  precisão não arredondada e ausência de escritas).
- `python -m unittest discover -q -p 'test_atlasquant*.py'`:
  **362/362 testes locais aprovados**, sem Pepperstone, sem custos e sem ordens.

## Próximo P0 real

Quando o usuário voltar ao computador, executar o coletor com o MT5
Pepperstone autorizado, auditar separadamente o snapshot XAU/USD e inspecionar
apenas dados **reais** da corretora. Depois, buscar versões econômicas
pré-decisão autenticáveis, calendário e notícias geopolíticas; construir coorte
prospectiva e medir acerto fora da amostra. Até lá, nenhuma estimativa de
assertividade do ouro pode ser anunciada.
