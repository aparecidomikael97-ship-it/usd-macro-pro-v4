# AtlasQuant Flow PRO v1.1 — checkpoint de arquivamento, sem execução
Data do registro: 2026-11-10. Estado: **RESERVADO / NÃO VALIDADO / NÃO PUBLICADO**.

A pedido do proprietário, o desenvolvimento do **Flow** fica estacionado até o AtlasQuant Trader ter fontes e vieses sólidos. Não começar trabalho de integração, backtest ou publicação automaticamente.

## Fonte preservada
- **Arquivo integral** guardado na Biblioteca pessoal do projeto, caminho: `/AtlasQuant/Flow/AtlasQuant_Flow_PRO_v1_1_LAB_20261110.pine`.
- SHA-256 do código exato arquivado: `315036fe40e252a3327de8cb88790ac99aa9fee6ad7a464c642c35970ce06ad1`.
- Tamanho: **18.765 bytes; 296 linhas**; Pine Script v6, protótipo de pesquisa EURUSD M15.
- Este documento é apenas um ponteiro/checkpoint; **não contém uma segunda cópia do fonte**. A Biblioteca pessoal preserva a cópia completa.
- Documento de arquitetura: `docs/trader/ATLASQUANT_FLOW_COT_PLANO_20261110.md`.

## Arquitetura congelada
- Início seletivo de expansão (OBSERVAR) separado de continuação confirmada.
- Detectar preço esticado e bloqueio de entradas atrasadas: ADR do dia, ATR por pernada, EMA/VWAP, pivôs, espaço e R:R.
- Direção macro do Trader independente do gatilho técnico; ausência de macro autenticada não pode ser apresentada como confirmação.
- Contexto COT semanal opcional, respeitando publicação, símbolo do contrato e diferença entre posições de terça e divulgação de sexta; COT não autoriza sinais M15.
- Depois de validar no TradingView, estudar versão MT5 separada e integração segura; nenhum webhook/robô instalado nesta fase.
- **Não confundir marca técnica no gráfico com recomendação de negócio.**

## Antes de retomar
1. Abrir fonte original e confirmar SHA-256 e versão da `LibraryCOT` contra manual/compilador atuais.
2. Compilar Pine v6 no TradingView; corrigir erros reais, não declarar compilação sem prova.
3. Auditar HTF sem repaint, datas de publicação do COT, reset da amplitude diária por sessão, valor de pivôs e cálculo realista de custos.
4. Testar início/continuação separadamente em dados fora da amostra com sinais raros, payoff, drawdown, cobertura/abstenção e baseline.
5. **NÃO** ativar ordens, sincronização com corretora, publicar, integrar ao Radar nem gastar sem nova decisão expressa.

Prioridade operacional vigente: **AtlasQuant Trader G8/28 FX, XAUUSD/índices, vieses D1/W1 e qualidade das fontes macro**.
