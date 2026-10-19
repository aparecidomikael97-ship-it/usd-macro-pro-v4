# AtlasQuant / AION — P0 HUMAN_OWNER — Prova de matrícula assinada (LAB) — 19/10/2026

**Status:** GO-LAB delimitado para verificador de recibo assinado, **NO-GO para matrícula real, integração e operação**; Worker OFF, 0/6 P0 homologados, HARD NO-GO.

## Rastreabilidade
- Fonte A118 original pinada `c62fab663c6349d7320f7843c8d09587c514426b` (original de assinatura V2.24/decisão V2.25/A74 e de ativação intacto).
- Branch `lab/aion-p0-owner-attested-bootstrap-20261019`, derivada da branch anterior do P0.
- Verificador LAB `atlasquant_aion_p0_signed_enrollment_proof_lab.py` commit `11fbfd04f71e9b1832a2a5ff5810d50c7480ff9d`.
- Matriz de 39 casos `test_atlasquant_aion_p0_signed_enrollment_proof_lab.py` commit `b72ec59e0afa1a2733b4c3c9b4e291e3ab65608b`.
- Workflow `.github/workflows/aion-p0-owner-signed-enrollment-lab.yml` commit `a2cd52321a9e62a58121627ee71d56ce1a61da23`.
- Documento de ameaça e limites `docs/aion/AION_P0_OWNER_SIGNED_BOOTSTRAP_ATTESTATION_LAB_20261019.md` commit `ec10e9c47527aad7166e5c361903aab4cd4c8aaf`.
- [GitHub Actions run #39305959906](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39305959906) COMPLETE SUCCESS, head de CI `a2cd52321a9e62a58121627ee71d56ce1a61da23`.
- Ubuntu job `118242985724`: `P0_SIGNED_ENROLLMENT_A118_ORIGINAL_BLOBS_MATCH`; 39 PASS + 27 PASS + 69 PASS + 6/6 unittest PASS.
- Windows job `118242985073`: `P0_SIGNED_ENROLLMENT_A118_ORIGINAL_BLOBS_MATCH`; 39 PASS + 27 PASS + 69 PASS + 6/6 unittest PASS.
- **141 casos distintos**, **282 execuções de casos PASS em dois SO**. Os 39 são novos; 102 eram regressões. Isto não comprova um P0 fechado nem equivale a CI Quality/Security integral.

## Achado técnico e fronteiras
- Um recibo sintético Ed25519 com assinatura verificável por uma raiz pública *fornecida pelo próprio laboratório*, escopo exato, challenge, fingerprint de chave, revisão, identificador de evidência e janela temporal correta resulta em `BLOCKED / P0_SIGNATURE_CONSISTENT_BUT_ISSUER_CUSTODY_UNVERIFIED`. A verificação matemática de assinatura não prova quem matriculou a raiz pública.
- Falsificação de assinatura, chave de emissor trocada, revogação, escopo/cross-tenant, nonce, fingerprint do proprietário, assinatura de payload adulterado, duplicação simulada, rollback de revisão, expirado/futuro, domínio/propósito/intent inválidos, flags trust fabricadas e dados incompletos foram rejeitados no escopo dos fixtures.
- Replay real **NÃO** foi resolvido: `prior_source_revision` e `seen_evidence_ids` são entradas fornecidas no laboratório, não persistidas de forma durável/independente. Prova de não-replay requer registro externo atômico e monotônico.
- `signature_checked=True` indica somente consistência criptográfica relativa à chave fornecida; `independent_issuer_custody_verified`, `human_owner_identity_established`, `owner_enrollment_authorized`, `trust_registry_modified`, `owner_decision_authorized`, `worker_armed` e `external_action_executed` permanecem todos FALSE.
- Não foi utilizada credencial real, hardware, biometria, WebAuthn, chave produtiva, Windows Hello, conta de emissor externo, serviço pago ou conexão à rede dentro dos testes. Nenhum merge ou deploy.
- Os módulos A118 originais comparados com hashes em ambos os jobs: V2.24 `eac8091ed9c80d838e069b16130c65530bde6652`; V2.25 `2d0ae10f33dc4a4cafdc0241074829a7a4d97b57`; trust-root `2d3b102893303751b2faf9a34b069ffb387ebce0`; activation `df43bb4371c784396069f4ede51205b0aa19cc0a`.

## Critérios exatos que faltam para P0 real
1. Procedimento de **bootstrap da identidade humana**, com aprovação expressa do proprietário, evidência out-of-band de vínculo pessoa/conta/dispositivo e auditor externo à solicitação; evitar autoinscrição por ADMIN/chat.
2. Matricular raiz pública de autoridade em custódia não controlada pelo mesmo processo que solicita cadastro e selecionar contrato de atestação/revogação/rotação/recuperação.
3. Vincular posse de credencial original com desafio efêmero e escopo exato; avaliar passkey/WebAuthn (Windows Hello e Android) vs. Ed25519 com chave apropriadamente custodiada. Passkeys não são substitutas automáticas da assinatura Ed25519 V2.24; requerem adaptador e RP ID/origin/UV.
4. Implementar registro atômico de nonces/revisões com antirollback durável, coordenado com a decisão e com o executor; proof stale/replayed não pode passar mesmo depois de reinício/restore.
5. Demonstrar em hardware real após autorização, incluindo troca/revogação, dispositivo perdido, suspensão/offline, recuperação e corrida. Executar Quality + Security completos e auditoria externa.
6. Somente com isso reconsiderar 0/6 P0, autorização do Worker continuará guardada por outros P0 inclusive M71, recibos, resultado incerto, reboot, SQLite.

## Decisão operacional
Manter desenvolvimento em LAB sem gastos. Próxima ação não é acrescentar falsos verdes; é selecionar e validar processo de custódia e matrícula real sob aprovação explícita, quando o proprietário estiver em condições de fazer isso com seu dispositivo. Até lá: HARD NO-GO, Worker OFF, ZERO_AUTO_RESEND, sem merge/deploy.
