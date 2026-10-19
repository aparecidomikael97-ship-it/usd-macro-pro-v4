# AtlasQuant AION — P0 HUMAN_OWNER WebAuthn ES256: 181/181 PASS em dois SO — 19/10/2026

**Veredito:** laboratório criptográfico ES256 comprovado no escopo limitado; **HARD NO-GO, 0/6 P0 homologados**. Um verificador de assertion não autentica sozinho o proprietário. Não ocorreu cadastro real, aquisição de serviço, merge, deploy ou Worker.

## Rastreabilidade dos trabalhos
- Branch isolada: `lab/aion-p0-owner-webauthn-assertion-20261019`, derivada da arquitetura P0 WebAuthn `103e8e5b9dae2c05f97f0394ba3be664eee6cc2b`.
- Implementação laboratorial: `atlasquant_aion_p0_webauthn_assertion_lab.py`, commit `d71791d5f9950d30fc345ba033979234747beef7`.
- Matriz de 40 cenários: `test_atlasquant_aion_p0_webauthn_assertion_lab.py`, commit `21b35a0fb8a4cfaa23495fd2642ebbbe0c3c0405`.
- GitHub Actions: `.github/workflows/aion-p0-owner-webauthn-assertion-lab.yml` commit `0b128ea398c52208eb85cfcced17e61cb1817b80`.
- Documento de limites: `docs/aion/AION_P0_WEBAUTHN_ES256_ASSERTION_LIMITS_LAB_20261019.md`, commit `851ee14e88a55d73102afe80f7695fd9e671c51f`.
- [CI #39308275545](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39308275545), Ubuntu job `118250893746` SUCCESS, Windows job `118250893963` SUCCESS, ambos PIN A118 `P0_WEBAUTHN_ORIGINAL_A118_BLOBS_MATCH`.

## Execuções verificadas nos dois sistemas
| Testes | Ubuntu | Windows |
|---|---|---|
| 40 novos de assertion WebAuthn ES256 | PASS 40 | PASS 40 |
| 39 de recibo assinado sintético | PASS 39 | PASS 39 |
| 27 de envelope de matrícula deny-only | PASS 27 | PASS 27 |
| 69 V2.24/V2.25 e custódia P0 | PASS 69 | PASS 69 |
| 6 A74 guards de autoridade | PASS 6 | PASS 6 |
| **Total** | **181 PASS** | **181 PASS** |

**362 execuções de casos / 181 distintos**, não equivalem a Security e Quality completos nem autenticam pessoa real. Os quatro arquivos originais pinados por blob SHA: `atlasquant_aion_owner_signature_ceremony.py eac8091ed9c80d838e069b16130c65530bde6652`; `atlasquant_aion_owner_decision_record.py 2d0ae10f33dc4a4cafdc0241074829a7a4d97b57`; `atlasquant_aion_trust_root.py 2d3b102893303751b2faf9a34b069ffb387ebce0`; `atlasquant_aion_global_worker_activation.py df43bb4371c784396069f4ede51205b0aa19cc0a`.

## O que foi demonstrado
- Bytes assinados ES256/P-256 (`authenticatorData || SHA256(clientDataJSON)`) sob chave pública de credencial fornecida no fixture; verificação de `type=webauthn.get`, challenge, origin HTTPS única do fixture, rpIdHash, UP/UV, ID/scope da credencial, tempo, contador quando aplicável e rejeição de alterações.
- Origem de teste é `atlasquant.invalid` (sintética, não RP/domínio real); assinatura, chave e challenge efêmeros no runner CI, não Windows Hello ou autenticação mobile real.
- Mesmo a assertion matematicamente válida resulta em `BLOCKED/P0_CRYPTO_VALID_BUT_REAL_OWNER_BOOTSTRAP_UNVERIFIED` e `owner_authenticated=false`; nenhuma ação/alteração de credencial.
- Counter zero e backup flags observados em fixtures não demonstram resistência à clonagem; `used_challenges` é conjunto injetado, não banco durável nem consumo atômico.
- Não foi demonstrado bootstrap out-of-band da chave pública realmente custodiada; não há registro WebAuthn `webauthn.create` nem integração a navegador, sessão, site real, banco, dispositivo, infraestrutura ou usuário legítimo.

## O que falta para autenticação REAL
1. Autoridade independente de matrícula inicial de HUMAN_OWNER, com verificação out-of-band da conta/pessoa, aprovação expressa e custódia fora da solicitação; anti-self-enrollment.
2. Confirmar compatibilidade real PC Windows Hello/passkey e celular Android, navegador, origem HTTPS/RP ID; escolhas não autorizadas e não implementadas.
3. Implementar registro FIDO/WebAuthn com credencial pública previamente matriculada, server challenges persistidos e consumidos atomicamente, política UP/UV, backups e recovery/revogação sob controle independente.
4. Verificação em dispositivos físicos com recuperação/perda, revogação/rollback/crash, tenant, origem, contas múltiplas, concorrência, sinais BE/BS e autenticação de ação crítica distinta de login.
5. Integração sem relaxar V2.24/V2.25, A74, F1/T1, RED M71, demais cinco P0 e Quality/Security. Sem isso, nenhum GO operacional.

## Próxima frente e regra de foco P0
**STOP em novos testes sintéticos adicionais de identidade por repetição**. A próxima evidência de valor depende de decisão explícita do proprietário com seus dispositivos/conta e de custódia independente; não fazer isso silenciosamente. Como o usuário quer priorizar todos os seis P0, seguir no próximo P0 que permite trabalho em código/CI sem dispositivo (autenticidade de recibo/resultado incerto/reinício/SQLite), preservando a frente do HUMAN_OWNER aberta. Não abrir features não P0.

**Estado:** 0/6 P0 homologados; Worker OFF; ZERO_AUTO_RESEND; sem merge/deploy/gasto; HARD NO-GO.
