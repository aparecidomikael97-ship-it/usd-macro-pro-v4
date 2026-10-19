# ADR LAB — P0 HUMAN_OWNER: matrícula com passkeys/WebAuthn e custódia independente

**Estado:** PROPOSTA TÉCNICA / NÃO APROVADA PARA OPERAÇÃO, 19/10/2026. **0/6 P0 homologados, HARD NO-GO**. AION Worker desligado. Nenhuma credencial, domínio, serviço, gasto, integração ou trust root foi matriculado neste ADR.

## 1. Decisão proposta — não é autorização

Preferir uma experiência baseada em **WebAuthn/passkeys nos dispositivos já existentes** (PC com Windows Hello, se compatível, e Android com passkey), como *opção a avaliar*. Não utilizar o texto do chat, nome da conta, e-mail, QR code isolado, biometria relatada por API não confiável ou uma chave pública fornecida pelo usuário solicitante como prova suficiente da identidade/custódia.

- O login cotidiano deve permitir a experiência "AION reconhece o proprietário" **após** matrícula inicial e prova de posse verificável, sem pedir pareamento manual a cada sessão.
- **Ações críticas** continuam exigindo nova confirmação explícita, vinculada à operação, via desafio de uso único; login não é assinatura de autorização.
- **Passkey sincronizada** melhora disponibilidade entre PC e celular, mas NÃO prova que a credencial é presa a um único dispositivo, nem é equivalente a uma chave de segurança com custódia física. Evitar declarar "device-bound" sem atestação verificável.
- WebAuthn **não substitui automaticamente** a assinatura Ed25519 V2.24 e a decisão V2.25 existentes: projetar adaptador com tipos/domínios/políticas distintos, sem converter estado de login em V2.24 `READY`.
- Não concluir que Windows Hello ou Android em uso pessoal já estão disponíveis/compatíveis sem inventário real e consentimento específico.

### Base pública consultada
- W3C Web Authentication Level 3 Recommendation, 25/08/2026: https://www.w3.org/TR/2026/REC-webauthn-3-20260825/
- Microsoft: Windows WebAuthn APIs / Windows Hello: https://learn.microsoft.com/en-us/windows/security/identity-protection/hello-for-business/webauthn-apis
- FIDO Alliance: passkeys sincronizadas versus device-bound e recuperação: https://fidoalliance.org/white-paper-replacing-password-only-authentication-with-passkeys-in-the-enterprise/

## 2. Três fronteiras que NÃO podem ser confundidas

**B0: matrícula de confiança da pessoa/conta (ainda ausente).** A primeira credencial não pode atestar a si mesma. AION exige um procedimento de bootstrap com comprovação de controle do proprietário em um canal **fora** do próprio pedido de cadastramento e com evidência independente. Uma passkey demonstra posse e presença/verificação do usuário *relativas a uma conta já previamente confiável*; não prova sozinha a identidade civil ou quem é o dono legítimo do ecossistema.

**B1: autenticação (adaptador ainda não implementado).** Dado um registro de credencial confiável já matriculado, validar WebAuthn (RP ID, origin, challenge emitido pelo servidor, assinatura, credential ID e chave previamente cadastrada, user verification obrigatório, TTL/nonce antirreplay, flags/backup-state e revogação). Somente contexto autenticado, não habilitação do Worker.

**B2: aprovação por ação e evidência de execução (continua bloqueada).** Mesmo B0+B1 não concedem F1/T1, verificação externa de fornecedor, aprovação F2, autenticidade de recibos, reinício H0, SQLite, proteção de resultado incerto ou fechamento do RED M71. `V224 owner_signature` e `V225 owner_decision` continuam cerimônias separadas e não recebem adaptações de status prontas por confiança local.

## 3. Fluxo futuro proposto com estados fail-closed

```text
UNENROLLED (HARD NO-GO)
   -> PENDING_HUMAN_IDENTITY_REVIEW (sem poder)
   -> PENDING_FIRST_CREDENTIAL_PROOF (desafio efêmero, não autoriza)
   -> PENDING_OUT_OF_BAND_CUSTODY_ATTESTATION (fonte separada)
   -> ENROLLED_INERT (chave pública custodiada/validada, sem ativação)
   -> OWNER_AUTHENTICATED (somente sessão)
   -> CRITICAL_ACTION_PENDING_FRESH_OWNER_DECISION (step-up por ação)
   -> DECISION_VERIFIED (ainda sem Worker)
   -> [todos os demais P0, F1/T1, recibos e gate atendidos] -> FUTURE_GO_REVIEW
```

A qualquer hora: `REVOKED`, `SUSPENDED`, `RECOVERY_PENDING`, `UNAVAILABLE` => ações críticas BLOQUEADAS. Restaurar banco/backup não pode restaurar credencial revogada. Um mesmo canal comprometido não pode simultaneamente pedir e aprovar recuperação. Duas credenciais no mesmo sincronizador não devem ser contadas como duas autoridades independentes.

## 4. Contrato verificável do adaptador WebAuthn (somente a ser construído)

**Registro:** domínio RP ID estável e origem HTTPS previamente aprovados, challenge único gerado do lado confiável, verificação de `clientDataJSON.type == webauthn.create`, `challenge`, `origin`, RP ID hash, flags UP e UV exigido, formato de attestation suportado/política de attestation coerente, credencial única, algoritmo permitido, key material público e credential ID em registro versionado e protegido. A política deve especificar se aceita passkeys sincronizadas (flags BE/BS e possíveis contadores zero) e como tratar perda/clone/backup; não deduzir "hardware proof" de UV.

**Autenticação:** `type == webauthn.get`, challenge servidor ligado a nonce, owner/tenant/workspace/ação, origin/RP ID, assinatura da assertion e credential ID vinculados a registro custodiado, contador/flags aplicáveis, tempo curto, detecção de revogação, substituição de chave e cross-origin/rpId fail-closed. O servidor não aceita `owner_verified=true` declarado pelo navegador como atestação independente de B0.

**Proteção do ato crítico:** não emitir autorização a partir de login, cookie ou simples prompt; exigir confirmação contextual explicitamente vinculada à intenção, valor, destino, fornecedor, validade e nonce. Revalidar estado/revisão da credencial e evidência de incidente no limite de escrita com fence apropriado. Nonce/revisões persistidos de forma atômica com recuperação/rollback independente.

**Segredos:** nunca imprimir, enviar ao GitHub/chat ou guardar chave privada/seed, PIN, biometria, tokens de sessão ou recovery secret. Apenas hashes/IDs públicos com dados pessoais mínimos e política LGPD.

## 5. Levantamento de lacunas já comprovadas no repositório

- `atlasquant_aion_trust_root.py`: lê/verifica registros de chaves públicas Ed25519 e validade/revogação, MAS um registro local JSON não demonstra custódia fora do mesmo controle administrativo.
- `atlasquant_aion_owner_signature_ceremony.py`: verifica criptografia V2.24 condicionada a `owner_trust_roots` recebido; não captura Windows Hello nem estabelece B0 independente.
- `atlasquant_aion_owner_decision_record.py`: V2.25 separa decisão de assinatura de identidade; aprovação continua sem liberar execução.
- LAB P0 `test_aion_p0_owner_root_custody_lab.py` demonstrou aceitação matemática de chave sintética quando ela é incluída no trust root sintético. Isso não é bypass de produção.
- LAB `atlasquant_aion_p0_signed_enrollment_proof_lab.py`: assinatura de recibo sintético, **sempre BLOCKED** se faltam custódia real, estado independente e prova do HUMAN_OWNER. Run #39305959906: 141/141 PASS em cada OS, mas nenhum P0 homologado.
- **Busca por arquivos nomeados WebAuthn/passkey no A118 não encontrou adaptador operacional.** Não inventar conclusão de compatibilidade do hardware/instalação.
- M71 aceita gate antigo READY na função isolada após REOPENED; M73 testa apenas diagnóstico de lab. Nenhuma dessas defesas está homologada no executor real.

## 6. Matriz de aceitação obrigatória antes de homologar B0/B1

| ID | Cenário | Contrato exigido |
|---|---|---|
| O-01 | Autoinscrição pelo primeiro login, ADMIN, ChatGPT ou GitHub GET | BLOCKED |
| O-02 | Credencial registrada sem comprovação out-of-band do proprietário | BLOCKED |
| O-03 | `origin` falso, RP ID trocado, challenge alheio/vencido ou cross-tenant | BLOCKED |
| O-04 | UV ausente, assinatura inválida, ID desconhecido, credencial revogada | BLOCKED |
| O-05 | Restaurar banco antigo após revogação | BLOCKED, rollback detected |
| O-06 | Perda de celular + PC, troca de aparelho, conta sincronizada comprometida | RECOVERY_PENDING sem autoelevação |
| O-07 | Reutilização de assertion/nonce em paralelo, inclusive após reinício | BLOCKED / single-use durável |
| O-08 | Credencial não sincronizada sem backup/alternativa | bloqueio seguro com recuperação independente |
| O-09 | Comprovar apenas autenticação sem decisão específica | nenhuma ação crítica |
| O-10 | Prova de B0/B1 perfeita com F1/T1/P0 restantes ausentes | Worker OFF, HARD NO-GO |
| O-11 | Fonte de custódia/registro ou tempo confiável indisponível | BLOCKED, sem fallback permissivo |
| O-12 | Homologação alegada por 141 testes sintéticos | rejeitar: evidência de dispositivo/custódia real é obrigatória |

## 7. Execução em duas fases sem comprar nada agora

**Fase A — presente, executável no celular (documental e análise):** registrar este ADR e o inventário dos controles existentes, preparar fluxos de UX e perguntas para matrícula real, manter testes históricos e M71 inalterados, sem custos ou credenciais reais.

**Fase B — somente depois de autorização e acesso ao dispositivo:** confirmar versões e compatibilidade de navegador/Windows/Android; escolher RP ID/origem definitiva, provedor/controlador da raiz de confiança e método out-of-band; validar recuperação antes de ativar cadastro real; executar testes físicos e auditoria independente em LAB; nenhum deploy/merge enquanto HARD NO-GO.

**Decision gate (não solicitado ao proprietário agora):** `OWNER_APPROVES_BOOTSTRAP_DESIGN` e `OWNER_APPROVES_REAL_CREDENTIAL_ENROLLMENT` são decisões distintas. Este ADR não concede nenhuma das duas.

## 8. Critérios de GO para apenas este P0

Contar P0 HUMAN_OWNER como homologado **somente se** houver (1) vínculo real pessoa-conta/credencial atestado fora da solicitação, (2) origem e custodiante independentes fixados, (3) verificação WebAuthn/Ed25519 correspondente, (4) revogação/recovery/rollback duráveis, (5) testes físicos Windows e celular, (6) revisão independente, (7) integração auditada com decisões e gates, (8) evidências nomeadas e aprovação expressa. Até lá **0/6 P0**.

Nenhum custo ou alteração operacional está aprovado por este documento.
