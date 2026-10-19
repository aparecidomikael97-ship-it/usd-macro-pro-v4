# AION P0 / HUMAN_OWNER — WebAuthn assertion ES256, prova criptográfica em LAB

19/10/2026 | PROTÓTIPO NÃO AUTORIZANTE | **0/6 P0 homologados, HARD NO-GO**

## Por que este ensaio
A assinatura V2.24 Ed25519 não implementa WebAuthn. As últimas rodadas P0 validaram envelopes de matrícula, mas não uma *assertion* assinada no protocolo. Este laboratório adiciona um ensaio criptográfico ES256 de assertion com credencial temporária, não uma autenticação operacional.

## Boundary experimental
`atlasquant_aion_p0_webauthn_assertion_lab.py` recebe:
- `assertion`: `credential_id`, bytes originais do `clientDataJSON` codificados em base64url, `authenticatorData` e assinatura DER ECDSA P-256.
- `expected`: credencial, owner/tenant/workspace, challenge base64url de 32–64 bytes, RP ID e origem HTTPS **exatos**, janela e tempo de análise.
- `pinned_credential`: credencial pública SEC1 ES256, status e contador armazenado (todos INJETADOS no LAB).
- `used_challenges`: conjunto sintético de challenges previamente vistos, NÃO persistido.
Verifica bytes assinados `authenticatorData || SHA256(clientDataJSON)`, RP-ID hash, flags UP/UV, tipo `webauthn.get`, origin exata, challenge, ID/escopo da credencial e assinatura ES256. Rejeita extensões não suportadas, `crossOrigin=true`, dados extras de authData, malformação, troca de chave e contador não monotônico quando ambos não zero. Counter 0 / passkeys sincronizadas podem ser válidos para diagnóstico, mas **não comprovam ausência de clonagem**.

O domínio `atlasquant.invalid` é puramente sintético para teste. NÃO registra RP ID, origem, domínio ou passkey real. Esse verificador não implementa attestation/registration `webauthn.create`, CBOR/COSE do registro, token binding, cross-device flows nem extensões WebAuthn; não é biblioteca WebAuthn de produção.

## Segurança: coerência != identidade real
Mesmo o caso matematicamente íntegro retorna:
`state=BLOCKED; reason=P0_CRYPTO_VALID_BUT_REAL_OWNER_BOOTSTRAP_UNVERIFIED`;
`signature_checked=true`; **owner_identity_verified=false, owner_authenticated=false, independent_enrollment_verified=false, real_device_custody_verified=false, nonce_durably_consumed=false, counter_atomically_persisted=false, owner_decision_authorized=false, worker_armed=false, external_action_executed=false.**

Os dados `expected`, `pinned_credential` e replay `used_challenges` são controlados pelo ensaio. Nenhuma autoridade real escolheu/guardou a chave pública, nem houve matrícula out-of-band do proprietário. Uma assertion assinada apenas comprova controle relativo à chave sintética fornecida.

## Plano de próximos passos com STOP do P0 físico
1. Guardar 40 casos adversariais e regressão de 141 casos anteriores em dois sistemas; registrar resultado real apenas após GitHub CI. Não alterar `atlasquant_aion_owner_signature_ceremony.py`, `atlasquant_aion_owner_decision_record.py`, guards A74 ou executor.
2. **Parar de acrescentar mais testes sintéticos de identidade sem um novo requisito comprovado**. O próximo ganho real exige decisão explícita sobre RP ID/origem, dispositivo compatível, política de passkey sincronizada versus dispositivo exclusivo, custódia da raiz inicial e recuperação/revogação independente.
3. Com o proprietário em posse do PC e celular, checar versões/compatibilidade com aprovação, sem coletar PIN/biometria/segredos no chat; só então avaliar teste físico de passkey, bootstrap out-of-band e adaptação auditada.
4. Enquanto a decisão/hardware estiver pendente, manter P0 de identidade aberto e avançar no **próximo P0 que admite avanço exclusivamente em código e testes** (recibo verificável/resultado incerto/reboot/SQLite), sem perder rastreabilidade.
5. A integração real requer revisão independente, verificador de credencial realmente cadastrada, nonce persistido e consumido atomically, trust anchor separado, audit logs, Quality/Security canônicos, teste de recuperação e decisão explícita.

Worker OFF; HARD NO-GO; sem merge/deploy; sem contratação, custo, credencial real ou aprovação de ação.
