# AION P0 — recibo de produtor assinado (LAB somente), 19/10/2026

**Este artefato NÃO autentica um fornecedor real.** É uma verificação matemática Ed25519 com chaves e provas inteiramente sintéticas. Regra fixa em todos os caminhos: `state=BLOCKED`, `automatic_retry_allowed=false`, `producer_effect_confirmed=false`, `producer_no_effect_fence_confirmed=false`, `external_action_executed=false`.

## Evidência e fronteiras
- `atlasquant_aion_producer_receipt_untrusted_precheck.py` original A37 faz checagem sintática e nega até recibos plausíveis. Esse bloqueio está correto e fica intacto.
- `atlasquant_aion_b2b_real_receipt_authenticator_contract_v1.py` descreve requisitos, mas não implementa verificação real.
- Criado `atlasquant_aion_p0_signed_producer_receipt_lab.py` isolado: confere assinatura Ed25519 sobre bytes canônicos e um domínio separado; vincula owner, tenant, workspace, host, emissor, conta do produtor, chave e versão, action, digest de intenção, idempotency key, attempt, epoch, sequência e head de witness, nonce, ID de recibo, effect/fence ref e janela temporal.
- `POSITIVE_COMMITTED` e `NEGATIVE_NO_EFFECT_FENCED` são tipos assinados distintos; alterar tipo ou ref invalida assinatura. O verificador não recebe `OUTCOME_UNKNOWN` como prova terminal.
- Mesmo assinatura válida retorna `P0_CRYPTO_CONSISTENT_EXTERNAL_EFFECT_UNVERIFIED`: fonte de chave de teste/escopo/counter/IDs usados são entradas controladas pelo mesmo ensaio.
- Negativo de produtor tem requisito EXTRA que assinaturas não resolvem: garantia do fornecedor de que não há efeito já emitido, pendente ou que poderá ocorrer tardiamente; uma mensagem de "não encontrado" ou apenas status local FAILED não comprova isso. Reenvio automático continua ZERO.

## Lacunas de P0 antes de qualquer integração real
1. Emissor/provedor existente realmente selecionado e conta autenticada, chave pública com custódia independente, revogação de credencial e prova de escopo tenant e host; **não presumir Twilio ou outro fornecedor como selecionado**.
2. Prova de efeito emitida pelo **próprio produtor/fornecedor**, com ID de operação e resultado consultável, autenticação de webhook ou recibo; comprovante local assinado ou `ACK` não é suficiente.
3. Para prova negativa, ***fence garantido pelo produtor*** com semântica de no-effect definitivo, cobrindo fila, atraso, envio com ACK perdido e tentativa incerta; se fornecedor não garante, manter `OUTCOME_UNKNOWN` e não reenviar.
4. Entidade separada mantém nonce/sequence/epoch/head monotônico e imune a rollback, com consumo durável atômico, relógio confiável e audit trail; chamadas repetidas não retornam permissão.
5. Testar concorrência, TOCTOU, crash/restart, rollback, credencial revogada, mudança de conta, múltiplos tenants, erro 429/5xx/timeout e status divergentes.
6. Integrar apenas com revisão independente, histórico Quality/Security e autorização de proprietário; nunca inverter o gate do Worker porque 32 testes sintéticos estão verdes.

## Próximo ganho técnico
Preparar **ensaio do contrato de fonte de verdade e de reconciliação de efeito incerto** com leitura somente e um fornecedor concreto escolhido pela viabilidade; isso não depende de gasto até haver contato/provider aprovado. Em paralelo estudar recibos reais disponíveis sem enviar mensagens ou executar efeitos. Se uma API não possui token de idempotência ou fence terminal, desenhar fluxo humano manual e manter no-resend. O objetivo é fechar P0, não aumentar contador de testes sintéticos.

**0/6 P0 homologados; Worker OFF; sem merge/deploy/gastos; HARD NO-GO.**
