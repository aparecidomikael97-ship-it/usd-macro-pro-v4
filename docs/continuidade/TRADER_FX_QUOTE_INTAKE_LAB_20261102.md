# AtlasQuant Trader — Admissão estrutural de cotações dos 28 pares (LAB)

Data: 02/11/2026 · PR #1803 DRAFT · HARD NO-GO

## Continuidade após aprovação visual do proprietário

O proprietário avaliou, no AM12, a prévia do Trader com as quatro abas
**Início, Radar, Scanner Técnico e Painel Mestre** e confirmou "ficou bom".
Isso aprova apenas a **referência visual de LAB**, não o sistema
operacional nem deploy/merge. O visual V2 já passou 19/19 checks
e 15 testes locais de interface. Não modificar esse visual sem
motivo específico e nova conferência.

A próxima necessidade concreta é saber se a fonte de dados permitirá
calcular a força das oito moedas, os 28 pares e os três horizontes sem
dados futuros, ausência de pares ou resultados arbitrários.

## Novo contrato offline

Arquivo: \`atlasquant_trader_fx_quote_intake_lab.py\`.

A função \`audit_fx_quote_intake_lab(books, at=...)\` recebe **arquivos/
objetos candidatos não autenticados** para D1, W1 e MN1. São exigidos:
- 28 pares Forex canônicos em cada horizonte (84 registros de pares
  no conjunto de três janelas), com identificação uniforme da fonte;
- declaração \`LAB_UNVERIFIED_QUOTE_BOOK\`, modelo
  \`UNVERIFIED_FX_SPOT_CANDIDATE\` e tipo
  \`SPOT_MID_UNVERIFIED\`, nunca \`VALIDATED_DAILY\`;
- preço inicial/final numérico finito e positivo, timestamps de mercado
  com UTC explícito, timestamps de captura e instante de avaliação;
- mesmo início/fim de amostragem por horizonte; janelas temporais
  compatíveis com D1 / W1 / MN1 e período de fechamento coerente;
- captura dos 28 pares sincronizada em janela LAB de até 60 segundos;
- URL HTTPS sem credenciais/fragmento e recusa de porta inválida;
- consistência triangular do grafo de oito moedas e 28 pares
  (resíduo no máximo 15 bps, limiar experimental não calibrado).

O relatório indica separadamente **a causa da recusa em cada horizonte**
e recusa silenciosamente a promoção de cotação suspeita. O resultado
\`LAB_THREE_HORIZONS_STRUCTURALLY_COMPLETE_UNTRUSTED\` significa
**somente formato/tempo/consistência interna**, não que a fonte seja
verdadeira, licenciada ou historicamente disponível naquela hora.

**Invariantes:** \`actual_currency_strength=null\`,
\`real_bias_28_pairs=null\`, \`daily_ui_contract=null\`,
\`can_feed_live_radar=false\`, \`can_feed_real_oos=false\`,
\`market_quotes_verified=false\`, \`trade_authorized=false\`,
\`worker_enabled=false\`, \`scheduler_enabled=false\`.
Mesmo três livros estruturalmente consistentes não são sinal real
nem prova de previsão. O contrato \`VALIDATED_DAILY\` do Radar
não é construído a partir desses dados.

## Testes realizados

\`test_atlasquant_trader_fx_quote_intake_lab.py\` traz **26 testes**
de laboratório: 28 pares/8 moedas/3 horizontes, falta de D1/W1/MN1,
par ausente/extra, fonte/URL inconsistente, URL com porta malformada,
datas ingênuas ou futuras, preço não numérico, captura antes do
evento, defasagem entre pares, corte temporal, incompatibilidade
triangular, período D1/W1/MN1 errado, campos de futuro indevidos
e impossibilidade de emitir viés/ordem/sinal real.

Na pasta TEMP isolada do AM12, os **26 testes novos mais
15 testes locais anteriores de interface** passaram (41/41).
O erro preliminar do teste de URL com porta inválida foi
corrigido antes do commit. Suíte completa de CI no GitHub
deve ser conferida na nova revisão.

## Próximos portões

1. Identificar fornecedor de dados FX com 28 pares, horário de
   captura, definição MID/BID/ASK, janelas e pares cruzados.
2. Revisar termos de uso, custos e histórico licenciável,
   **sem contratar serviços sem autorização**.
3. Obter amostras confiáveis com recibos independentes e
   provar que existiam antes do horário das previsões.
4. Somente então pesquisar calibração de força/viés D1 com
   confirmação W1/contexto MN1 em OOS, sem vazamento de futuro.
5. Ligar leitura ao Radar apenas após segurança e homologação
   dos bloqueios gerais do AION/AtlasQuant.

Nenhuma API consultada, Worker ativado, cron, merge, deploy,
trade, aprovação de OOS real ou despesa adicional.
HARD NO-GO segue vigente.
