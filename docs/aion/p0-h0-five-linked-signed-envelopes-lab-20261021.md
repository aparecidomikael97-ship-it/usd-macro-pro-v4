# AION P0 H0 — cinco documentos Ed25519 vinculados (LAB)

Data: 21/10/2026. Isolamento: somente branch/PR Draft sobre a PR #1382; **não integrado ao Worker, Saga, Outbox nem `main`**.

## Escopo

Novo `atlasquant_aion_p0_h0_linked_five_envelopes_lab.py` combina duas verificações anteriores, ambas exclusivamente sintéticas:

1. Matrícula assinada com as chaves públicas de `reservation_signer` e `readback_witness`;
2. Instantâneo de revogação assinado e associado por SHA-256 à matrícula;
3. Desafio/nonce assinado por chave sintética do custodiador e vinculado ao SHA-256 da revogação;
4. Reserva assinada por **exatamente a chave registrada para `reservation_signer`**, não por uma chave avulsa apresentada com o recibo;
5. Readback assinado pela chave registrada de `readback_witness`, associado ao desafio assinado, ao hash da reserva e aos campos de cabeça do histórico.

Após a verificação matemática dos três primeiros envelopes sob chaves **fornecidas pelo próprio chamador**, o verificador **deriva internamente** as chaves dos dois documentos finais a partir da matrícula. Compara os IDs de chave, issuer, scope, request, intent, attempt_nonce, challenge_nonce, SHA-256 de reserva, epoch, seq, head_digest e version_id. Bloqueia reaproveitamento de uma mesma chave entre raiz/custodiador/testemunhas e ordem temporal incompatível dos recibos segundo o relógio **também fornecido pelo chamador**.

A época das chaves de registro e a época do histórico são grandezas diferentes: não se presume que coincidam. A sequência da cabeça, entretanto, deve coincidir com a declarada no desafio assinado, e a versão/época esperadas continuam somente declarações do chamador sem fonte externa autenticada.

## Demonstração de ameaça

Mesmo cinco assinaturas matematicamente válidas são insuficientes para comprovar que:

- Os emissores são independentes do AION;
- A matrícula e a revogação constituem a versão **mais recente** de um registro externo;
- O desafio foi gerado aleatoriamente, persistido e consumido de forma atômica fora do executor;
- O relógio é confiável, o head é efetivamente o último e não houve rollback duplo;
- O fornecedor confirmou `COMMITTED_EFFECT` ou `NO_EFFECT_FENCED`;
- A identidade e o consentimento do HUMAN_OWNER foram autenticados;
- Não existe controlador administrativo oculto compartilhado.

Um adversário que **controle as chaves de raiz e custodiador fornecidas pelo chamador** pode criar uma cadeia coerente e obter `synthetic_five_envelopes_linked_lab=True`. Isso significa **somente consistência criptográfica simulada**. Em todos os casos o estado é `HARD_NO_GO`; `allowed=False` e todas as flags de autoridade falsa. Também não existe anti-replay durável: passar duas vezes o mesmo pacote pode produzir a mesma constatação matemática sem nunca abrir uma permissão.

## Matriz e critérios

- 44 novos casos adversariais: chave trocada apesar de assinaturas válidas, IDs trocados, papel revogado, desafio diferente no readback, seq/head incompatíveis, epoch/versão, assinaturas adulteradas, nonce antes da reserva, dados hostis, replay e pacote totalmente autocriado.
- Regressão sobre 56+38+34+55+28+20+64+8 testes anteriores = **347 métodos selecionados por sistema**, se todos forem executados.
- CI Ubuntu e Windows em workflow read-only, `permissions: contents: read`, `persist-credentials: false`; worker e efeitos externos desabilitados.
- A aprovação da CI específica do commit não homologa P0; Quality/Security canônica sem dispensas devem ser reexecutadas no HEAD final. Baseline anterior: **6.562 Quality, 52 FAIL, 34 ERROR**; Security A74 365 PASS; H0 A79 64 PASS.

## Próximo bloqueio real

Matrícula **fora da máquina e conta** e custódia de chaves confiáveis; identidade/controle de administradores e recuperação; readback externo autenticado de versão mais recente; nonce monotônico consumido em armazenamento realmente independente; recibo originário do fornecedor e recuperação de UNKNOWN; ensaio físico de rollback; revisão de todos os seis P0. O projeto **não autoriza compra nem provisioning de serviços** com este LAB.

**0/6 P0 homologados · HARD NO-GO · Worker OFF · ZERO_AUTO_RESEND · sem merge, deploy, chamada externa, contratação ou gastos.**
