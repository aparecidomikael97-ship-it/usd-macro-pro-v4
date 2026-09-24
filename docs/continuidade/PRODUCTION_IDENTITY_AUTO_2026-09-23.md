# AtlasQuant — Automatic Production Identity — 2026-09-23

## Objetivo

Fechar a lacuna entre **produção saudável** e **produção comprovadamente executando o mesmo código validado na main**.

O endpoint de saúde HTTP 200 continua importante, mas não prova sozinho que o Render já trocou para o build recém-mesclado.

## Mudança

O workflow `AtlasQuant - Production Browser Smoke` continua sem gatilho direto de `push`.

Isso preserva o desenho do Render:

`autoDeployTrigger: checksPass`

Depois que o workflow **AtlasQuant - Mobile DOM Stability** termina com sucesso para um push na `main`, o Browser Smoke é iniciado por `workflow_run`.

Assim:

1. os checks do push podem terminar;
2. o Render pode iniciar o deploy de `checksPass`;
3. o Browser Smoke roda fora do conjunto de checks do push;
4. ele espera a produção trocar para o source bundle esperado;
5. abre desktop e mobile no Chromium;
6. compara o fingerprint de código da produção com o commit exato que disparou a validação.

## Identidade exata

Em execução automática, o Browser Smoke recebe:

`TARGET_SHA = github.event.workflow_run.head_sha`

O checkout é feito explicitamente nesse SHA.

O fingerprint `expected_source_build` é calculado desse checkout e comparado ao marcador oculto da aplicação em produção:

`#atlasquant-source-build-marker`

O commit Git exposto pelo host continua apenas diagnóstico. O fingerprint do source bundle é a prova principal quando metadados Git não estão disponíveis no Render.

## Janela de deploy

A espera pela identidade do deploy foi ampliada de aproximadamente 3 minutos para aproximadamente 6 minutos, mantendo limite total de 20 minutos.

Essa espera é separada da medição de velocidade da interface, portanto tempo do Render para publicar um novo build não é atribuído incorretamente à performance do AtlasQuant.

## Segurança

O workflow:

- continua read-only no GitHub;
- não escreve no runtime;
- não contém secrets da aplicação;
- não executa ordem;
- não altera Safety Core;
- não bloqueia o deploy `checksPass` como um check de push;
- só encadeia automaticamente quando Mobile DOM terminou com sucesso em um push da `main`.

Execuções manuais e agendadas continuam disponíveis.

## Regra da Verdade

A partir deste mecanismo, um novo commit não deve ser chamado de **build confirmado em produção** somente porque Production Health ficou verde.

A confirmação forte exige Browser Smoke verde com:

`source_build == expected_source_build`

e sem falhas críticas de renderização/DOM nas verificações desktop e mobile.
