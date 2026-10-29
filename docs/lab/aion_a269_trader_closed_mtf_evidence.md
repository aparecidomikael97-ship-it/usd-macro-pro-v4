# A269 — Admissão conservadora de evidência por timeframe no AION Trader

**Status:** PR LAB draft, SEM merge, Worker, deploy, corretora, alertas, ordens ou custos. P0 0/6 homologadas; HARD NO-GO, UNCERTAIN=ZERO_AUTO_RESEND.

## Continuidade A268 → A269

A268 já criava leitura dos 28 pares FX e admitia M15 exclusivamente de cache residente validado. Todos os outros períodos eram `NO_SEPARATE_TIMEFRAME_EVIDENCE`. A269 adiciona o módulo puro `atlasquant_aion_trader_timeframes.py`, integrado por argumento opcional `timeframe_evidence` na função `trader_readonly_observation()` e na hidratação residente. A ausência do argumento mantém **exatamente o comportamento anterior**. Nenhum novo feed é coletado.

**Contrato do insumo suplementar:** dicionário `{par: {timeframe: registro}}` com par canônico dos 28 FX, timeframe exatamente `M5/M15/M30/H1/H4/D1`; cada registro exige `timeframe` correspondente, `source="ATLASQUANT_OFFLINE_CLOSED_CANDLE_INPUT_V1"`, `closed_candles=True`, `fetched_at` aware e lista de 2–240 candles fechados, com `closed_at`, open/high/low/close positivos e finitos. Os horários precisam estar ordenados, separados por **ao menos a duração declarada do TF**, nunca futuros e nunca posteriores ao `fetched_at`. Rejeita duplicação, aliases FX repetidos, flags extras de suposta verificação, fontes divergentes, preços inválidos, bool, NaN e TF inventado. **Não reamostra nem infere candles de um período a outro.**

**Política de frescor de último candle fechado:** M5 <20min, M15 <70min, M30 <100min, H1 <180min, H4 <600min, D1 <3000min. O `fetched_at` também deve obedecer a essa janela. Se velho, classifica como histórico. Fechamento de mercado pode deixar todo o quadro em histórico; não inventa sinal atual. Um carimbo informado pelo host é apenas metadado, não certificação de feed.

**Uma distinção crucial:** todas as entradas suplementares aceitas são rotuladas `INPUT_FRESH_CLOSED_<TF>_UNATTESTED`. O contador `mtf_coverage` representa **somente a estrutura e atualidade alegadas pelo insumo**, com `mtf_coverage_is_external_attestation=False`. **Não** eleva `fresh_m15_pairs` ou `all_28_fresh_closed_m15` apenas porque alguém trouxe 28 séries M15 supostamente recentes. Esses campos preservam a validação de cache residente da A268. Se o insumo M15 contradizer o último close já validado no residente, retorna `CONFLICT_WITH_RESIDENT_M15_BLOCKED` e reduz a cobertura. Informação suplementar M15 velha ou inválida não faz fallback silencioso ao M15 residente daquele par. Demais TFs são independentes.

**Regra geral:** `no_orders=True`, `no_alerts=True`, `authorizes_order=False`, `external_actions_enabled=False`, P0 zero. Força de moedas permanece só contexto não comprovado por provedor. Não gera OB/FVG/BOS/CHOCH, direções de trade nem sinais de reversão — a A269 só habilita leitura separada e auditável de dados para análise futura. UI do cockpit permanece sem nova tela específica.

## Testes

25 ensaios novos de LAB: compatibilidade exata sem argumento MTF, seis TFs com candles próprios, ausência/contradição/atraso, 28 séries fornecidas sem inflar `28/28`, M15 comparado ao residente, intervalos inválidos, timestamps futuro/naive, OHLC malformado, aliases duplicados, fonte desconhecida, DXY separado, pacote raiz malformado, integração de hidratação e limpeza em refresh inválido, ausência de mutação de input e ausência de clientes de broker/rede.

CI separada Ubuntu/Windows inclui A269, A268, Guardião de Risco, Registry/Capabilities, testes `pytest` de Resident/Scanner FX28. Toda bateria é sintética e somente leitura. **Resultados devem ser conferidos no HEAD final, não presumidos por CI anterior.**

**Dependências externas abertas:** nenhuma fonte independente de mercado foi autenticada; marcação `closed_candles=True` ainda é declarada pelo chamador. Proteção administrativa da main A264 não está aplicada; Render não exige os gates de build A260–A262; todas as seis P0 seguem pendentes. Trader prioritário, Investimentos scaffold, Negócios congelada nesta visão (não é congelamento global operacional).
