# AION Unified Core V2.1 — hardening, adapters e continuidade

## Base

Esta etapa permanece stacked sobre a Draft PR #550, branch `integration/aion-unified-core-v2-20261003`.

Ela continua separada da PR #551 da interface. Não liga o Chat AION ao app principal, não faz merge, deploy, chamada de provider externo, transação financeira nem trade real.

## Bloco V2.1A — Chat, Checkpoint Mestre e Biblioteca

### Browser reduced-motion

O contrato Chromium foi estabilizado para o fluxo em que `chat.js` reconstrói os cards `.conversation` com `replaceChildren()`. O teste re-resolve o elemento conectado e usa retry nativo do Playwright sem afrouxar o contrato:

- `prefers-reduced-motion: reduce` confirmado;
- elemento anexado;
- `transition-duration: 0s`;
- `transform: none`.

O gate específico executa o browser cinco vezes em sequência.

### Chat -> Checkpoint Mestre

`atlasquant_aion_chat_checkpoint_adapter.py` implementa o bridge sobre o `CheckpointCoreStore` existente:

- scope owner/tenant/workspace validado;
- export canônico com digest;
- nenhuma gravação automática;
- receipt de aprovação obrigatório e vinculado ao digest;
- replay para payload diferente rejeitado;
- repetição idêntica idempotente;
- conversa não vira decisão ou fato oficial automaticamente;
- Core recebe apenas âncora de export aprovado;
- nenhuma promoção automática para memória.

### Chat -> Biblioteca AION

`atlasquant_aion_chat_library_adapter.py` mantém anexos como dados não confiáveis:

- quarentena por padrão;
- hash, tamanho, nome e MIME real validados;
- PDF reutiliza pipeline existente;
- TXT entra somente como documento staged/reviewável;
- nenhum index, review, provider ou memory promotion automático;
- retrieval permanece isolado por tenant/workspace.

O bridge agora também rejeita índices forjados como "revisados" quando o schema, estado do documento, estado da passagem ou vínculo documento/passagem não satisfazem o contrato real da Library.

## Bloco V2.1B — continuidade do núcleo

### Unified Request Event Journal

`atlasquant_aion_unified_journal.py` cria uma trilha específica do lifecycle do request unificado, separada do journal de eventos de mercado.

Características:

- scope owner/tenant/workspace/request;
- cadeia de hash por evento;
- revision/head digest verificáveis;
- metadata limitada e secret-redacted;
- detecção de tamper e replay cross-tenant;
- journal não autoriza execução, não promove memória e não grava Checkpoint Mestre.

### Durable / Recovery

`atlasquant_aion_unified_durable_bridge.py` liga o preflight unificado ao `atlasquant_aion_durable_tasks.py` existente sem criar um segundo motor de tarefas.

O handoff registra o preflight já concluído e preserva a continuação como `PAUSED`, `WAITING_APPROVAL` ou `BLOCKED`.

Recovery:

- exige journal íntegro e mesmo request/scope;
- respeita digest do checkpoint e optimistic revision;
- restaura cursor/contexto somente;
- não executa próximo passo;
- não limpa aprovação pendente;
- não faz restore externo automático.

### Matriz dos 8 papéis

`atlasquant_aion_role_authority.py` formaliza os oito papéis oficiais:

1. Orquestrador / Núcleo;
2. Arquiteto / Estrategista;
3. Guardião / Auditor;
4. Prime / Execução;
5. Shadow / Pesquisa e Triagem;
6. Sentinel / Monitoramento;
7. Comercial / Leads e CRM;
8. Educador / Treinamento.

Todos continuam responsabilidades do mesmo AION Core. Nenhum papel pode sozinho:

- conceder aprovação crítica;
- executar ação externa sem gates;
- promover memória automaticamente;
- gravar checkpoint automaticamente;
- mergear `main`;
- deployar produção;
- gastar dinheiro;
- ler credenciais;
- habilitar trade real.

Aprovação crítica permanece com o proprietário humano. Mesmo uma aprovação humana explícita não equivale, por si só, à execução: o downstream execution gate continua obrigatório.

### Truth / Knowledge mapping

`atlasquant_aion_truth_mapping.py` reconcilia, de forma fail-closed, os estados do evidence engine com os estados da Biblioteca.

Regras centrais:

- `VALIDATED + SUPPORTED` pode ser mapeado a `CONFIRMED`, sem ganhar autoridade de decisão e sem promoção automática de memória;
- `CONFLICTING`, `STALE`, `QUARANTINED`, `REVIEW_REQUIRED` e `REJECTED` nunca viram fato operacional confirmado;
- conflito preserva retrieval para revisão quando permitido, mas o runtime recebe `UNKNOWN`;
- conhecimento revisado ainda passa por quarantine/policy antes de memória.

### Aprovação estritamente booleana

O runtime unificado agora considera aprovação somente quando `approved is True`. Valores truthy como `"yes"`, `"true"` ou `1` não liberam o gate nem entram como approval receipt.

## Testes adversariais V2.1

`test_atlasquant_aion_unified_hardening_v21.py` cobre:

- tamper da cadeia do journal;
- replay cross-tenant;
- metadata secreta;
- checkpoint drift;
- recovery com journal alterado;
- preservação de `WAITING_APPROVAL`;
- fake approvals truthy;
- autoridade crítica dos oito papéis;
- truth mapping conflitante/stale/quarentena/rejeitado;
- índice revisado forjado;
- retrieval conflitante sem promoção para fato confirmado.

## CI

Os gates específicos do AION aceitam a branch-base da #550 enquanto esta PR stacked está em revisão:

- AION Unified Core;
- AION Core Security Gate.

Os workflows globais `Quality tests` e `AtlasQuant - Release Readiness` permanecem `main`-only, preservando o contrato de produção. O Quality completo será exercitado quando a cadeia chegar à integração normal contra `main`.

## Limites remanescentes

Continuam fora desta revisão:

- provider runtime real;
- ligação do Chat AION à UI principal;
- merge/deploy;
- execução externa;
- trade real;
- ação financeira.

Nada nesta etapa executa ação externa, provider real, trade, merge ou deploy.
