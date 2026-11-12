# AtlasQuant Trader — checagem prévia do PPI 13/11: AM12, fontes e 7 FX (LAB)

**Data de preparação:** 11/11/2026 em Mato Grosso. **PPI de outubro dos EUA:** 13/11/2026, 13h30 UTC / 09h30 MT. A janela de reação H4 só estará completamente fechada às **17h30 UTC / 13h30 MT**.

## Motivo

O estudo PPI já exige 17 velas M15 para cada um dos sete pares USD: EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF e USDCAD. O capturador `atlasquant_trader_ppi_mt5_m15_capture_lab.py` **não** torna símbolos visíveis automaticamente, e a última verificação do AM12 encontrou somente quatro desses sete pares exibidos; NZDUSD, USDCHF e USDCAD estavam ocultos.

Antes do evento, faltava uma checagem única que diferenciasse **prontidão documental**, **exibição dos símbolos** e **autorização/possibilidade de usar históricos futuros**.

## Novo módulo de preparação somente leitura

`atlasquant_trader_ppi_preflight_lab.py`:

1. Confere um relógio UTC declarado; separa fase pré-divulgação, pós-divulgação antes de fechar H4 e fase após 17h30 UTC. Essa fase **não** presume que os dados tenham sido publicados ou entregues pela corretora.
2. Reexecuta o protocolo congelado `ABSTAIN`. Nenhuma previsão direcional do PPI deste estudo foi registrada; reação posterior não vira acerto de modelo.
3. Recalcula os SHA-256 dos **dois arquivos originais TD Economics/Trading Economics**, contra hashes congelados, sem baixar novos dados ou substituir o consenso.
4. Reabre o manifesto das **três agendas oficiais parciais EIA, Fed Board e SF Fed**, conferindo seus corpos HTML, hashes fixados e horários de captura. Não declara que a janela foi livre de outras notícias. BLS permanece sem página salva nesse manifesto.
5. Conecta-se ao **terminal MT5 já autorizado** com `initialize`, `terminal_info`, `symbol_info` dos sete pares e `shutdown`, sem `symbol_select`, `copy_rates`, `tick`, `account_info`, `positions_get` ou `order_send`. Não lê dados pessoais ou de conta.
6. Emite exatamente os pares visíveis, ocultos ou com identificação/precisão incompleta. Se faltar alguma peça, falha de forma explícita. Se tudo estiver documentalmente coerente, diz apenas **pronto para futura captura manual sob restrições**, não GO operacional.

**Comportamento garantido:** `operational_bias=AGUARDAR`, `m15_candles_read=0`, `trade_authorized=false`, `publishable=false`, `new_cost_brl=0`. Não instala componentes nem executa agendamentos.

## Testes e limites

O arquivo `test_atlasquant_trader_ppi_preflight_lab.py` usa um MT5 completamente falso e verifica cobertura 7/7, três símbolos ocultos, base/cotada inválidas, alteração de HTML, falta de agenda oficial, falha de terminal, relógios ausentes/sem timezone, fases de espera, symlink e microssegundos de captura. A CI executa em Python 3.11/3.12. **Teste de código não mede assertividade real.**

A verificação não certifica a Pepperstone, o servidor de cotações, a disponibilidade point-in-time, o calendário completo, nem a causalidade de uma reação. A implantação do próprio módulo continua limitada ao LAB/PR rascunho. A coleta dos 17 candles após o evento **continua manual, opt-in e condicionada** às quatro horas totalmente fechadas e à presença dos sete símbolos.

## Procedimento local sem mudar o MT5 automaticamente

Quando os três pares permanecerem ocultos: abrir Observação do Mercado com `Ctrl+M`, botão direito, `Mostrar Tudo`. Isso altera apenas a exibição da lista e **não envia ordens**. O usuário pode fazer a alteração manualmente; o preflight nunca a faz.

**Nenhum merge, publicação, operação real, histórico futuro fabricado ou custo adicional.**

## Resultado do teste com fontes reais no AM12

Executado diretamente no terminal Pepperstone MetaTrader 5 com Python 3.12 isolado, sem acesso a conta, tick ou candles.

A primeira execução bloqueou cedo porque o limite artificial de HTML era 750 KB, enquanto o arquivo **Trading Economics congelado** possui **1.401.914 bytes**. Os dois hashes originais continuavam exatamente iguais aos documentos previamente arquivados. A correção elevou o limite a **2.000.000 bytes**, mantendo teto e conferência SHA; dois testes sintéticos cobrem HTML de ~1,4 MB e excesso de 2 MB.

Nova execução local real:
- Protocolo pré-evento `ABSTAIN`: válido documentalmente;
- TD e Trading Economics: **2/2 hashes válidos**;
- EIA, Fed Board, SF Fed: **3/3 arquivos oficiais originais válidos**, mas agenda incompleta do mercado;
- MetaTrader 5: conectado e **7/7 símbolos com metadados coerentes**;
- **EURUSD, GBPUSD, AUDUSD, USDJPY visíveis**;
- **NZDUSD, USDCHF, USDCAD ocultos**;
- Estado `LAB_PPI_PREFLIGHT_VISIBILITY_OR_SPEC_INCOMPLETE_NO_GO`;
- Zero candles e ticks lidos, zero operações e contas consultadas, nenhum símbolo selecionado automaticamente.

O problema está apenas na exibição dos três símbolos para o fluxo de captura estritamente local; isso **não** autentica o feed ou garante a futura disponibilidade das 17 barras M15. O usuário deverá usar manualmente `Ctrl+M` → Observação do Mercado → Mostrar Tudo, e depois repetir o preflight quando desejar.

A alteração ainda não permite a captura antes de 13/11/2026 às 17h30 UTC (13h30 MT), nem cria qualquer previsão ou resultado do PPI antes da publicação oficial.
