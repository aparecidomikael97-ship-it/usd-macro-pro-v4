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
