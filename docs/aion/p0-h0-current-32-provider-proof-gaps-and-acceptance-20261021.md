# AION P0/H0 — 32 erros do produtor: vínculo exato entre Quality 6.562 → 6.895

**21/10/2026 · Verificação documental offline em LAB · HARD NO-GO · 0/6 P0 homologados.**

## Resultado da auditoria

Reunimos os dois inventários já existentes, sem reescrever seu histórico: a matriz `docs/aion/AION_P0_32_EXTERNAL_PRODUCER_EVIDENCE_MATRIX_20261020.json`, originada de uma Quality mais antiga com **6.562 testes**, e o manifesto `docs/aion/evidence/aion_p0_quality_85_red_baseline_20261021.json`, extraído da execução canônica de **6.895 testes**, SHA `0630441417fb1ec0e42a06ca0b104a311a6de399`, job `119348084463`. Validamos também a reprodução canônica mais recente da PR #1405, SHA `a4789ab097f7a80bc6b25da9b893ed312b03f794`, [run #39638294268](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39638294268), com os mesmos 85 IDs e 51 FAIL +34 ERROR.

O cruzamento **não** foi feito apenas pelo número 32. Para cada ocorrência, exigimos igualdade de módulo, classe, método, subteste quando presente e exceção observada. Resultado: **32/32 correspondem exatamente**, sem um só ID órfão ou duplicado e sem diferença de exceção. A seleção atual contém 23 erros do Outbox em gate de matrícula de produtor, 8 erros de recibo causal e 1 erro de prova terminal de ausência de efeito, completando os 9 de Saga (8+1) e os 23 de Outbox. Um identificador desaparecer ou mudar de exceção exige revisão manual, nunca é contado como autoridade ou fechamento do P0.

| Classe de bloqueio | Casos atuais | Prova externa faltante |
|---|---:|---|
| `PRE_ADAPTER_PRODUCER_ENROLLMENT` | 23 | Identidade/account/endpoint/escopo do fornecedor, chave pública com matrícula independente, vínculo ao intent/nonce, revogação e controle administrativo externo |
| `CAUSAL_COMMITTED_EFFECT_RECEIPT` | 8 | Recibo emitido/autenticado pelo produtor para a primeira tentativa real, com vínculo causal, referência de efeito, sequência e histórico sob custódia independente |
| `TERMINAL_NO_EFFECT_FENCE` | 1 | Prova **do próprio produtor** de que nenhum efeito ocorreu nem poderá chegar tardiamente, incluindo bloqueio de replay, high-water monotônico e reinício/restauração |

O pacote de evidência está em `docs/aion/evidence/aion_p0_h0_32_provider_errors_current_6895_crosswalk_20261021.json`. A auditoria em `tools/aion_p0_h0_provider_32_crosswalk_audit.py` confere o pacote contra os **dois documentos originais** e impede que uma alteração de matriz atribua autoridade não comprovada. O script tem somente retorno de verificação de inventário: quando retorna código 0 isso quer dizer que a **lista está coerente**, e NÃO que o provedor esteja habilitado. O `verdict` permanece `HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING`. A suíte `tests/test_aion_p0_h0_provider_32_current_crosswalk_lab.py` cobre perda/duplicação de ocorrência, exceção nova, procedência alterada, promoção indevida de matrícula, falsos recibos, 404/listagens/timeout e confusão de API.

## Avaliação de fornecedor disponível: Twilio Programmable Messaging clássica

A avaliação documentada em `docs/aion/p0-h0-twilio-programmable-messaging-provider-no-go-20261021.md` e resposta do suporte fornecida pelo proprietário **não representam matrícula externa real nem validação de envio**. A API clássica `POST /2010-04-01/Accounts/{AccountSid}/Messages.json` foi descrita sem token nativo de idempotência no create. Consulta posterior por `To/From/DateSent`, eventualmente paginada, serve para investigação — não é prova de que uma mensagem não exista, nem de que nunca será enfileirada/entregue. O cancelamento de mensagens agendadas não implica capacidade universal de desfazer mensagens já enfileiradas. Outras APIs Twilio (por exemplo Conversations/Orchestrator) possuem contratos distintos e **não podem ser usadas como justificativa para este endpoint**.

Para esta API e com as evidências disponíveis, **HARD NO-GO**. Se um fornecedor diferente realmente assegurar `NO_EFFECT_FENCED`, essa garantia precisa ser **demonstrada e auditada por fonte independente**, sem credenciais/raízes privadas controladas pelo próprio executor. Uma string ou JSON alegando `COMMITTED_EFFECT`, `NO_EFFECT_FENCED` ou `provider_verified:true` nunca é prova.

## Protocolo de aceitação externa que ainda NÃO foi executado

As seguintes evidências precisam ser trazidas antes de se cogitar qualquer alteração nos bloqueios de runtime:

1. **Emissor e custódia.** Contrato exato do endpoint; identidade da entidade emissora, conta, escopo e chaves/certificados obtidos por canal independente de administração do AION. Revisor externo confronta enrolment, revogação, epoch e autonomia administrativa. Não basta a chave pública entregue junto do próprio recibo.
2. **Reserva da primeira tentativa.** Número ou token único provido e preservado fora do host antes de qualquer efeito, ligado ao request, digest de intent, operação, nonce e sequência do servidor. Perda de resposta não pode disparar segundo create.
3. **Recibo de resultado causal.** `COMMITTED_EFFECT` só é aceito se autenticamente emitido pelo produtor, ligado à primeira tentativa e verificável contra um head/latest independente. Status de transporte e assinatura sintética não comprovam aplicação do efeito.
4. **Ausência terminal de efeito.** `NO_EFFECT_FENCED` requer contrato que **impeça efeito futuro/tardio** daquela operação; `404`, lista vazia, atraso, timeout ou botão de cancelamento sem cobertura do estado em fila **não satisfazem** esse contrato.
5. **High-water e rollback.** Custódia e leitura autenticadas de epoch/sequence/head monotônico em domínio administrativo independente, cobrindo reinício físico, restauração de SQLite, concorrência, atraso, duplicidade, desordem e perda de resposta. Recibo não pode fazer rollback junto do host e depois ser reapresentado como atual.
6. **HUMAN_OWNER e homologação integral.** Identidade/consentimento real do proprietário com challenge e escopo, revisão independente, todos os 6 P0 fechados, Quality e Security canônicas verificadas sem waiver antes de qualquer Worker, deploy ou gasto operacional.

**Nenhum artefato do presente pacote executa essas seis provas nem autentica um produtor real.** É um mapa dos bloqueios e do que faltaria coletar; a aceitação e homologação exigem fluxo externo real futuro e autorização específica.

## Limitações e política vigente

As correções de SQLite e Saga das PRs Draft continuam em LAB, sem merge. Testes negativos locais podem demonstrar recusa de entradas e boa integridade do banco, mas não resolvem custódia de evidências em domínios externos. A Quality continua com 85 ocorrências abertas, 0/6 P0 homologados, HARD NO-GO, Worker OFF e ZERO_AUTO_RESEND. **Sem novas contas de fornecedor, envio de mensagens, ativação, credenciais ou custos adicionais.**
