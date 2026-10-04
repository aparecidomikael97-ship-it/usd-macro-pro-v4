# Trader runtime consistency — revisão pós-#555

Base confirmada antes das alterações: `a61cd9c21748ad4f6cf61f5e24bdc4642df2f00f`.
Branch: `fix/trader-runtime-state-consistency-20261003`. Entrega por nova Draft PR. #555 não foi reaberta nem alterada.

## Causa e contrato de apresentação

O adaptador anterior descartava todo o snapshot quando sua idade ultrapassava o TTL de runtime de 90 minutos. Isso apagava preços, vieses, timeframes e contexto persistidos da apresentação e devolvia PRÉVIA, apesar de haver sete packs. O validador operacional continua intacto. A apresentação agora distingue VALIDATED_CURRENT, STALE_HISTORY e INVALID: idade isolada conserva histórico; estrutura, segurança e timestamps inválidos continuam fechados. STALE_HISTORY nunca entra no ranking atual, nem habilita execução.

Snapshot auditado: `2026-10-03T22:04:57.892654+00:00`, arquivo remoto SHA `a546ee443f7e504655a3c694fd5a9cf478e4669c`. Status: última execução `2026-10-03T22:04:59.520477+00:00`, MARKET_CLOSED, 0/480 usados. Scanner: sete leituras persistidas, zero atuais. Market Map: sete persistidos, zero atuais. Seis sinais EXPIRED e AUD/USD NO_SIGNAL. Não há Top 10 operacional publicado.

| Par | Último preço persistido |
| --- | --- |
| EUR/USD | 1.12519 |
| GBP/USD | 1.32401 |
| AUD/USD | 0.69561 |
| NZD/USD | 0.56152 |
| USD/JPY | 157.86313 |
| USD/CHF | 0.82882 |
| USD/CAD | 1.42503 |

Os preços técnicos são de 02/10. O ticker apresenta Último preço, timestamp próprio, Último viés e EXPIRADO · REVALIDAR ou SEM SINAL / AGUARDAR. Nunca os promove a cotação live. Variação ausente permanece —. Macro/Fed têm timestamp e avaliação de frescor independentes.

## Scanner, ranking e manutenção

O produtor apenas serializa `market_strip`: até 30 closes M15 fechados por par, timestamps, último preço e proveniência `scanner/cache_v110/m15`, extraídos do cache existente. Não serializa o cache inteiro e não chama providers. Séries antigas aparecem como HISTÓRICO M15 · REVALIDAR. O snapshot remoto auditado ainda não contém esse campo; as capturas reais são projeção local explícita do patch sobre o snapshot e o scanner existentes, sem alterar timestamps.

Home e Painel Mestre legado usam o mesmo `eligible_fx_population`: prontidão, proveniência confirmada, pipeline elegível, sinal CONFIRMED e validade futura. O ranking macro fica separado como MAPA MACRO DE ATENÇÃO, com NÃO OPERAR. A métrica Radar 28/28 foi substituída por Universo Forex / pares cadastrados; cobertura atual e leitura persistida permanecem separadas.

Atualizações manuais de mercado ficam ocultas no fluxo normal. Só aparecem com `ATLASQUANT_MANUAL_MARKET_REFRESH=1` e sessão ADMIN já existente. Código manual e proteções de quota continuam presentes. Nenhuma autorização, RBAC ou gate foi modificado.

## Estado e navegação das 24 funções

As 24 rotas existentes permanecem na mesma barra lateral desktop e no acesso mobile Funções do Trader · 24. Iniciante e Avançado conservam todos os acessos. Nenhuma tela aprovada foi redesenhada.

O modelo comum usa evidência residente por módulo: Scanner, Radar, Mestre, ICT, Market Map, Autopilot, Macro/Fed, Paper, Performance, Guardião e notícias. Laboratório, Diário e Perfil indicam disponibilidade local. Outras funções mostram SEM DADOS ou SEM FONTE LIVE conforme a ausência real. Resumos úteis são apresentados antes do acesso às análises legadas; navegação e retorno continuam operantes.

News Global possui 219 histórias persistidas; Pré-Notícia / Nowcast é separado e mostra AUTH_ERROR / HTTP 401, retry de 360 minutos. Paper tem zero trades; Model Paper tem 387 candidatos, 381 bloqueados por contexto e seis por timeframe. Setup Audit aguarda amostra. Não há ordem real.

DXY mostra força USD macro, com fonte explícita; DXY spot não tem fonte live configurada. Índice amplo USD (FRED) tem nome próprio e não é apresentado como DXY spot. NASDAQ, demais índices e criptos sem produtor live usam SEM FONTE LIVE CONFIGURADA. O ticker de Investimentos segue os mesmos estados.

## Auditoria read-only do Autopilot

Workflow 358055609 ativo; cron declarado `7,37 * * * *`. Foram lidos 30 runs: 27 schedule e três push, todos success. Último run auditado: [37157121636](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/37157121636), push em 03/10 22:03:18 UTC, concluído 22:05:27. Último schedule: [37144832690](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/37144832690), 03/10 18:36:27 UTC, concluído 18:38:20.

Não havia novo dispatch schedule registrado depois desse horário na amostra consultada. O workflow não estava desativado e a amostra não contém falhas que expliquem o intervalo. Causa da ausência de novos disparos não comprovada. Não houve run/rerun/enable nem alteração de configuração de Actions; o arquivo do Autopilot permanece intacto.

## Validação e evidências

Quality local: 4.170 testes, OK, um skip. Contratos de apresentação e navegação, orçamento, integridade do cache e scanner foram executados adicionalmente. Chromium percorre as 24 rotas, registra título realmente renderizado, painel conectado, estado, uso residente, prévia, console, overflow e duplicação. Testa cliques, retorno, descoberta mobile, hover/focus e reduced-motion. Painel Mestre legado é renderizado com chamadas de provider proibidas, em 1280×720, 1440×900, 1024×768 e 390×844.

Capturas de QA sintético ficam no artifact CI `atlasquant-reference-ui-evidence`. Capturas da projeção com dados reais persistidos, auditoria JSON e fonte local explicitamente rotulada ficam no pacote local de evidências. Incluem todas as 24 rotas desktop, módulos críticos mobile, lista aberta e retorno à home; a matriz local acrescenta 768×1024.

Tooltip Fechar: não reproduzido nos elementos próprios das 24 rotas; não foi atribuída causa sem evidência. O texto legítimo Fechar sinal no painel legado não é um tooltip órfão.

## Pendências e limites

A serialização nova só chegará ao artifact remoto em uma futura execução autorizada após integração pelo responsável. Este trabalho não executou o Autopilot nem fez merge/deploy. A lacuna de schedule e o erro de autenticação Nowcast continuam pendências externas. Não há preços live inventados para índices/cripto/DXY; dados históricos permanecem identificados.

480/dia, 28/hora, 6/62s, quota saver, real_orders=false, automatic_execution=false e 28FX live disabled preservados. AION Core não foi alterado. Não houve trade real, merge, deploy ou aumento de cota.
