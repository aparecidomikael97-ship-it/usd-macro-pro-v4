# AtlasQuant — Checkpoint Mestre
## Proposta consolidada — decisões do proprietário, integração de outubro e pendências preservadas

**Data de referência:** 17/11/2026  
**Estado:** DOCUMENTO / LAB / SOMENTE TEXTO / HARD NO-GO  
**Publicação no GitHub:** PR documental em rascunho autorizada em 17/11/2026, 00h53 de Cuiabá; merge NÃO AUTORIZADO  
**Convenção temporal:** UTC como referência técnica; Cuiabá = UTC−4.

---

## 0. Alerta de integridade — merges de outubro de 2026

### 0.1 PR #910: integração identificada

**[CONFIRMADO POR EXECUÇÃO — consultas anteriores à API do GitHub]**

A PR #910, *CI ONLY — AION B2B Durable Dispatch Record Contract V1*, apresenta:

| Campo | Registro |
|---|---|
| Estado | Fechada, com merge |
| Destino | `main` |
| `merged` | `true` |
| `draft` | `true` |
| `merged_by` | `aparecidomikael97-ship-it` |
| Commit associado | `8acda88a5801f1ddbf9bec70eeb5fe38011e87e0` |
| Commits na comparação acumulada | 1.050 |
| Arquivos na comparação acumulada | 537 |
| Horário do merge | 07/10/2026, 01h38min10s UTC |
| Horário em Cuiabá | 06/10/2026, 21h38min10s |

O commit individual `8acda88` alterou somente `.github/workflows/quality-tests.yml`, incluindo um teste no Quality CI.

A quantidade de arquivos da comparação acumulada não representa o número de arquivos modificados pelo commit individual.

**[NÃO VERIFICADO]**

A causa da combinação `draft=true` e `merged=true` permanece desconhecida.

### 0.2 Integração concentrada no mesmo intervalo

**[CONFIRMADO POR EXECUÇÃO — API do GitHub, conforme investigação do auditor Claude em 17/11/2026]**

As 30 PRs com título *CI ONLY* entre #888 e #950, registradas como integradas à `main`, possuem `merged_at` entre:

**07/10/2026, 01h38min09s e 01h38min10s UTC.**

A PR #964, *Release Candidate — AION Core V1 Frozen Integration → main*, apresenta merge às **01h38min07s UTC**.

A PR #952, *CI ONLY — AION Core V1 Technical Closure Candidate*, apresenta merge às **01h38min09s UTC**.

**[INFERIDO]**

Essa concentração é compatível com um único evento de integração acumulada, em vez de dezenas de ações independentes.

Não comprova que tenha sido executado apenas um comando.

**[NÃO VERIFICADO]**

O mecanismo efetivo de integração, o executor físico e a existência de registro escrito contemporâneo de autorização não foram estabelecidos.

**Classificação:** padrão compatível com evento único de integração; mecanismo efetivo não verificado.

### 0.3 Declarações posteriores do proprietário

Em **17/11/2026, às 00h25 de Cuiabá (04h25 UTC)**, o proprietário declarou ao auditor Claude, com base em sua memória:

**“Tudo foi com autorização minha.”**

A declaração abrange a integração da noite de 06/10/2026 em Cuiabá, incluindo a PR #964 e as PRs CI ONLY registradas naquele intervalo.

Em **17/11/2026, às 00h28 de Cuiabá (04h28 UTC)**, o proprietário também declarou que sua autorização abrangia os merges posteriores:

| PR | Descrição | Horário em UTC |
|---|---|---|
| #965 | Manual Render deploy + workflow newline hardening | 07/10, 10h32min23s |
| #973 | Production Build Identity manual post-deploy only | 07/10, 11h00min52s |
| #974 | Interface Finalization Lock V2 | 07/10, 12h27min49s |

As declarações são registros posteriores da memória do proprietário. Não são evidência de execução técnica nem substituem um documento escrito contemporâneo.

**Classificação documental:**

**AUTORIZAÇÃO DECLARADA PELO PROPRIETÁRIO, DE MEMÓRIA, SEM REGISTRO ESCRITO LOCALIZADO; EXECUTOR FÍSICO NÃO VERIFICADO.**

**[NÃO VERIFICADO]**

Não foi localizado registro escrito contemporâneo que documente a autorização específica desses merges.

Não se sabe se a integração foi executada pessoalmente pelo proprietário, por assistente ou por automação.

A declaração posterior não poderá ser retroativamente apresentada como documento de autorização emitido em outubro.

Não se afirma que os merges foram indevidos, comprovadamente autorizados por documentação contemporânea ou acidentais.

### 0.4 Divergência entre o texto das PRs e os estados registrados

**[CONFIRMADO POR ANÁLISE ESTÁTICA — texto da PR #910]**

O corpo da PR #910 contém:

`DO NOT MERGE / DO NOT DEPLOY`

**[CONFIRMADO POR EXECUÇÃO]**

A mesma PR apresenta merge registrado na `main`.

**[CONFIRMADO POR ANÁLISE ESTÁTICA — Checkpoint #889]**

O documento histórico contém restrições de integração e declarações de etapas não mergeadas.

**[NÃO VERIFICADO — pelo auditor Claude]**

O relato da investigação do ChatGPT menciona restrições semelhantes nos textos de outras PRs da cadeia.

Essas restrições adicionais não foram reconferidas diretamente pelo auditor Claude.

Portanto, somente o texto da PR #910 e o conteúdo examinado do Checkpoint #889 podem ser atribuídos à conferência direta do auditor.

**[INFERIDO]**

Existe uma divergência documental entre instruções históricas de não integrar e estados posteriores registrados pelo GitHub.

As declarações de autorização prestadas pelo proprietário são posteriores e não modificam o texto original das PRs.

**Situação:** DIVERGÊNCIA DOCUMENTAL NÃO RESOLVIDA.

Não propor alteração, exclusão ou reversão de PRs, branches ou commits.

### 0.5 Checkpoint da PR #889

**[CONFIRMADO POR ANÁLISE ESTÁTICA]**

O Checkpoint #889 contém estados históricos como:

- `NÃO MERGIADO`.
- Nenhum merge ou deploy realizado.
- `70/70 workflows` concluídos.

**[INFERIDO]**

Esse documento deverá ser preservado como fotografia histórica, hoje desatualizada em relação às integrações posteriormente identificadas.

Uma nota de sucessão deverá explicar:

1. O estado originalmente documentado.
2. Os merges registrados posteriormente.
3. A declaração do proprietário prestada em 17/11/2026.
4. A ausência de autorização escrita contemporânea localizada.
5. As questões operacionais ainda não verificadas.

A decisão posterior do proprietário estabelece que a PR #889 deverá passar por reconciliação documental em outra etapa.

Até essa etapa, seu conteúdo permanecerá intacto.

**Estado:** APROVADO / PENDENTE DE REGISTRO.

Não há autorização implícita de merge da PR #889.

---

## 1. Verificações de CI e correção do workflow

### 1.1 Execuções vinculadas ao commit da PR #910

**[CONFIRMADO POR EXECUÇÃO — investigação anterior]**

Para o commit `8acda88`, foram encontrados:

| Fonte | Resultado |
|---|---|
| Check-runs | 72 com sucesso |
| Workflow runs | 73 |
| Workflow runs com sucesso | 70 |
| Workflow runs com falha | 3 |
| Endpoint legado `/status` | Zero registros, estado `pending` |

As execuções com falha possuem os identificadores:

`37440629791`, `37440667936` e `37441661387`.

Todas têm evento `push` e estão associadas ao arquivo:

`.github/workflows/aion-b2b-pilot-activation-persistence-attestation.yml`

Essas contagens representam conjuntos distintos de registros.

**[NÃO VERIFICADO]**

A apresentação visual “72 of 73 checks passed” não foi reconciliada conclusivamente.

O endpoint `/status` não identificou o check adicional.

### 1.2 Correção do YAML

**[CONFIRMADO POR ANÁLISE ESTÁTICA]**

Na versão histórica, o workflow estava armazenado em uma única linha física, com sequências literais `\n`.

**[CONFIRMADO POR EXECUÇÃO — histórico de commits]**

O commit `3430a35a9b1bca42f7fb7d23b8b3145cff29a61c` foi registrado em **07/10/2026, às 01h55min08s UTC**.

Título:

`fix(release): make Render deploy manual and repair workflow YAML`

Ele corrigiu a formatação do workflow, acrescentou testes de proteção contra o mesmo defeito e alterou a configuração do Render para desativar o deploy automático.

**[INFERIDO]**

O defeito de formatação é uma explicação tecnicamente consistente para as falhas históricas.

**[NÃO VERIFICADO]**

Não foi demonstrada a causa individual de cada execução por seus logs detalhados.

---

## 2. Janela de possível deploy no Render

**[CONFIRMADO POR EXECUÇÃO — histórico de commits e PRs]**

O primeiro merge identificado na `main` nessa sequência foi o da PR #964, registrado em:

**07/10/2026, 01h38min07s UTC.**

A correção do `render.yaml`, que estabeleceu `autoDeployTrigger: off`, foi registrada pelo commit `3430a35`, em:

**07/10/2026, 01h55min08s UTC.**

### Intervalo correto

| Referência | Horário |
|---|---|
| Início — merge da PR #964 | 07/10/2026, 01h38min07s UTC |
| Fim — correção `3430a35` | 07/10/2026, 01h55min08s UTC |
| **Duração total** | **17 minutos e 1 segundo** |
| Horário equivalente em Cuiabá | 06/10/2026, aproximadamente 21h38–21h55 |

**[INFERIDO]**

Como a configuração anterior indicava `autoDeployTrigger: commit`, existia possibilidade de implantação automática durante essa janela.

Isso não demonstra que o Render efetivamente iniciou ou concluiu um deploy.

**[NÃO VERIFICADO]**

Continuam desconhecidos:

- Se houve deploy nessa janela.
- Qual SHA eventualmente foi implantado.
- Qual era o estado operacional do serviço.
- Se ocorreram efeitos reais em produção.
- Se existiu relação causal entre os merges e algum deploy.

**Situação:** UNVERIFIED.

### 2.1 Decisão do proprietário sobre a investigação

Em **17/11/2026, às 00h45 de Cuiabá (04h45 UTC)**, o proprietário respondeu **“SIM PRA TODAS”** ao conjunto de perguntas apresentado pelo auditor Claude.

Para a pergunta 11.1, essa manifestação autorizou a conferência do histórico de deploys do Render referente ao intervalo acima, **somente em leitura**.

**Estado:** APROVADO / PENDENTE DE REGISTRO.

**Quando realizar a conferência:** PENDENTE.

O painel autenticado do Render exige acesso do proprietário. Essa aprovação não representa liberação de credenciais nem autorização para qualquer modificação.

A futura investigação não poderá:

- Iniciar deploy.
- Realizar rollback.
- Alterar configurações.
- Modificar serviços.
- Criar novas versões.

A ocorrência de deploy na janela histórica continua **NÃO VERIFICADA** até que existam evidências específicas.

---

## 3. Prioridade principal — decisão A

A decisão expressa do proprietário de 17/11/2026 estabelece a alternativa A como prioridade de desenvolvimento do AtlasQuant.

O piloto de oito ativos substitui a ordem geral de prioridades aprovada em 29/09/2026.

| Registro | Estado proposto |
|---|---|
| `D-PRIORITY-ORDER-2026-09-29` | `SUBSTITUÍDO` |
| `D-TRADER-PILOT-EIGHT-ASSETS-2026-11-17` | `APROVADO / PENDENTE DE REGISTRO` |

### 3.1 Instrumentos

| Grupo | Ativos |
|---|---|
| Forex | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD |
| Índices | US500, NAS100 |
| Ouro | XAUUSD |

Fonte candidata: Pepperstone MT5 Demo.

Objetivo imediato: desenvolver e avaliar o viés macroeconômico D1/W1.

### 3.2 Histórico preservado

AION, Núcleo, certificação, interface, Negócios e Investimentos deixam a prioridade imediata de expansão.

Permanecem preservados seus requisitos, códigos, decisões, documentação e bloqueios de segurança.

O universo FX28 não será apagado nem alterado por essa redução de escopo.

### 3.3 Limite da aprovação

A aprovação da prioridade não autoriza:

- Alteração de código.
- Criação ou merge de PRs técnicas.
- Deploy.
- Operações reais ou simuladas.
- Expansão dos instrumentos.
- Alteração dos protocolos CPI/PPI.

Cada ação posterior exige sua própria autorização.

A escolha do arquivo canônico e as autorizações documentais posteriores estão registradas separadamente nas seções 5 e 10.

---

## 4. Exceção de segurança — decisão aprovada

**[INFERIDO — conteúdo técnico da proposta original]**

Incidentes críticos de segurança, integridade e risco de perda de dados podem receber prioridade investigativa mesmo durante o desenvolvimento dos oito ativos.

### 4.1 Histórico das manifestações

Em 17/11/2026, o proprietário respondeu inicialmente **“OK”** à proposta.

O auditor Claude considerou essa resposta ambígua e não a aceitou como aprovação inequívoca.

Em manifestação posterior, o proprietário respondeu **“não sei”** sobre a mesma exceção.

Ambas as respostas permanecem preservadas como parte do histórico.

### 4.2 Decisão posterior

Em **17/11/2026, às 00h45 de Cuiabá (04h45 UTC)**, o proprietário aprovou expressamente a exceção de segurança, ao responder afirmativamente ao conjunto de perguntas apresentado pelo auditor Claude.

Essa decisão posterior esclarece o estado da proposta.

**Estado:** APROVADO / PENDENTE DE REGISTRO.

A decisão permite priorizar a **investigação** de incidentes críticos de segurança e integridade.

**Não autoriza nenhuma alteração técnica automática.**

Cada eventual ação corretiva continua dependendo de autorização específica, escopo definido e verificações correspondentes.

A exceção não autoriza modificar código, Render, MT5, workflows, branches, commits ou produção sem permissão própria.

---

## 5. Arquivo canônico do Checkpoint Mestre

### 5.1 Decisão expressa do proprietário

Em **17/11/2026, às 00h48 de Cuiabá (04h48 UTC)**, o proprietário escolheu expressamente:

`docs/CHECKPOINT_MESTRE.md`

como **ponto de entrada oficial único do Checkpoint Mestre**.

A decisão foi declarada ao auditor Claude após esclarecimento solicitado por ele.

A resposta original ao conjunto de perguntas havia sido **“SIM PRA TODAS”**, às 00h45, mas a pergunta sobre o arquivo exigia uma escolha entre alternativas. Essa escolha foi esclarecida às 00h48.

**Estado:** APROVADO / PENDENTE DE REGISTRO.

### 5.2 Histórico da escolha

O histórico inclui um relato anterior do ChatGPT sobre a escolha de `docs/CHECKPOINT_MESTRE.md`, que não havia sido reconferido diretamente pelo auditor Claude.

A fonte utilizada para a decisão consolidada passa a ser a declaração expressa do proprietário ao auditor em 17/11/2026, às 00h48 de Cuiabá.

A decisão não depende de presumir que a aprovação da alternativa A relativa à prioridade também abrangia o arquivo canônico.

São decisões distintas.

### 5.3 Preservação dos documentos anteriores

| Registro | Local |
|---|---|
| Checkpoint de 22/09 | `docs/continuidade/CHECKPOINT_MESTRE_ATLASQUANT_2026-09-22.md` |
| Reconciliação de 29/09 | `docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md` |
| Checkpoint de outubro | `docs/CHECKPOINT_MESTRE.md`, na PR #889 |

Os registros históricos deverão permanecer preservados integralmente.

O futuro arquivo canônico deverá apontar para os documentos anteriores, sem apagar seus textos ou substituir silenciosamente suas decisões.

### 5.4 Limite da escolha

A aprovação do caminho canônico, por si só, não autoriza criar ou editar o arquivo.

A criação do arquivo por meio de uma PR exclusivamente documental, em rascunho, foi autorizada especificamente pelo proprietário em 17/11/2026, às 00h53 de Cuiabá (04h53 UTC), depois da auditoria do texto consolidado.

O merge continua exigindo autorização expressa e separada.

---

## 6. Cadeia do executor — estado documental

### 6.1 PRs CI ONLY integradas

**[CONFIRMADO POR EXECUÇÃO — consultas anteriores e auditoria relatada]**

Foram identificadas 30 PRs com título CI ONLY e merge registrado na `main`, entre #888 e #950.

| Grupo | PRs | Quantidade |
|---|---|---:|
| Inicial | #888, #891, #893, #895, #896, #898, #900, #902, #904, #906, #908, #910 | 12 |
| Intermediário | #912, #914, #916, #918, #920, #922, #924, #926, #928, #930, #932 | 11 |
| Final | #936, #938, #942, #944, #946, #948, #950 | 7 |
| **Total** | | **30** |

Segundo a conferência do auditor, os merges estão concentrados entre 01h38min09s e 01h38min10s UTC de 07/10/2026.

As PRs #934 e #940 têm CI ONLY no título, mas não apresentam merge registrado.

### 6.2 PRs de transição do Núcleo

**[CONFIRMADO POR EXECUÇÃO — consultas anteriores]**

- #951: fechamento técnico candidato, integrado a branch de integração.
- #952: CI ONLY do fechamento técnico, integrada à `main`.
- #964: Release Candidate do Core V1, integrada à `main`.
- #965, #973 e #974: merges posteriores, abrangidos pelas declarações do proprietário de 17/11.

Não confundir integração em branch intermediária com integração direta na `main`.

### 6.3 Conteúdo técnico observado

**[NÃO VERIFICADO — pelo auditor Claude]**

O relato da investigação do ChatGPT informa que os commits individuais das 12 primeiras PRs foram examinados e que os módulos e testes correspondentes estavam presentes na árvore da `main` consultada.

O mesmo relato descreve 11 casos nos quais as mudanças individuais incluíam testes na lista de qualidade e a PR #896 como correção de asserções do workflow de rollback.

Esses detalhes não foram reconferidos diretamente pelo auditor Claude.

Não atribuir essa inspeção de código à auditoria independente do Claude.

**[INFERIDO]**

Mesmo que os arquivos estejam presentes, isso não basta para comprovar prontidão operacional, segurança integral ou autorização de efeitos externos.

### 6.4 Estado consolidado

**[INFERIDO — classificação conservadora]**

`UNVERIFIED`

Ainda não foram comprovadas:

- Conclusão operacional ponta a ponta.
- Autorização para execução de efeitos externos.
- Ativação de produção.
- Certificação integral das capacidades.
- Reconciliação definitiva entre documentação, integração e funcionamento.

A declaração de autorização dos merges não altera automaticamente o estado técnico do executor.

---

## 7. AION Core V1 — registro de congelamento

**[CONFIRMADO POR ANÁLISE ESTÁTICA]**

O documento de bloqueio de interface de 07/10/2026 declara o Core V1 formalmente congelado no alvo:

`662eab4dc4f5bb009fa1ca89f87530df74d30ddf`

**[INFERIDO]**

O congelamento documental não comprova a prontidão operacional de toda a cadeia do executor.

A evidência de congelamento será preservada como registro documental.

**Prontidão operacional do AION Core V1:** `UNVERIFIED`.

Não equiparar o congelamento documental à comprovação de funcionamento integral.

---

## 8. Atlas Índices — piloto, critérios e documentação

### 8.1 Regras técnicas preservadas

**[INFERIDO — consolidação das regras anteriormente discutidas]**

| Critério | Definição |
|---|---|
| Limiar mínimo | 70 pontos e dois fatores concordantes |
| Pesos macroeconômicos | 35/25/25/15 |
| Captura | H1, D1, W1 |
| Horizonte de viés | D1 e W1 |
| Avaliação planejada | 52 semanas informativas |
| Referências | Três baselines |
| Teste estatístico | Exato de sinais unilateral |
| Correção | Bonferroni `0,05/3` |
| Integridade | Dados e previsões com anterioridade verificável |
| Operações | Nenhuma real ou simulada |

O escore de 70 pontos não representa 70% de probabilidade de acerto.

### 8.2 Critério de expansão

A ampliação não será baseada apenas em “assertividade boa”.

Será considerada somente após:

1. Cumprimento do horizonte estatístico aprovado.
2. Comparação com três baselines.
3. Aplicação do teste exato e da correção Bonferroni.
4. Integridade de dados, calendários e fontes.
5. Prova de anterioridade das previsões.
6. Ausência de informação futura.
7. Auditoria independente.
8. Nova autorização expressa do proprietário.

O limite de 35 resultados favoráveis em 52 diferenças não empatadas não vale automaticamente em amostras com empates ou menos diferenças efetivas.

Não alterar as regras depois de observar resultados para favorecer o método.

### 8.3 Protocolo estatístico e pendências da v0.8

**[INFERIDO — aprovação do protocolo relatada, não reconferida pelo auditor Claude]**

O protocolo foi anteriormente descrito como aprovado, com regras de parada, agregação semanal e empates ainda pendentes.

Essa descrição **não constitui confirmação independente da aprovação integral do protocolo**.

Sua conclusão depende da resolução documental das regras ainda abertas.

As quatro pendências já existentes permanecem:

| Pendência | Situação |
|---|---|
| Faixa de estabilidade | PENDENTE |
| Classificação SURPRESA ou ESTADO por fator | PENDENTE |
| Validade temporal das evidências econômicas | PENDENTE |
| Regra de parada, agregação semanal e empates | PENDENTE |

A versão v0.8 também deverá resolver três lacunas adicionais:

**1. Definição de semana informativa**

**PENDENTE**

Ainda falta definir objetivamente quais condições tornam uma semana elegível para a contagem de 52 semanas informativas.

A regra deverá tratar cobertura, integridade, abstenções, dados faltantes e diferenças entre método e baselines antes da avaliação prospectiva.

Não escolher essa definição depois de observar os resultados.

**2. Exclusão do W1 do indicador estatístico principal**

**PENDENTE**

Ainda não foi aprovada a proposta de excluir o W1 do indicador estatístico principal.

É necessário decidir previamente se o W1 será apresentado separadamente ou integrado a alguma medida formal, preservando a utilidade do viés semanal.

A definição não deverá ser escolhida retrospectivamente.

**3. Número mínimo de diferenças efetivas**

**[INFERIDO — limite matemático, não decisão do proprietário]**

No teste exato unilateral com Bonferroni `0,05/3`, menos de seis diferenças efetivas não podem alcançar o limiar estatístico, mesmo que todas favoreçam o método.

Isso decorre da própria distribuição binomial: com cinco diferenças favoráveis em cinco, o valor unilateral é `1/32 = 0,03125`, superior a `0,01667`.

Com seis diferenças favoráveis em seis, o valor unilateral seria `1/64 = 0,015625`.

Essa observação **não significa que seis diferenças sejam suficientes para comprovar robustez ou que esse seja o mínimo metodológico aprovado**.

**[NÃO VERIFICADO]**

O proprietário ainda não aprovou a regra operacional do número mínimo de diferenças efetivas.

A futura decisão deverá preservar o horizonte de 52 semanas informativas e evitar conclusões baseadas em amostras excessivamente pequenas.

Nenhuma dessas sete pendências será escolhida por IA.

### 8.4 PR #2012 — referência documental

**[CONFIRMADO POR EXECUÇÃO — leitura anterior do GitHub e conferência relatada pelo auditor Claude]**

A PR #2012 reúne cinco arquivos de documentação da versão Atlas Índices v0.7, localizados em:

`docs/atlas-indices/`

A PR está aberta como rascunho, sem merge.

Os documentos tratam de:

- Apresentação e prioridade do piloto.
- Especificação funcional v0.7.
- Contrato documental de captura MT5 H1/D1/W1.
- Decisões e pendências.
- Histórico das versões.

A PR não constitui implementação operacional do motor.

**[NÃO VERIFICADO — como versão publicada no GitHub]**

A versão v0.8 foi elaborada em texto, mas não possui registro publicado no GitHub identificado na auditoria.

**Pendência:** `Atlas Índices v0.8 no GitHub — PENDENTE`.

O futuro registro da v0.8 não está autorizado por esta proposta.

### 8.5 Interface experimental

**[INFERIDO — objetivo de desenvolvimento]**

A interface futura deverá apresentar ALTA, BAIXA ou ABSTER-SE para os oito ativos, com fonte, motivo, horário e estado da evidência.

Aviso obrigatório:

**EM VALIDAÇÃO — NÃO É SINAL DE OPERAÇÃO.**

Nenhuma operação real ou simulada está autorizada.

---

## 9. Pendências oficiais — lista integral atualizada

| Tema | Estado |
|---|---|
| Prioridade dos oito ativos | `APROVADO / PENDENTE DE REGISTRO` |
| Autorização dos merges de outubro | Declarada posteriormente pelo proprietário, de memória |
| Registro escrito contemporâneo dos merges | `NÃO VERIFICADO` |
| Executor físico dos merges | `NÃO VERIFICADO` |
| Mecanismo de integração concentrada | `NÃO VERIFICADO` |
| Contradição entre o texto das PRs e os merges | Divergência documental não resolvida |
| Combinação `draft=true` e `merged=true` da #910 | Causa não verificada |
| Indicador visual “72 de 73 checks” | `NÃO VERIFICADO` |
| Deploy do Render de 01h38min07s a 01h55min08s UTC, 07/10/2026 | `UNVERIFIED` |
| **Consulta ao histórico de deploys do Render** | **`APROVADO / PENDENTE DE REGISTRO` — somente leitura; horário pendente** |
| **Exceção de segurança** | **`APROVADO / PENDENTE DE REGISTRO` — sem autorização técnica** |
| **Escolha do arquivo canônico** | **`APROVADO / PENDENTE DE REGISTRO` — `docs/CHECKPOINT_MESTRE.md`; escrita somente por PR documental em rascunho, autorizada em 17/11/2026, 00h53 (Cuiabá); merge não autorizado** |
| **Destino da PR #889** | **`APROVADO / PENDENTE DE REGISTRO` — reconciliação documental posterior; PR intacta até lá** |
| **Autorização de PR documental** | **`APROVADO / PENDENTE DE REGISTRO` — criação da branch e da PR em rascunho autorizada em 17/11/2026, 00h53 (Cuiabá); merge não autorizado** |
| Estado operacional da cadeia do executor | `UNVERIFIED` |
| AION Core V1 — congelamento documental em `662eab4`; prontidão operacional | `UNVERIFIED` |
| Regras finais do piloto | `PENDENTE` |
| **Definição de semana informativa — v0.8** | **`PENDENTE`** |
| **Exclusão do W1 do indicador estatístico principal — v0.8** | **`PENDENTE`** |
| **Número mínimo de diferenças efetivas — v0.8** | **`PENDENTE`** |
| Production Browser Smoke #266 | `UNVERIFIED` — relatado como vermelho, não investigado |
| SHA efetivamente implantado no Render | `UNVERIFIED` |
| Segunda cópia do backup | `PENDENTE` |
| Teste de restauração do backup | `PENDENTE` |
| Auditoria retrospectiva desde 15/09 até a conclusão do Núcleo | `PENDENTE` |
| Decisão de manter ou pausar o Render | `PENDENTE` — escolha exclusiva do proprietário |
| Atlas Índices v0.8 no GitHub | `PENDENTE` |

A aprovação da investigação do Render não equivale à comprovação de que houve deploy.

A autorização da PR documental em rascunho não equivale à autorização de merge.

Nenhuma pendência poderá desaparecer de versões futuras sem evidência de conclusão, decisão expressa de descarte ou registro de substituição.

---

## 10. Governança e preservação histórica

**[INFERIDO — procedimento documental proposto]**

A consolidação deverá seguir:

Decisão expressa do proprietário → proposta textual → auditoria independente → reconciliação histórica → autorização específica de escrita → PR documental → Quality CI → revisão independente → autorização separada de merge.

### 10.1 Decisão sobre a PR documental

Em **17/11/2026, às 00h45 de Cuiabá (04h45 UTC)**, o proprietário autorizou **para o futuro** uma PR exclusivamente documental, depois da auditoria final do texto.

Em **17/11/2026, às 00h53 de Cuiabá (04h53 UTC)**, após a auditoria do texto consolidado, o proprietário declarou **“AUTORIZO”** à criação de uma branch nova e de uma PR exclusivamente documental, em rascunho, com um único arquivo novo: `docs/CHECKPOINT_MESTRE.md`.

**Estado:** APROVADO / PENDENTE DE REGISTRO.

Essa autorização não inclui merge, marcar a PR como pronta para revisão, alterar arquivos existentes nem qualquer ação na PR #889.

O merge exigirá outra autorização expressa.

### 10.2 Decisão sobre a PR #889

Em **17/11/2026, às 00h48 de Cuiabá (04h48 UTC)**, o proprietário decidiu que a PR #889:

**“Passa por uma reconciliação documental depois.”**

**Estado:** APROVADO / PENDENTE DE REGISTRO.

A PR continuará intacta até que a etapa seja especificamente autorizada e executada.

Não há autorização implícita de merge.

### 10.3 Preservação do histórico

Registros substituídos conservarão:

- Identificador.
- Data.
- Origem.
- Conteúdo histórico.
- Estado da época.
- Referência à decisão sucessora.

As declarações prestadas em 17/11/2026 sobre os merges serão preservadas com sua data real.

Não serão utilizadas para criar retroativamente um documento de autorização datado de outubro.

A documentação do Atlas Índices v0.7 e suas versões anteriores permanecerá preservada.

A publicação da v0.8 exigirá autorização própria.

### 10.4 Limites permanentes

Nenhuma das decisões documentais autoriza:

- Modificação de código do Motor A.
- Alteração dos protocolos CPI/PPI.
- Alteração do cadastro FX28.
- Mudança de workflows.
- Execução ou modificação no MT5.
- Alteração de serviço Render.
- Deploy ou rollback.
- Operações reais ou simuladas.
- Ativação de capacidades externas do AION.

---

## 11. Questões ainda abertas ao proprietário

As cinco decisões apresentadas anteriormente foram respondidas pelo proprietário em 17/11/2026, às 00h45 e 00h48 de Cuiabá.

Permanecem apenas as definições de execução que não foram autorizadas para esta etapa.

### 11.1 Quando conferir o histórico do Render?

A investigação **somente em leitura** foi aprovada para o intervalo de:

**07/10/2026, 01h38min07s a 01h55min08s UTC.**

Quando o proprietário deseja realizar essa conferência no painel autenticado do Render?

O acesso deverá ser feito por meio autorizado, sem compartilhamento de credenciais.

A investigação não permitirá deploy, rollback nem alteração de configuração.

### 11.2 Quando autorizar o merge documental?

A criação da branch e da PR exclusivamente documental, em rascunho, foi autorizada em 17/11/2026, às 00h53 de Cuiabá (04h53 UTC).

O merge exigirá uma autorização expressa e separada, depois da revisão da PR e do Quality CI pelo auditor.

---

## 12. Declaração final de integridade

A proposta incorpora as decisões do proprietário comunicadas ao auditor Claude em 17/11/2026:

- Investigação somente de leitura do histórico de deploys do Render, com horário de realização ainda pendente.
- Exceção de segurança aprovada como prioridade investigativa, sem autorização de alterações técnicas.
- Escolha de `docs/CHECKPOINT_MESTRE.md` como ponto de entrada oficial único.
- Reconciliação documental posterior da PR #889, que permanece intacta.
- Autorização, em 17/11/2026 às 00h53 (Cuiabá), de uma branch nova e de uma PR exclusivamente documental em rascunho, com um único arquivo novo; o merge não está autorizado.

Também foram preservadas as quatro pendências estatísticas anteriores e acrescentadas as três lacunas da v0.8: definição de semana informativa, eventual exclusão do W1 do indicador principal e número mínimo de diferenças efetivas.

A autorização dos merges históricos foi declarada posteriormente pelo proprietário, de memória, sem registro escrito contemporâneo localizado.

A hipótese de evento único de integração não comprova o mecanismo exato nem a identidade do executor físico.

O possível deploy do Render durante a janela de **17 minutos e 1 segundo** permanece `UNVERIFIED`.

A prioridade dos oito ativos está aprovada, mas o piloto ainda não possui desempenho estatístico demonstrado.

**Declaração de integridade:** esta revisão é exclusivamente textual.

Até a redação desta proposta, ela própria não criou nem alterou arquivo, branch, commit, PR, merge ou workflow; a criação posterior da PR documental em rascunho está registrada nas seções 5.4 e 10.1.

Esta revisão de texto não acessou GitHub, Render ou MT5; as consultas de leitura do auditor Claude estão descritas nas seções 0.1 a 0.4.

Nenhuma alteração foi feita no cadastro FX28, Radar ou Painel Mestre.

Nenhuma ordem real ou simulada foi executada ou autorizada.

Nenhuma credencial foi solicitada.

Nenhuma decisão foi tomada em nome do proprietário.

**Estado final: DOCUMENTO / LAB / AGUARDAR / HARD NO-GO.**