# A178 — Verificação Ed25519 de recibos com chaves fixadas em LAB

**22/10/2026 | PR Draft #1468 empilhada em #1467 | 0/6 P0 homologados | HARD NO-GO**

## Contrato experimental
O arquivo `aion_chat/signed_receipt_lab.py` implementa `PinnedEd25519ReceiptLab`, callback compatível com o `evidence_verifier` de A177, sem carregar chaves reais nem conectar provedores. O chamador fixa *antes da consulta* `key_id -> (issuer, public_key Ed25519)`, revogações, instante de validação e limiar `high_water`.

O verificador aceita somente corpo canônico versionado, com campos obrigatórios e sem campos extras. Checa assinatura Ed25519 sob chave pública previamente fixada, emissor compatível com essa chave, tipo de prova (EFFECT_CONFIRMED / EFFECT_ZERO), `idempotency_key`, hash SHA-256 da decisão completa, proprietário, tenant e workspace, `effect_ref`, `receipt_id`, nonce, número de sequência, vigência máxima 600 segundos, relógio sintético e revogações locais.

Atributos controlados pelo próprio adaptador **não** modificam a lista de chaves confiáveis. Informação ausente, inválida, expirada, adulterada ou falha na assinatura é rejeitada. Uma assinatura de EFFECT_ZERO válida sob a chave fixada pode simular FAILED terminal em LAB, **nunca autoriza reenvio automático**. A autenticação física da ausência externa de efeito está FORA do escopo.

## Evidência de execução
Código e testes exercitados no commit `61f83756140935ba102bd5199a6ae832331c2cc8`.
- [GitHub Actions A178 #39869577629](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39869577629): **Ubuntu 56/56, Windows 56/56**, total 112 execuções. Inclui 16 testes A178 + históricos A177/A176/Outbox/Saga.
- [GitHub Actions SQLite lifecycle #39869577563](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39869577563): **Ubuntu 93/93, Windows 93/93**, total 186 execuções de regressão.
- **Total: 298 execuções aprovadas**, não 298 provas independentes nem homologação de produção. Dependência `cryptography==50.0.2` igual à dependência fixada em `requirements.txt`. Durante execução dos testes a rede foi bloqueada.

### Exemplos conferidos nos dois sistemas
- `A178_VALID_PINNED_LAB_SIGNATURE=CONFIRMED_SYNTHETIC_ONLY`.
- `A178_SIGNED_RECONCILIATION=CONFIRMED_NO_RESEND_LAB`.
- `A178_UNPINNED_KEY=DENIED`.
- `A178_CROSS_SCOPE_REPLAY=DENIED`.
- `A178_REVOKED_KEY=DENIED`.
- `A178_STALE_SEQUENCE=DENIED_WITH_LAB_SNAPSHOT`.
- `A178_SIGNED_EFFECT_ZERO=FAILED_NO_AUTO_RETRY_LAB_ONLY`.

## Contraprovas reproduzidas — NÃO FECHADAS
1. `A178_CALLER_CONTROLS_TRUST_ROOT=FAKE_PROOF_ACCEPTED_NOT_EXTERNAL`: se o chamador puder substituir a lista de chaves fixadas, também pode assinar evidência falsa com sua chave e fazê-la passar pela verificação matemática. **Faltam pinagem fora do controle do adaptador, origem de chaves autenticada, cadeia de autoridade, revogação auditável e testemunha externa**.
2. `A178_ROLLBACK_OF_TRUST_SNAPSHOT=REPLAY_ACCEPTED_NOT_ATTESTED`: restaurar um instantâneo local antigo de `high_water` permite admitir recibo de sequência anteriormente rejeitada. Não há armazenamento monotônico independente, proteção contra rollback físico ou quórum.
3. Validação de recibo positivo não prova entrega real nem autentica quem controla a chave sem cerimônia externa. Recibo negativo assinado tampouco prova, por si, completude ou efeito zero no provedor.
4. Verificador é injetado por callback de A177 e não é o caminho obrigatório nem exclusivo para todas as operações do Worker. Ainda não há vínculo de validade com chaves reais, CNPJ/identidade do proprietário ou autoridades do provedor, nem auditoria de todos os callsites.
5. Campos `receipt_id`, nonce e sequência são vinculados pela assinatura, mas **não estão armazenados numa custódia externa com detecção de replay global**. Assinatura íntegra não impede replay após perda de memória/diário. Banco local apagável/restaurável (A174/A175); sem vínculo ao handle SQLite real (P0-5/6).
6. Quality canônica completa e os P0 externos não foram homologados nesta rodada.

## Próximo gate, antes de considerar P0-2/P0-3 homologáveis
Obter especificação de fornecedor que disponibilize recibos assinados verificáveis, origem de chave pública autenticada, revogação, abrangência dos recibos (especialmente prova de ausência), sequência/custódia monotônica fora do host AION, disponibilidade e recuperação em infraestrutura-alvo. Fazer ensaio independente sem chave privada fornecida pelo mesmo código/adapter; exigir prova verificável de efeitos. **Nenhuma contratação, cadastro, chave real, gasto, merge, deploy ou Worker foram autorizados**.

**ZERO_AUTO_RESEND. HARD NO-GO. P0 0/6.**
