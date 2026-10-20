# AION P0 — comparação de produto: Twilio Classic vs Bulk Messaging API beta

**Data da verificação:** 20/10/2026. **Estado:** NO-GO para envio automático, matrícula de produtor e reenvio em resultado incerto.  
**Escopo:** documentação pública oficial; nenhuma conta/credencial, requisição à Twilio, Message SID real, cobrança ou envio foi usado.  
**Complementa:** [auditoria Twilio Classic](AION_P0_TWILIO_READONLY_EVIDENCE_AND_RFI_20261020.md) e [matriz 23/8/1](AION_P0_32_EXTERNAL_PRODUCER_EVIDENCE_MATRIX_20261020.json).

## Descoberta não contemplada no primeiro estudo

**Twilio Bulk Messaging API** entrou em *Public Beta* em 06/05/2026; suporta WhatsApp além de SMS/MMS/RCS e pode aceitar até 10.000 destinatários por envio. O recurso é **diferente** da API tradicional `/2010-04-01/Accounts/{AccountSid}/Messages.json`.

- **Classic:** resposta de criação normalmente inclui um `Message SID` `SM...`, depois consultado por `GET`. Se o POST é incerto sem SID, o filtro por To/From/DateSent ajuda a procurar candidatos, mas não impede uma execução tardia nem garante unicidade de operação.
- **Bulk Beta:** `POST https://comms.twilio.com/v1/Messages` é **assíncrono** e responde `202 Accepted` com `operationId`; `GET /v1/Messages/Operations/{operationId}` consulta a operação. Um `operationId` retornado permite rastrear o conjunto de mensagens. `messageId` de Bulk não é o mesmo que Message SID clássico; uma mensagem pode ter **várias tentativas por canal**, cada uma com SID. **Perder a resposta 202** significa que o cliente pode ficar sem `operationId`.
- **Não confundir termos:** `202 Accepted` significa operação aceita para processamento assíncrono, **não** que todos os efeitos tenham sido executados/delivered. `COMPLETED` é estado agregado, a ser investigado por mensagens e tentativas. `CANCELED` não prova terminal `NO_EFFECT_FENCED` para postagens desconhecidas e operações paralelas.
- **Tratamento de erro:** a referência de `POST /v1/Messages` descreve `429` com orientação `Retry-After` e diz que `500` não deve ser reenviado. Mesmo que um provedor recomende retry em certos erros de **um endpoint**, o AION não pode considerar isso autorização suficiente para repetir uma ação depois que sua condição causal é incerta; **ZERO_AUTO_RESEND**.
- **Idempotência:** buscas na documentação do endpoint Bulk `Send Messages` **não estabeleceram** um `Idempotency-Key` com escopo/TTL/igualdade de payload aplicável a esse POST. Há **outras** APIs Twilio que documentam idempotência de operações de Configuração em Conversations (24h por conta/região) e Insights async; isso **não** pode ser herdado pelas APIs Messaging. Um identificador de operação retornado após aceite não é um token de deduplicação enviado antes do pedido.
- **Estabilidade:** Bulk Messaging está em **Public Beta, sem SLA**, com funcionalidades e documentação sujeitas a alteração. Não é possível promovê-lo a base de H0 homologado apenas pelo recurso assíncrono.
- **Autenticidade:** status callbacks podem correlacionar `operationId`, `messageId` e SIDs de tentativas. Essa correlação não substitui raiz de confiança externa, verificação de origem do produtor, garantia antirollback nem atestado de efeito com binding ao intent digest original.
- **Custódia/dados:** logs e tags devem obedecer LGPD e minimização; não usar números, nomes, conteúdo de mensagens, AuthTokens, API Keys ou informações de cliente em testes.

## Matriz de comparação

| Evidência | Classic Messages | Bulk Messaging Beta | Impacto para AION |
| --- | --- | --- | --- |
| Identificador após resposta bem-sucedida | `SM...` | `operationId`, `messageId`, SIDs de tentativas | Ajuda a investigar, não supre `COMMITTED_EFFECT` |
| Sem resposta após POST | SID pode ser desconhecido | `operationId` pode ser desconhecido | **Não reenviar automaticamente** |
| Consulta da operação | GET por SID / listagem com filtros | GET por `operationId` + mensagens/recibos por recursos | Não é `NO_EFFECT_FENCED` |
| Fan-out | Uma mensagem por POST típico | Até 10.000 destinatários por operação | Reenvio duplicado pode multiplicar efeitos |
| Idempotência atômica de CREATE por chave da aplicação | Não estabelecida | Não estabelecida | AION mantém HARD NO-GO |
| Cancelamento/garantia de ausência terminal de efeito | Cancelar agendamento identificado antes de `SendAt` | Estado `CANCELED` documentado; fence universal não estabelecido | Não inferir proteção contra efeito tardio |
| Condição do produto | API clássica documentada | Public Beta, sem SLA | Não usar Beta como garantia H0 |
| Garantia de recibo causal autenticado pelo produtor | Não comprovada para AION | Não comprovada para AION | 8 ERROR Saga ainda abertos |

**Conclusão formal:** `GO-LAB` apenas para modelagem de consultas e avaliação de capacidade; `NO-GO` para efeitos reais e retry automático. Em nenhum dos produtos consultados foi comprovado o conjunto **matrícula confiável + COMMITTED_EFFECT independente + NO_EFFECT_FENCED terminal**. A ausência de prova nas páginas públicas **não é afirmação de inexistência universal**; exige confirmação contratual por operação e testes com evidência real sob autorização futura.

## Fontes primárias específicas (produto correto)

1. Twilio Bulk Messaging Public Beta, **sem SLA**: https://www.twilio.com/docs/bulk-messaging
2. Anúncio em 06/05/2026: https://www.twilio.com/en-us/changelog/bulk-messaging-api---public-beta
3. Bulk Messages `POST /v1/Messages`, responses/status/error handling: https://www.twilio.com/docs/bulk-messaging/api/message-resource
4. Bulk Operations `GET /v1/Messages/Operations/{operationId}`: https://www.twilio.com/docs/bulk-messaging/api/operation-resource
5. Operation tracking (operationId/messageId and SM/MM attempts): https://www.twilio.com/docs/bulk-messaging/operations-and-message-tracking
6. Classic Messages POST/Fetch/List: https://www.twilio.com/docs/messaging/api/message-resource
7. Classic scheduled cancel: https://www.twilio.com/docs/messaging/features/message-scheduling
8. Twilio Conversations Configuration idempotency **only for that API**: https://www.twilio.com/docs/conversations/orchestrator/concepts/async-operations
9. Twilio Insights async idempotency **only for that API**: https://www.twilio.com/docs/api/insights/v3/twilio-insights-async/create-query-job

## Adendos ao RFI (Twilio precisa responder por endpoint e produto)

1. A versão `POST https://comms.twilio.com/v1/Messages` suporta algum header de idempotência **documentado e obrigatório pelo executor real**? Qual nome, retenção, escopo, parâmetros e comportamento de payload divergente, timeout e concorrência?
2. Com resposta `202` perdida **antes de saber `operationId`**, existe uma leitura única, consistente e não-mutante por chave **previamente enviada** que encontre a operação? Se não, confirmar explicitamente.
3. Um `COMPLETED` de Bulk garante o que exatamente em cada submessage e tentativa/canal? Qual o efeito relevante e qual atestação de origem, binding e monotonicidade é fornecida?
4. O estado `CANCELED` de Operation/Message Bulk impede irrevogavelmente todos os envios já agendados e tentativas atrasadas? Qual mecanismo atômico faz o fence no ponto de execução? O que acontece com fallback múltiplo?
5. Quais políticas e garantias de serviço são aplicáveis ao Beta (sem SLA), incluindo capacidade de migrar futuramente para GA com mudança de semântica?
6. `429 Retry-After` e `500` têm contratos de idempotência diferentes para Bulk POST? A recomendação do endpoint comprova ausência de criação antes de qualquer novo POST? Fornecer comportamento depois de timeout/network reset.

## Testes LAB

- [24 cenários em JSON](AION_P0_TWILIO_CLASSIC_BULK_CROSS_PRODUCT_MATRIX_20261020.json), incluindo 6 Classic, 16 Bulk Beta e 2 exemplos de **outros** produtos Twilio que não podem emprestar o contrato de idempotência.
- `tests/test_aion_p0_twilio_classic_bulk_contract_lab.py`: 14 testes de integridade, escopo, semântica de `202`, fan-out, callbacks e barreiras reais do Outbox/Saga com dados `operationId`/`messageId` exclusivamente fictícios.
- Todas as combinações mantêm `auto_resend_permitted=false`, `no_effect_fence_verified=false`, `case_closes_canonical_quality_error=false`; os 32 ERROR Quality permanecem `OPEN_NOT_WAIVED`.

**Sem endpoint acessado; nenhum token ou número usado; sem Worker, merge, deploy, gastos ou produção.**
