# AtlasQuant / AION — P0 HUMAN_OWNER root custody audit / 19-10-2026

**Veredito:** testes dirigidos PASS em Ubuntu e Windows; **P0 identidade REAL não homologado**, HARD NO-GO. Esta rodada não cria/cadastra credencial real, não homologa F1/T1, não altera produto, não autoriza ação.

## Baseline isolado
- Fonte pinada: A118 commit `c62fab663c6349d7320f7843c8d09587c514426b`, branch LAB `lab/aion-p0-owner-root-custody-20261019`.
- Testes novos `test_aion_p0_owner_root_custody_lab.py`, commit `898925c8353068b0f665145c50ec21b75cae1aca`.
- Workflow de verificação `.github/workflows/aion-p0-owner-root-custody-lab.yml`, commit `bffce322b8548a003f17a0796cb986a070460f5e`.
- [GitHub Actions run #39302729585](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39302729585): Ubuntu job `118231829886` e Windows job `118231830326` SUCCESS. Os jobs verificaram **seis hashes de código/testes originais** antes de executar.
- Em cada SO: **61 testes históricos V2.24 + V2.25 PASS**, **8 testes novos P0 PASS**, **6 controles A74 PASS**. Total **75 testes distintos, 150 execuções** em dois SO. Não significa fechar P0 ou passar Quality canônico.
- Conjunto original usado sem mudanças: `atlasquant_aion_owner_signature_ceremony.py` blob `eac8091ed9c80d838e069b16130c65530bde6652`; `atlasquant_aion_owner_decision_record.py` blob `2d0ae10f33dc4a4cafdc0241074829a7a4d97b57`; `atlasquant_aion_f1_t1_untrusted_witness_intake_a75.py` blob `efaf025d198e67acc24fda7fb05de46a064509b2`; `test_atlasquant_aion_v224_owner_signature_ceremony.py` blob `383f7044c7535368b94e1333f5687a93bd13d25e`; `test_atlasquant_aion_v225_explicit_owner_decision_record.py` blob `2c150d5e9cf15dba07718fcc30270e733de3b86d`; `test_atlasquant_aion_activation_authority_a74.py` blob `884a046f7e01ed9ebdef85209be0a8bf98b2990e`.

## Achado técnico relevante
O método V2.24 `verify_owner_signature(... owner_trust_roots=...)` verifica corretamente **controle criptográfico de chave aceita pelo registro que recebeu**. O teste P0-01 cria em memória uma nova chave Ed25519 e seu próprio `TrustRootRegistry`, assina o desafio e obtém `READY_FOR_EXPLICIT_OWNER_DECISION` / `owner_identity_verified=True` no verificador sintético. A chave e o registro são temporários. Isto **não prova** que um invasor altere o registro confiável da implantação real e **não é bypass de ativação**; demonstra que essa função isolada depende integralmente da autenticidade da origem do `owner_trust_roots`. Uma chave/registro apresentado por quem está pedindo a autorização não pode ser considerado matrícula real do HUMAN_OWNER. O nome do campo `owner_identity_verified` não substitui essa premissa.

Controle negativo: assinatura da chave errada contra raiz fixa BLOQUEADA; troca do registro após desafio BLOQUEADA; texto de chat BLOQUEADO; nonce reapresentado após reabrir arquivo SQLite BLOQUEADO; chave revogada BLOQUEADA; rótulo ADMIN forjado BLOQUEADO; decisão com assinatura válida continua **pendente de persistência**, sem operação. Não capturamos biometria, Windows Hello, FIDO2, chave real nem provedores externos.

## Critérios de fechamento P0 (pendentes; NÃO executados)
1. Definir processo de matrícula inicial do HUMAN_OWNER fora do próprio fluxo que pede aprovação, com identificação/controle da conta e da credencial, prova presencial ou out-of-band de custódia e autorização explícita do proprietário para matricular. Documentar revogação, substituição e perda de dispositivo.
2. Fixar trust anchor da chave pública fora de runtime/branch/JSON mutável pelo mesmo principal que pede autorização; impedir autoinscrição e substituição de raiz pelo caller.
3. Challenge único com escopo (owner/tenant/workspace/ação/operação/epoch), propósito, TTL curto, antirreplay persistente, verificação de assinatura e separação explícita identidade -> decisão -> execução. Vincular assinatura ao contexto de sessão e ação.
4. Definir trajetória de Windows Hello/FIDO2/WebAuthn e cenário mobile, **sem obrigar compra nova agora**. Identidade física/legal e controle de credencial autenticada não são automaticamente a mesma coisa.
5. Fazer ensaio independente: chave de invasor, troca raiz, revogação, offline/outage, rollback, restart, múltiplos aparelhos, tentativa de alterar registro, continuidade auditável. Reexecutar Quality e Security canônicos além das suítes dirigidas.
6. Só após evidência real aprovada pelo HUMAN_OWNER registrar uma contagem P0 > 0. Não ativar Worker; F1/T1 fonte/antirollback e os outros cinco P0 são trilhas separadas.

## Restrições mantidas
- **0/6 P0 homologados**; M71 RED do gate reapresentado continua aberto; M73 é apenas protótipo LAB.
- Worker OFF, ZERO_AUTO_RESEND, nenhum merge/deploy, nenhuma matrícula real, chave de produção, contato a serviço externo ou custo novo; **HARD NO-GO.**

## Próxima prioridade
Preparar **especificação de matrícula verificável e raízes de confiança imutáveis**, com matriz RED antes de propor adaptador de dispositivo. Sem aprovação explícita da escolha real da credencial/custódia, somente LAB/draft.
