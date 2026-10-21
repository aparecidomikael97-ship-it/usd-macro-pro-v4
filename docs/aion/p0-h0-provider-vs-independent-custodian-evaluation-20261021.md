# AION P0/H0 — fornecedores de mensagem ≠ custodiantes independentes (análise documental sem compra)

**Data da revisão:** 21/10/2026. **Somente LAB, sem matrícula, credenciais, APIs reais, primeiro envio, deploy ou merge.**
**Estado:** HARD NO-GO, 0/6 P0 homologados, Worker OFF e ZERO_AUTO_RESEND.

## Resultado da pesquisa: contratos são diferentes

Não existe atalho “escolher um serviço com idempotência = resolver H0”. O problema envolve **duas responsabilidades independentes**, com provas distintas:

- **PRODUTOR (efeito externo)** deve preservar a identidade de cada pedido/primeira tentativa, autenticar sua resposta e comprovar `COMMITTED_EFFECT` ou, quando realmente suportado, garantir `NO_EFFECT_FENCED` mesmo diante de processamento tardio. Dedupe de criação de recurso por prazo limitado não implica efeito downstream exatamente uma vez ou prova terminal de não efeito.
- **CUSTODIANTE (registro externo do primeiro intento e high-water)** deve reservar o intent/nonce antes de qualquer efeito, serializar CAS/sequence, disponibilizar readback autenticado após timeout/rollback e manter controle administrativo separado do executor, incluindo keys, revogação e logs. O mesmo administrador comprometido controlando o banco e a custódia não forma uma âncora independente. Um banco transacional não é por si só prova de recibo do produtor.

### Fornecedores de mensagens — estudo de endpoint, não elegibilidade operacional

| Serviço / endpoint | Recurso documentado | Limitação H0 determinante | Resultado |
|---|---|---|---|
| **OneSignal notifications#create SMS** | `idempotency_key` UUID de **30 dias** para a criação de notificação; documentação SMS usa essa chave | Após 30 dias, reutilizá-la pode criar outro envio. Não há contrato verificado aqui de recibo criptográfico de efeito atrelado ao AION, identidade matriculada, não efeito terminal nem exclusão garantida do envio tardio | **Prioridade apenas para pergunta técnica, NO-GO** |
| **Twilio Programmable Messaging clássica `POST /2010-04-01/Accounts/{AccountSid}/Messages.json`** | Criação de Message, `MessageSid` e busca por ID/listagens conforme documentação; suporte previamente informou que create **não oferece token de idempotência** | Se a primeira resposta se perde antes do `MessageSid`, busca por data/destino não é prova causal negativa, e mensagem em fila pode ser processada tardiamente | **NO-GO** |
| **Twilio Bulk Messaging `POST https://comms.twilio.com/v1/Messages`** | Responde `202 Accepted` com `operationId` para consultar andamento | `operationId` emitido **após** acceptance não equivale a uma chave de dedupe do `POST`. Se a primeira resposta some, AION pode nem possuir o `operationId`. O contrato de NO_EFFECT terminal não foi demonstrado | **NO-GO, contrato independente do clássico** |

Fontes oficiais rechecadas nesta rodada:
- OneSignal: https://documentation.onesignal.com/reference/idempotent-notification-requests e https://documentation.onesignal.com/reference/sms .
- Twilio Classic: https://www.twilio.com/docs/messaging/api/message-resource .
- Twilio Bulk: https://www.twilio.com/docs/bulk-messaging/api/message-resource e https://www.twilio.com/docs/bulk-messaging/overview .

### Custódia independente — duas alternativas condicionais

| Opção | Funcionalidade documentada | Condição adicional ainda não provada | Custo |
|---|---|---|---|
| **Cloudflare Durable Objects SQLite** | Armazenamento transacional e consistente, disponível em Workers Free com backend SQLite; limites atuais documentam até 5 GB no Free | Conta e administração independentes, revogação/custódia de chaves, prevenção de rollback/PITR malicioso, atestado de head assinado e leitura independente por terceiro ainda não preparados. Workers Cloudflare ≠ AION Global Worker | Pode caber no Free para protótipo pequeno, **não é promessa de R$0 nem autorização de provisionamento** |
| **AWS DynamoDB** | Escrita condicional/CAS e `GetItem(ConsistentRead=true)` documentados | Mesmo sem colisões CAS, IAM de administrador/deleção/restore e rollback, assinatura do high-water, auditoria e distribuição das credenciais exigem domínio independente adicional | Free Tier existe em certas condições; preço dependeria de conta, região, modo e uso. **Não há orçamento medido/contratação** |

Fontes oficiais rechecadas:
- https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://developers.cloudflare.com/durable-objects/platform/limits/
- https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html
- https://aws.amazon.com/dynamodb/faqs/
- https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-understanding-billing.html

**Escolha apenas para pesquisa documental:** OneSignal SMS para perguntas do produtor; Cloudflare Durable Objects SQLite para estudar um CAS sob administração realmente separada. Isso não é aprovação técnica de integração, deploy, contratação, criação de conta ou envio, pois falta um emissor de resultado externo verificável.

## Provas exigidas antes de cogitar piloto com efeitos

1. **Identidade/controle:** obter o contrato por endpoint e comprovar canal de assinatura, conta, issuer, escopo e revogação por canal não controlado pelo host AION.
2. **Primeira reserva:** custodiador remoto independente registra intent/nonce/epoch/sequence com CAS único ANTES de dispatch; timeout não cria segunda reserva.
3. **Recibo causal de efeito:** prova do produtor ligada ao request, hash da intenção, nonce da primeira tentativa e referência específica de efeito, comparada com head/latest verificado independentemente.
4. **Não efeito terminal:** sem suporte do fornecedor a fence que **impeça processamento futuro/atrasado**, classificar resultado perdido como `UNKNOWN_BLOCKED`. Nunca usar 404/lista vazia, resultado imediato ausente ou cancelamento parcial.
5. **Rollback físico/high-water:** separar administradores, credenciais e logs; testar perda de resposta, atraso de webhook, cópia antiga de SQLite e restauração/remoção administrativa do custodiante.
6. **HUMAN_OWNER, qualidade e custo:** comprovar identidade real e consentimento por operação, revisar valor real de SMS + tráfego/custos Cloudflare/AWS, monitor de despesas, e fechar TODOS os seis P0 e Quality/Security antes de habilitar Worker.

## Gate de inventário auditável (não runtime)

`docs/aion/evidence/aion_p0_h0_vendor_custodian_two_role_review_20261021.json` contém 3 fornecedores de mensagem, 2 opções de custódia e **6 pares** com `can_dispatch=false`, `can_retry_uncertain_first_attempt=false`, `can_homologate=false`. `tools/aion_p0_h0_vendor_custodian_documentary_gate.py` verifica coerência estrutural, vínculos e guardas explícitas. Seu código de saída 0 significa somente que o **documento de comparação não contradiz a política NO-GO**; não atesta nenhuma conta, assinatura, rede, preço ou custódia externa real.

`tests/test_aion_p0_h0_vendor_custodian_two_role_documentary_lab.py` inclui 28 casos adversariais. A CI read-only executa esses testes e mantém os gates anteriores de inventário 32/32, ledger 85/85 e H0 A79, no Windows e Ubuntu. A Quality canônica original de 588 módulos/6.895 testes e Security A74 365 continuam executadas sem dispensas, com 51 FAIL +34 ERROR conhecidos como referência.

**Proibição permanente nesta etapa:** **HARD NO-GO · ZERO_AUTO_RESEND · Worker OFF · 0/6 P0 homologados · custo novo autorizado R$0.** Nenhum teste prova exatamente uma vez no fornecedor ou autenticidade de chave de produtor ainda não matriculada.
