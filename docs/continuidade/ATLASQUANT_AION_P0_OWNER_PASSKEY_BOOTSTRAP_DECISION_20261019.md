# Checkpoint Mestre — AION P0 HUMAN_OWNER: decisão de arquitetura pendente — 19/10/2026

**Esta rodada é arquitetura e análise de lacuna, NÃO teste executado, cadastro real ou homologação.** HARD NO-GO e Worker OFF.

## Artefato produzido
- ADR em branch LAB `lab/aion-p0-owner-webauthn-architecture-20261019`:
  `docs/adr/ADR-AION-P0-HUMAN-OWNER-PASSKEY-BOOTSTRAP-LAB-20261019.md`
- Commit do ADR `103e8e5b9dae2c05f97f0394ba3be664eee6cc2b`.
- Fonte de continuidade LAB anterior: `a2cd52321a9e62a58121627ee71d56ce1a61da23` + documentação da auditoria da prova de matrícula.
- Auditoria técnica anterior: [run #39305959906](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39305959906), 141/141 casos PASS Ubuntu e 141/141 Windows, limitado à prova assinada em LAB. **Nenhum teste novo foi executado no presente checkpoint.**

## Decisão técnica proposta para o proprietário (ainda não aprovada)
Escolher **passkey/WebAuthn nos dispositivos já existentes, se compatíveis**, como candidato para autenticação cotidiana. WebAuthn é um mecanismo diferente da assinatura Ed25519 existente e requer um adaptador independente, RP ID/origem aprovados, challenge + assinatura + UV + custódia. Não migrar automaticamente `owner_signature` ou `owner_decision` para um simples `login=ok`.

É obrigatório um **bootstrap out-of-band** para a primeira credencial: uma chave fornecida por quem pede acesso não pode declarar a si mesma autoridade. Possuir passkey não é automaticamente comprovação da identidade civil nem independente da custódia inicial. O custodiador externo/independente, trilha de revogação, recuperação e política de chave ainda não foram selecionados/validados.

A arquitetura proposta mantém: login habitual com experiência integrada PC+celular depois de cadastrar credencial; step-up por ação crítica; revogação/recovery segura; status SUSPENDED/UNKNOWN/RECOVERY_PENDING negam ações; cadastro não fornece autoridade de Worker; nunca solicitar segredos, PIN ou biometria no chat.

## Observações objetivas de fonte
- Não foi encontrado módulo WebAuthn/passkey por nome na árvore do baseline A118. Isso é um inventário limitado, não prova absoluta de ausência de toda biblioteca.
- `atlasquant_aion_trust_root.py` é registry de chaves públicas, não autoridade independente de primeiro cadastramento.
- `atlasquant_aion_owner_signature_ceremony.py` verifica assinatura sob `owner_trust_roots` fornecido; `atlasquant_aion_owner_decision_record.py` mantém aprovação separada.
- Falha M71 de replay de gate READY permanece RED no código original; M73 foi apenas ensaio diagnóstico.
- Fontes de referência: W3C WebAuthn L3 https://www.w3.org/TR/2026/REC-webauthn-3-20260825/ ; Microsoft https://learn.microsoft.com/en-us/windows/security/identity-protection/hello-for-business/webauthn-apis ; FIDO Alliance https://fidoalliance.org/white-paper-replacing-password-only-authentication-with-passkeys-in-the-enterprise/

## Próximos passos realmente necessários

### Pode ocorrer sem computador/credencial real
1. Revisar ADR e matriz O-01...O-12 (ameaças de autoinscrição, nonce, UV, origin/RP ID, rotatividade, recuperação, credencial sincronizada, tenant cruzado).
2. Definir contrato de trust anchor externo e de comprovação humana out-of-band independente do solicitante e do runtime. Não afirmar que GitHub GET/credencial sincronizada equivalem à custódia.
3. Preparar interface de enrolment com estados e fluxos de UX somente no LAB, sem registrar nenhuma credencial ou gastar dinheiro.
4. Manter outros 5 P0 e M71 pendentes, em vez de abrir frentes de produto.

### Requer aprovação explícita do proprietário e acesso a PC/celular
1. Confirmar versões de Windows, Android, navegador, suporte a passkey/Windows Hello e disponibilidade de recuperação.
2. Escolher origem HTTPS/RP ID definitiva, conta/provedor/custódia e política de credenciais sincronizadas versus vinculadas ao dispositivo. Domínio e infraestrutura NÃO estão contratados/aprovados.
3. Autorizar de forma independente desenho de bootstrap e, depois, cadastrado real (duas decisões separadas).
4. Validar no dispositivo, logs, revogação, perda/restauração, antirollback, fluxo real e Security/Quality originais; revisão externa antes de integrar.

## Estado e decisões
- Não gerou/chamou WebAuthn, nenhuma chave produtiva, nenhuma assinatura real, nenhum banco, rede de autenticação, contas, deploy/merge/Worker, despesa ou matrícula.
- Não existe evidência para declarar P0 identidade fechado; **0/6 P0 homologados**; Worker OFF; ZERO_AUTO_RESEND; HARD NO-GO.
- O ADR pode ser revisado, não é ordem de implantação. Próximo marco objetivo é a **decisão de arquitetura e de custódia**, não acumular mais testes verdes sintéticos.
