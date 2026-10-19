# AtlasQuant / AION — P0 Twilio readback / operação incerta, 91 PASS por SO — 19/10/2026

**Veredito:** contrato LAB de leitura e triagem consistente em dois SO, **NÃO autentica fornecedor, NÃO reconcilia efeito real, NÃO autoriza reenvio ou uso do Worker**. Estado global **0/6 P0 homologados; HARD NO-GO**.

## Problema crítico registrado
No Messaging REST API da Twilio, uma primeira requisição `POST /Messages.json` pode criar uma mensagem no fornecedor e o cliente perder a resposta. O uso de `GET /Messages.json` com filtros `To`, `From`, `DateSent` e paginação é útil para investigação mas não constitui prova de não criação. Sem `MessageSid` durável, duas mensagens de mesmo destino/data podem ser indistinguíveis quanto à intenção local. Mesmo quando o fornecedor retorna 0 resultados, `failed`, 404, timeout ou falta de callback, não se comprova no-effect definitivo da primeira tentativa. Callbacks de status não notificam a criação inicial em todos os fluxos. `sent` não equivale a `delivered`; cancelamento disponível para mensagens programadas não é fence universal contra efeitos atrasados.

Resposta anterior do suporte Twilio ao usuário: Message REST API não suporta chave de idempotência para criação (não extrapolar isso a APIs diferentes); consultas por número/data ajudam a procurar mensagens; não é possível recolher mensagem já enfileirada para entrega.

Documentação Twilio consultada:
- https://www.twilio.com/docs/messaging/api/message-resource
- https://www.twilio.com/docs/messaging/guides/outbound-message-status-in-status-callbacks
- https://www.twilio.com/docs/messaging/features/message-scheduling

## Implementação verificável no GitHub
- Base LAB `dd456083c23669c1e84ed54a0945aae06d61a879` da rodada P0 recibos (A118 originais intactos), branch isolada `lab/aion-p0-twilio-readback-triage-20261019`.
- `atlasquant_aion_p0_twilio_readback_triage_lab.py`, commit `725aa0664b3fbea73f337a4ba060fd0ecebd2204`: triagem PURA sem Twilio SDK, API, rede, escrita ou chamada a fornecedor.
- `test_atlasquant_aion_p0_twilio_readback_triage_lab.py`, commit `65513b5e5c53f3e0816eded131ea3b18e1930bd2`: 36 cenários adversariais congelados.
- Contrato de fonte e segurança `docs/aion/AION_P0_TWILIO_READBACK_UNKNOWN_OUTCOME_CONTRACT_20261019.md`, commit `9bb3e2fdb314bf5f54a81498e8038db43395b4c4`.
- Workflow `.github/workflows/aion-p0-twilio-readback-triage-lab.yml`, commit/head `29a096e09e97e68949e67960bef30a070f4765c1`.
- [GitHub Actions #39310583874](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39310583874), **SUCCESS**:
  - Ubuntu job `118258802160`: `P0_TWILIO_ORIGINAL_4_BLOBS_MATCH`; 36/36 novos + 32/32 P0 recibo assinado + 19/19 A37/A83/B2B + 4/4 A110 Outbox ambíguo = **91/91 PASS**.
  - Windows job `118258801708`: mesmos hashes e **36+32+19+4 = 91/91 PASS**.
  - **91 casos distintos; 182 execuções de teste aprovadas.**
- Baseline original conferido por hash nos dois SO:
  `atlasquant_aion_producer_receipt_untrusted_precheck.py` `4fba14585c87591f2195a312600ad30e3f7eafe9`;
  `atlasquant_aion_b2b_external_effect_outcome_receipt_contract_v1.py` `49ad7329ae3311c4878f988a988ddd424a93f967`;
  `atlasquant_aion_execution_outbox.py` `6bad4ee9ba5909bbb49c609a5d3ac3c05c16ab83`;
  `test_atlasquant_aion_a110_outbox_ambiguous_block.py` `2ca086e315ee629026968924bae8e64cafd3a1f1`.

## Contratos verificados e incertezas explícitas
- `NO_MATCH_IS_NOT_NO_EFFECT`: nenhuma mensagem encontrada, ainda **OUTCOME_UNKNOWN**.
- `LIST_INCOMPLETE_NO_MATCH_PROOF`: dados paginados incompletos, não resolver.
- `MULTIPLE_CANDIDATES_AMBIGUOUS`: vários SIDs possíveis, não atribuir efeito arbitrariamente.
- `POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED`: um SID aparente com conta/remetente/destinatário coerentes é só candidato para revisão; NÃO é autenticação.
- Callback sozinho não é prova; ID incorreto, outra conta/remetente/destino, falha de consulta, revogação, `failed`, `canceled` ou 404 não autoriza retry.
- `source_error`, `pagination_complete`, linhas e SID são **fictícios e controlados pelo teste**; até uma paginação marcada `True` não é atestação de completude independente.
- Em TODAS saídas: `state=BLOCKED`, `unknown_outcome_cleared=false`, `current_external_effect_verified=false`, `definitive_no_effect_fence_verified=false`, `provider_readback_authenticated=false`, `automatic_retry_allowed=false`, `resend_authorized=false`, `worker_armed=false`, `external_action_executed=false`.

## Próximo passo para progresso objetivo nos P0
1. Registrar em desenho uma correlação durável **antes de qualquer primeira operação**: owner/tenant/workspace, destino, remetente, operação única, digest de payload, janela, estado e possibilidade de SID no caso de resposta autenticada. A chave de idempotência LOCAL não é aceita automaticamente pelo fornecedor.
2. Definir o procedimento de readback **autenticado e somente leitura** com conta/credenciais de fornecedor, garantias e escopo aprovados pelo proprietário; **não criar/usar credenciais reais aqui**.
3. Se não houver garantia de deduplicação e fence terminal externo, **não projetar auto-reenvio**. Investigação humana pode ser a única alternativa para uma primeira tentativa incerta; decidir qualquer nova ação exige consentimento explícito e análise de duplicação.
4. Auditar antirollback/replay, recibos assinados por emissor comprovado, H0 após reinício, SQLite e regra de check-and-act; execução produtiva ainda bloqueada.
5. Evitar continuar apenas acumulando testes de mocks: próxima evidência de alta qualidade requer contrato de provedor realmente selecionado, custódia e/ou reproduções do Outbox original sob crash/restart sem escrita operacional.

**Sem merge/deploy, Twilio GET/POST, SMS, custos, exposição de dados de clientes, Worker ou autorização de ação. RED M71 e todos os seis P0 seguem abertos.**
