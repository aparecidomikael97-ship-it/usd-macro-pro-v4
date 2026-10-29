# A254 — Identidade de evento de negócio assinada (LAB sintético, P0-3)

**Situação: HARD NO-GO, 0/6 P0 homologadas, sem Worker, deploy, merge, custo, uso de provedor ou envio real.**

## Por que precisamos disto

A243 calcula `semantic_effect_digest` com escopo/ação/agregado/conteúdo. Dois eventos de negócio **legítimos e distintos** podem ter exatamente o mesmo conteúdo (por exemplo, duas compras autorizadas idênticas em instantes diferentes); a A243 os confunde. Por outro lado, o mesmo evento com `intent_ref` ou request-ID novo não pode ser reenviado duas vezes. É preciso uma identidade **imutável, assinada pela origem real do evento** e independente do request-ID.

## A254 — contrato técnico restrito ao LAB

- `labs/a254_synthetic_origin_event_identity.py` especifica envelope de identidade de evento com `event_id`, `issuer`, `key_id`, escopo owner/tenant/workspace, ação, agregado, hash do payload, emissão/expiração e assinatura Ed25519 com domínio exclusivo A254.
- Verifica assinatura (quando comparada com uma **chave pública fornecida pelo host para testes**), schema fechado, IDs válidos, campos de escopo/ação/conteúdo, tempo UTC e TTL curto; rejeita qualquer campo extra, inclusive `verified: true`.
- Deriva `event_effect_digest` de identidade autêntica **sintética**, escopo, ação e payload, ignorando o request-ID. Eventos distintos e assinados, mesmo com payload idêntico, produzem identidades distintas; reenvio do mesmo `event_id` ou alteração de payload com mesmo ID é recusado pela tabela de memória do LAB.
- Mesmo envelope aceito **sempre retorna `authorizes_send: false` e `independent_origin_proven: false`**. Não altera a A243 nem aprova `ExecutionOutbox`. A integração negativa com o Outbox exige `UNCERTAIN` e zero adapter.send.
- Ledger local e chave pública fornecida no construtor são **não independentes**. A A254 define um contrato e uma ferramenta de teste, não entrega o provedor confiável.

## 13 ensaios

1. Identidade sintética válida nunca autoriza envio.
2. Eventos distintos, assinados e com mesmo conteúdo não colidem.
3. Mesmo evento repetido com novo request-ID é vetado.
4. Mesmo event-ID com conteúdo alterado é conflito.
5–9. Signatário incorreto, escopo, ação, payload, assinatura, schema, tempo, ID e campos extras são recusados.
10. 60 verificações paralelas do mesmo evento admitem só uma no registro local.
11. Integração negativa no Outbox garante estado UNCERTAIN, sem send nem efeito real.
12. **XFAIL explícito:** host troca a raiz por chave do atacante, e assinatura sintética passa como formato válido. Falta origem de chave independente.
13. **XFAIL explícito:** após reiniciar/reconstituir a tabela local, o mesmo event-ID é aceito outra vez. Falta monotonicidade fora do host.

## Evidências necessárias para homologar P0-3 (não disponíveis agora)

- Origem legítima externa ao host do AION que emita event-IDs imutáveis com políticas claras de criação, cancelamento e reuso.
- Custódia e distribuição das raízes de verificação independente de quem deseja executar o efeito; rotação/revogação auditadas e anti-repin.
- Ledger de não repetição **durável fora da autoridade do host**, com ordenação e fail-closed perante rollback do cliente e do serviço.
- Provar que dois eventos distintos da origem legítima não colidem e que retries do mesmo evento, inclusive após reboot e restauração, são recusados.
- Provar identidade HUMAN_OWNER independente, primeira tentativa e comprovantes de efeito externos (demais P0).

Nenhum novo campo bool `trusted`, `verified`, assinatura autoemitida ou hash local pode substituir essas evidências. A254 deixa explícitos os limites e evita declarar que o formato assinado resolve a origem.

**UNCERTAIN=ZERO_AUTO_RESEND. Trader prioridade, Investimentos preparado, Negócios congelada.**
