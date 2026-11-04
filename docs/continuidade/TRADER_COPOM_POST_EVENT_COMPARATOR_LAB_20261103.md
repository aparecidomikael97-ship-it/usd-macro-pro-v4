# AtlasQuant Trader — comparador pós-Copom 04/11, PREPARADO antes do evento (03/11/2026)

**PR #1803 DRAFT | LAB / HARD NO-GO.** Esta etapa prepara código e testes, **não contém uma decisão real do Copom**. Na data do desenvolvimento, a decisão de 04/11/2026 ainda não foi publicada. Não ligar Render, Worker, cron, APIs pagas, negociação, Radar ou alterar o visual aprovado.

## Por que este módulo existe

Em 03/11 foi congelada uma versão do cenário pré-Copom com as seguintes expectativas:

- Registro Git pré-evento imutável por conteúdo: commit `1281f21860211e9b6f784c649396aa56d17ecdf5`, blob Git do JSON `4f6ff11f05b78d6361b2c1e313ce2e394acfff63`. O arquivo original continua em `docs/continuidade/TRADER_COPOM_20261104_FROZEN_PRE_EVENT_20261103.json`. **Reformatação, mudança de número, fonte ou horizonte torna o blob diferente e o comparador recusa.**
- Reuters 03/11: 33/48 economistas respondentes esperavam manutenção em **13,75%** (68,75% da AMOSTRA, não probabilidade de mercado).
- Alternativa condicional: corte de 0,25 pp até 13,50%; terceiro ramo: qualquer outro desfecho.
- Focus data-base 30/10 publicado em 03/11: Selic para fim/2026 = 13,50%, para fim/novembro = 13,50%. Ambos **diferentes da pergunta sobre a reunião 04/11**.

Fonte dos horários: calendário do Copom 03–04/11 e comunicado normativo do Banco Central que prevê divulgação do comunicado **a partir das 18h30 de Brasília de 04/11, 21h30 UTC** (limite mínimo, não horário preciso): https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Comunicado&numero=43383 . **O código não consulta uma página ou coleta a decisão.**

## Contrato novo: `atlasquant_trader_copom_post_event_compare_lab.py`

1. Sem conteúdo pós-evento, retorna `LAB_COPOM_POST_EVENT_OFFICIAL_RELEASE_PENDING`, inclusive depois do horário teórico, até termos uma publicação real independente.
2. Se alguém entregar um suposto resultado antes de **04/11 às 21h30 UTC**, recusa. Exige horário declarado de publicação e de primeira observação em UTC, ambos anteriores ao relógio de avaliação.
3. Exige link HTTPS com host literal `www.bcb.gov.br`, caminhos de comunicado/notícia admitidos, texto extraído com menção a Copom, Selic e a taxa anual informada, bytes UTF-8 e SHA-256 local consistente. Não confia em fonte terceirizada disfarçada nem em arquivo alterado após hash.
4. Com conteúdo sintético consistente, retorna apenas `LAB_COPOM_POST_EVENT_CANDIDATE_UNATTESTED` e classifica **HOLD_13_75**, **CUT_25BP_13_50** ou **OTHER**. Isso é só classificação do que o texto *afirma*, nunca resultado oficial atestado ou acerto de previsão.
5. Mesmo com URL/sha/relógio coerentes, um chamador pode forjar os dados. Por isso `actual_policy_decision_verified=false`, `release_independently_authenticated=false`, `trader_accuracy=null`, `market_direction=AGUARDAR`, `market_implied_probability=null`, e todas as permissões de operação/produção/despesa são falsas.

## Como usaremos depois do comunicado

- Conferir **manualmente no BCB** o comunicado publicado, o teor e a decisão efetiva e sua data; preservar o URL definitivo e os bytes originais/headers quando o ambiente permitir.
- Validar que o texto e o valor citado realmente tratam **da decisão atual**, e não de Selic passada, projeção ou citação. Só depois adicionar um **registro de verificação independente distinto**; esta etapa não o implementa.
- Comparar com o artefato 03/11 já congelado, **sem reescrever o checkpoint nem criar previsão retroativa**.
- Estudar reprecificação DI, mercado de dólar e WIN/WDO com dados antes/depois e horários independentes. Um único desfecho de juros não mede assertividade do viés macro nem lucro.
- Em caso de conteúdo ausente, erro, timestamp não verificado ou fonte divergente, manter `AGUARDAR`.

## Testes

`test_atlasquant_trader_copom_post_event_compare_lab.py` tem **24 cenários sintéticos**, inclusive rejeição do JSON pré-evento adulterado, datas futuras, fontes falsas, SHA errado, texto malformado, simulações de manutenção/corte/outro e bloqueio de falsas probabilidades. **Nenhum cenário de teste corresponde à decisão real de 04/11.** O novo teste foi incluído no workflow Quality. A aprovação da CI precisa ser consultada para o commit que contiver este módulo.

**ZERO contratação de notícias, ZERO alteração no Render, zero merge/deploy/Worker/cron/ordens.**
