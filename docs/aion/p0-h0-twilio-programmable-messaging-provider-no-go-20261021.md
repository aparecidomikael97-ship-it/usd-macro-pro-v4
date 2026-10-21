# ADR P0/H0 — Twilio Programmable Messaging: resultados incertos e impossibilidade de prova negativa

**Data da avaliação:** 21/10/2026  
**Decisão para integração AION:** **HARD NO-GO** para efeito externo, operação automática, reenvio após timeout e promoção de `UNKNOWN` a `NO_EFFECT_FENCED`.  
**Escopo:** `POST /2010-04-01/Accounts/{AccountSid}/Messages.json`, isto é, **Twilio Programmable Messaging / API clássica de Messages**, não Twilio Conversations/Orchestrator nem Bulk Messaging/Communications API.  
**Natureza:** avaliação de compatibilidade documental, **sem inscrição de fornecedor, conta, API key, requisição autenticada, teste de integração real, gasto ou envio de mensagem**.

## Evidência de fornecedor utilizada

Em 17/10/2026, o proprietário compartilhou a resposta de um representante da Twilio à consulta sobre timeout, idempotência, cancelamento e comprovação de estado da primeira mensagem. A resposta indicou:

- Em caso de erro ao criar mensagem, consultar a lista de mensagens por destino, origem e data/hora como investigação.
- **A API de Mensagens não oferece tokens de idempotência para a criação de mensagem** (declaração do atendimento para o endpoint em análise).
- Mensagens programadas para envio futuro podem ser canceladas.
- Depois de enfileirada, uma mensagem não pode ser recuperada/cancelada nessa modalidade de API.

A resposta não inclui, no material disponível, identidade verificável, número do ticket, assinatura digital do emissor, compromisso contratual com garantias imutáveis, retenção de registro nem prova de revogação independente. Portanto, ela é **evidência informativa de suporte**, não uma credencial de confiança e não um recibo de execução.

### Documentação oficial (consulta pública 21/10/2026)

1. API clássica de Message resource: https://www.twilio.com/docs/messaging/api/message-resource
   - `POST .../Messages.json` cria uma Message. A resposta normal pode incluir um `MessageSid` gerado pela Twilio.
   - `GET .../Messages.json` lista mensagens, com filtros `To`, `From` e `DateSent`; resultados são paginados. O próprio manual alerta para seguir `next_page_uri`, evitando resultados inconsistentes durante leitura.
   - O filtro `DateSent` corresponde à data do envio e não é uma prova universal de criação: mensagens ainda `accepted`, `scheduled` ou `queued` podem não ter sido enviadas.
   - O material consultado não documenta para **este endpoint** uma idempotency key que garanta devolver a resposta original sem criar nova mensagem após timeout. Esta ausência de documentação **sozinha não prova inexistência**; a indicação explícita veio da resposta de suporte acima.
2. Message scheduling: https://www.twilio.com/docs/messaging/features/message-scheduling
   - Cancelamento por atualização para `canceled` é documentado para mensagem ainda `scheduled` e com SID conhecido, antes da data/hora `SendAt`. Não é um fence genérico para operação de envio imediato que já tenha entrado na fila.
3. Status callbacks e significados: https://www.twilio.com/docs/messaging/guides/outbound-message-status-in-status-callbacks
   - Eventos de `queued`, `sent`, `delivered`, `failed` etc. são sinais positivos ou negativos relativos a uma **mensagem identificada**, não a demonstração de que uma tentativa HTTP que perdeu a resposta não criou nenhuma mensagem.
   - `sent` significa aceitação no fluxo upstream, não garante leitura pelo destinatário.
4. Documentação de idempotência da **API diferente** (Twilio Conversations Orchestrator): https://www.twilio.com/docs/conversations/orchestrator/concepts/async-operations
   - Há `Idempotency-Key` para **operações de configuração deste outro produto**. Não transplantar essa garantia para `Programmable Messaging POST /Messages.json`.

## Contrato de capacidades e decisão H0

| Propriedade necessária para comprovar `NO_EFFECT_FENCED` da primeira tentativa | Evidência atual | Decisão |
| --- | --- | --- |
| ID da primeira tentativa gravado pelo próprio fornecedor antes de possível efeito | Um `MessageSid` pode ser retornado numa resposta recebida; se a resposta se perder, não há identificação inequívoca a partir dos filtros | **NÃO COMPROVADA** |
| Deduplicação atômica por chave do chamador na criação de mensagem após timeout/retry | Suporte respondeu que não há idempotency token no endpoint clássico | **NÃO SUPORTADA para o requisito apresentado** |
| Consulta de histórico completa, monotônica, irrevogável e vinculada à primeira tentativa | Listagem `To/From/DateSent` com paginação; não prova ausência de mensagem ainda não enviada nem snapshot mais recente | **NÃO COMPROVADA** |
| `NO_EFFECT_FENCED` que impeça a primeira tentativa de produzir efeito tardio | Só há cancelamento de mensagem ainda agendada, que exige SID e estado adequado | **NÃO COMPROVADA / NÃO GENERALIZÁVEL** |
| Recibo causal externo autenticado de primeira tentativa | Status/MessageSid podem ajudar se conhecidos, mas não resolvem prova de ausência após resposta perdida | **PARCIAL; SEM HOMOLOGAÇÃO** |
| Identidade e administração separadas de AION, chave fora do executor, revogação latest | Não avaliadas nem verificadas com provedor independente | **NÃO COMPROVADAS** |
| Prova persistente após rollback conjunto host/SQLite/manifesto | Nenhum mecanismo desse tipo contratado e verificado | **NÃO COMPROVADA** |

## Protocolos de incidente permitidos como investigação, não execução

Ao sofrer timeout, conexão interrompida, 5xx ou resultado incompleto depois de **potencial envio**:

1. Conservar a tentativa como `UNKNOWN_BLOCKED`; proibir `send()`, reenvio automático, reconstituição da fila para despacho, liberação da próxima ação do mesmo agregado e marcação `NO_EFFECT_FENCED`.
2. Preservar dados do primeiro pedido se existentes: escopo, referência de operação, `To`, `From`, horário, mensagem e `MessageSid` caso efetivamente recebido; sempre observando minimização/LGPD e sem registrar segredos no relatório.
3. Uma consulta autenticada à lista da Twilio — **somente em fase futura aprovada, nunca por este pacote** — pode auxiliar investigação, incluindo paginação e estados não finais. O resultado vazio **não elimina** a possibilidade de efeito. Dois registros de mesmo destinatário/horário não comprovam qual pertence à tentativa.
4. Status callback autenticado e consulta ao MessageSid podem mostrar que **uma mensagem identificada existe**, mas não fornecem ausência global nem fence tardio.
5. Resolver manualmente apenas com evidência suficiente para a ação e consentimento do proprietário; **nenhuma aprovação manual deve ser reinterpretada automaticamente como autorização genérica para repetir a mesma operação H0**.
6. Se a exigência do produto for "repetir automaticamente e garantir exatamente uma mensagem", **essa combinação de endpoint e evidência é inadequada** até que a Twilio documente e comprove uma alternativa específica com garantias reais, ou que outro fornecedor/protocolo seja selecionado e testado.

## Contraexemplos explícitos

- `POST` cria `MessageSid=SM...`; resposta cai antes de chegar ao cliente; consulta `DateSent` no minuto seguinte retorna lista vazia por status `queued`; repetir o `POST` cria uma segunda mensagem. **BLOQUEAR**.
- Um `404` na leitura de SID incorreto, revogado, fora do escopo ou ainda invisível não prova ausência da mensagem criada por uma tentativa anterior sem SID. **BLOQUEAR**.
- `scheduled` pode ser cancelável **se o SID e o estado forem conhecidos**. Isso não comprova cancelamento da operação de envio imediato em `queued`. **BLOQUEAR interpretação universal**.
- `sent` atesta parte do fluxo upstream, mas não é evidência de leitura, entrega final em todas as redes ou exclusividade da primeira tentativa. **BLOQUEAR promoção indevida**.
- Restaurar Outbox e os próprios logs de consulta ao mesmo snapshot antigo elimina pista local, mas não reverte mensagem já enfileirada fora do host. **BLOQUEAR**.

## Gate de aceitação futura (depende de nova evidência real)

Uma eventual revisão **não** pode ser feita por flags locais `idempotency=True`, prints, simulações assinadas pelo executor ou apenas por link de SDK. Necessita contrato oficial por **endpoint e versão**, cenários de concorrência e timeout testados em ambiente autorizado, idempotência/deduplicação verificável sob retenção/rollback, recibos de produtor genuíno, readback do head mais recente, controle de credenciais e revogação independente, ensaio físico de reinício, autorização HUMAN_OWNER e fechamento dos seis P0 mais Quality/Security canônicas. Até lá, permanecer NÃO APTO.

**Estado do projeto:** 0/6 P0 homologados · HARD NO-GO · Worker OFF · ZERO_AUTO_RESEND · sem merge, deploy, novo contrato, teste pago ou envio.
