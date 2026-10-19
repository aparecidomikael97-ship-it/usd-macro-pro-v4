# AION — P0 de recibos e resultado incerto: Twilio Message readback sem reenvio

19/10/2026 | Contrato de LAB **somente leitura**, NÃO integra Twilio, NÃO autentica uma conta, NÃO envia mensagens. **HARD NO-GO, 0/6 P0**.

## Evidência documental oficial e resposta recebida
- Twilio Messaging API `Messages`: cria via `POST /Accounts/{AccountSid}/Messages.json`, consulta individual por SID, lista via `GET /Accounts/{AccountSid}/Messages.json`, filtros `To`, `From`, `DateSent`, paginação via `next_page_uri`. A listagem não é um log transacional de uma requisição AION; o usuário do AION não deve inferir ausência de efeito mesmo após uma listagem completa.
- Ao criar recursos, o status inicial é `queued`, ou `accepted`/`scheduled` em Messaging Service conforme modalidade. Status callbacks informam mudanças posteriores e **não cobrem necessariamente a criação inicial**.
- `sent` é diferente de `delivered`; `undelivered` não significa que não houve envio; `failed` isolado não comprova fence de nenhuma tentativa. Cancelamento de mensagens programadas é um caso limitado; cancelar mensagens já na fila ou enviadas não é uma garantia genérica disponível.
- A resposta de suporte da Twilio fornecida ao usuário informou que o recurso de Mensagens não oferece token de idempotência para criar mensagens, que buscas por destinatário/data são opção para investigar uma resposta incerta e que só mensagens programadas podem ser canceladas antes do envio. **Não generalizar isto para TODAS as APIs Twilio**; APIs diferentes podem ter idempotência.
- Fontes oficiais lidas em 19/10/2026:
  - https://www.twilio.com/docs/messaging/api/message-resource
  - https://www.twilio.com/docs/messaging/guides/outbound-message-status-in-status-callbacks
  - https://www.twilio.com/docs/messaging/features/message-scheduling

## Problema que o código resolve em LAB
O contexto inicial de uma única tentativa pode existir de forma durável no AION, mas após `POST` de resultado incerto o AION pode perder a resposta com `MessageSid`. Pesquisar por `From`, `To` e datas pode encontrar **zero, uma ou mais mensagens similares** e a pesquisa pode estar incompleta. Nenhum desses retornos comprova de forma independente que a chamada **original** foi criada ou não criada.

`atlasquant_aion_p0_twilio_readback_triage_lab.py` introduz triagem PURA sobre *fixtures não confiáveis*. Escolhe apenas razões de revisão humana:
- `NO_MATCH_IS_NOT_NO_EFFECT`: não encontramos candidatos; NÃO autoriza nova mensagem.
- `LIST_INCOMPLETE_NO_MATCH_PROOF`: não completou paginação, resultado incerto.
- `MULTIPLE_CANDIDATES_AMBIGUOUS`: mais de um SID plausível, sem correlação unívoca.
- `POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED`: SID plausível sob conta/remetente/destinatário, ainda **sem prova de origem** ou vínculo com a tentativa única.
- `POSSIBLE_MATCH_FROM_INCOMPLETE_LIST`: candidato apesar da paginação incompleta; necessidade de investigação.
- `READBACK_FAILED_OR_UNAVAILABLE`: timeout, autenticação, rate limit, 404 ou erro; não desambigua o efeito.
- `CALLBACK_ALONE_UNTRUSTED`: callback sem autenticação/provider enrollment não é recibo.
- Divergência de SID persistido, conta, telefone, status ou formato -> bloquear e pedir revisão.

Toda saída, mesmo `POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED`, mantém `state=BLOCKED`, `provider_readback_authenticated=false`, `current_external_effect_verified=false`, `definitive_no_effect_fence_verified=false`, `unknown_outcome_cleared=false`, `automatic_retry_allowed=false`, `resend_authorized=false`, `outbox_release_authorized=false`, `writer_armed=false` (representado no código por `worker_armed=false`). Não lê telefone real, não faz GET/POST, não persiste estado.

## Sequência futura de reconciliação a aprovar
1. Pré-tentativa: registro durável de operação única, owner/tenant/workspace, classe de ação, destino/remetente, hashes de payload, hora UTC, idempotency key **LOCAL** (não fingir que Twilio respeita esse token), e estado `PENDING/ATTEMPT_UNKNOWN`, *antes* da chamada externa.
2. Tentar uma única vez quando os seis P0 e guards independentes permitirem; neste momento Worker continua OFF, portanto nenhuma tentativa real é aprovada.
3. Se a resposta `201` e SID autenticados chegarem, persistir evidência. Se houver timeout, desconexão ou falha de persistência da resposta, marcar `OUTCOME_UNKNOWN`, sem repetir.
4. Reconciliar apenas após autenticar credencial/conta do provedor, API readback, SID, paginação, janela, payload/correlation quando possível, timestamps, callbacks **validados por assinatura e origem** e histórico do emissor. Nunca inferir ausência de efeito de `0 resultados`, `404`, `failed` ou de callback ausente.
5. Enquanto não há certeza independente sobre no-effect e fence terminal do fornecedor, manter resultado incerto e **ZERO_AUTO_RESEND**. Revisão humana NÃO deve ser confundida com permissão automática de repetir; eventual nova ação precisa nova intenção/consentimento e análise de risco separada.
6. Real integração exige suporte do provedor/garantias contratuais, custódia de credenciais, testes em sandbox autorizado com dados não reais, P0 originais (identidade, recibo, resultado incerto, reboot, 2 SQLite), auditoria independente e Quality/Security canônicos.

## Limites e privacidade
- `expected` e `observations` são FIxtures sintéticos; até flags de `pagination_complete=true` são do chamador, logo não provam completude real.
- `MessageSid` visto em listagem não é garantia de que corresponde à primeira tentativa incerta; busca por número/data é ambígua.
- O verificador usa valores fictícios `AC...`, `SM...` e `+155501...`; nunca anexar números reais, segredos, conteúdo de mensagens, tokens ou dados de clientes ao GitHub.
- Atualizações não atingem o A118 original nem a branch main. Sem custos, rede Twilio, Worker, merge ou deploy.

Próximo marco objetivo: levantamento de garantias reais da API/provedor e preparação de auditoria de reconciliação com evidência de fonte independente, **sem ativar envios**.
