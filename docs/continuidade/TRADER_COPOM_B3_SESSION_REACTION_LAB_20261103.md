# AtlasQuant Trader — reação pós-Copom com janelas reais de sessão B3 (LAB 03/11/2026)

**Descoberta prática com fonte primária B3:** o Copom divulga o comunicado da reunião de 04/11/2026 **a partir das 18h30 horário de Brasília**, sem garantir que seja exatamente às 18h30. O Ofício Circular B3 **050/2026-VNC, de 13/10/2026**, Anexo 1 com grade válida desde 03/11/2026, informa negociação regular de **WIN das 09h às 18h25** e de **WDO das 09h às 18h30**. Fontes:
- B3: https://www.b3.com.br/data/files/99/B7/82/67/8A631A103BBB511AAC094EA8/OC%20050-2026-VNC%20NOVOS%20HORARIOS%20DE%20NEGOCIACAO_PT.pdf
- B3 horário WDO: https://www.b3.com.br/pt_br/solucoes/plataformas/puma-trading-system/para-participantes-e-traders/horario-de-negociacao/derivativos/cambio-e-dolar-pronto/
- B3 horário WIN: https://www.b3.com.br/pt_br/solucoes/plataformas/puma-trading-system/para-participantes-e-traders/horario-de-negociacao/derivativos/indices/
- BCB (normativo divulgado em fonte oficial): https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Comunicado&numero=43383

## Regra de janela em 04/11/2026

| Ativo | Último limite de negociação regular em Brasília | Limite UTC | Primeira sessão REGULAR POSTERIOR, somente candidata |
|---|---:|---:|---|
| WIN (FUT WIN) | 18:25 | 21:25 UTC, 04/11 | 05/11 às 09:00 BRT (12:00 UTC), sujeito a calendário/exceções |
| WDO (FUT WDO) | 18:30 | 21:30 UTC, 04/11 | 05/11 às 09:00 BRT (12:00 UTC), sujeito a calendário/exceções |

O fechamento regular **não é sinônimo** do preço de ajuste, liquidação ou do último tick. Não usar preços de ajuste como se fossem preços executáveis às 18h25/18h30. O horário de 09:00 em 05/11 é uma **janela candidata baseada na grade regular**, não prova de que houve sessão, negócio, liquidez ou preço nesse minuto. O código registra `b3_holiday_and_exception_calendar_verified=false` e `next_business_session_guaranteed=false`. No vencimento, o horário do contrato vencendo pode ser diferente; verificar o vencimento e o boletim B3 antes de qualquer comparação efetiva.

**Erro de backtest evitado:** se a notícia só puder ser publicada a partir de 18h30 e o WIN já fechou às 18h25, não existe reação regular do WIN *após a notícia no mesmo dia*. O WDO termina às 18h30, de modo que a notícia não deve ser presumida conhecida antes do encerramento. Registrar a primeira observação elegível na sessão regular seguinte, e não usar vela pré-notícia como preço pós-notícia.

## Contrato de LAB

`atlasquant_trader_copom_b3_session_reaction_lab.py` só aceita o arquivo de expectativas **original e inalterado** do pré-Copom congelado no Git blob `4f6ff11f05b78d6361b2c1e313ce2e394acfff63` (commit `1281f21860211e9b6f784c649396aa56d17ecdf5`). Ele não ingere divulgação do Copom, notícia nem preço real.

- Sem observações posteriores: produz `LAB_COPOM_B3_PRICE_REACTION_PENDING_REAL_QUOTES`, com os fechamentos regulares documentados e a primeira abertura proposta, sem acerto ou direção.
- Para verificar a aritmética, aceita **somente** um ou dois registros `fixture_mode=SYNTHETIC_TEST_ONLY`, em símbolos `SIM_WIN` e `SIM_WDO`; rejeita símbolos de contratos reais, dados com alegação de origem B3 e permissões de uso que não foram verificadas.
- Os registros de teste exigem cotações anteriores dentro da janela regular de 04/11, e posteriores dentro da janela candidata de 05/11, com relógios UTC explícitos, sem consultar informação futura. Nunca usa candle de mesmo dia após fechamento, nem cria preço na abertura sem observação.
- Calcula a diferença percentual SOMENTE entre preços fictícios e exibe `LAB_COPOM_B3_SYNTHETIC_REACTION_ONLY`; não é lucro, sinal, probabilidade de acerto, previsão prospectiva ou preço/volatilidade real.
- Para casos reais futuros serão necessários: calendário B3 e exceções, contrato/vencimento idêntico antes/depois (ou série contínua com ajuste explícito sem vazamento temporal), fonte, horário e direitos de uso de dados B3, escolha de spread/último negócio/preço de abertura e metodologia de deslizamento. Também é necessário comprovar a divulgação e decidir se outros acontecimentos externos afetaram o movimento.

## Blindagem adicional de contrato e preço (03/11/2026)

O protótipo agora exige **identidade explícita do mesmo contrato fictício** em duas referências: `pre_contract_id` e `post_contract_id`. Apenas `SIM_WIN_FAKE_SINGLE_EXPIRY` ou `SIM_WDO_FAKE_SINGLE_EXPIRY` são admitidos conforme o instrumento. Troca de identificador, vencimento, WIN por WDO, código real de contrato ou valores não textuais são recusados. Esses nomes são **inventados exclusivamente para os testes**, não representam um vencimento real da B3. A igualdade nos exemplos **não certifica** identidade do contrato verdadeiro.

Também exige que as duas cotações fictícias tenham o tipo `SIMULATED_REGULAR_TRADE_TICK`, recusando dados declarados como **preço de ajuste, liquidação ou candle**. Na futura coleta real, não basta rotular um dado: será necessário conferir o negócio, código completo e mês/ano de vencimento no arquivo original de uma fonte autorizada e guardar a evidência de origem e horário.

O retorno de LAB registra seis requisitos ainda sem prova: calendário de negociação e exceções B3, contrato idêntico, último negócio regular pré-evento, primeiro negócio regular pós-evento, direitos/origem de preços e **outros acontecimentos no intervalo noturno** (juros DI, USD e notícias). Nenhum requisito pode ser dado por concluído a partir de uma fixture, e `gap_causally_attributable_to_copom=false` permanece obrigatório. O estudo é de **gap de sessões**, não prova causal exclusiva.

**Observação de desenho:** se o dado de reação vier da sessão seguinte, não será correto chamar o estudo de negociação de notícia em segundos. É um **gap entre sessões** com múltiplos fatores potencialmente envolvidos; não pode atribuir causalidade exclusiva ao Copom.

`test_atlasquant_trader_copom_b3_session_reaction_lab.py`: 32 testes unitários sintéticos, incluindo limite de sessão WIN/WDO, conversão BRT-UTC, bloqueio de futuro, recusa de contratos reais não auditados e de snapshots pré-evento alterados. Registrado na suíte Quality CI, a confirmar no GitHub do commit.

**PR #1803 DRAFT / LAB / HARD NO-GO, sem custo adicional, Render, Worker, cron, feed, produção, merge, deploy, alteração visual ou operação real.**
