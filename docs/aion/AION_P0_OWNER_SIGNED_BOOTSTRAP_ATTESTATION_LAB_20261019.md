# AION P0 HUMAN_OWNER — prova de matrícula assinada (LAB, não autorizante)

Data: 19/10/2026. **HARD NO-GO / 0 de 6 P0 homologados.** Nenhuma credencial real cadastra aqui.

## Objetivo do experimento
Fechar uma parte técnica importante do P0: provar que um recibo de matrícula tem assinatura Ed25519 verificável sob uma chave de testemunha pública previamente fornecida ao verificador, e bloquear alterações de escopo, recibo, revisão, contexto ou prazo.

**IMPORTANTE:** Isso NÃO comprova a custódia independente dessa chave. O próprio LAB injeta o emissor, a chave de verificação, o escopo esperado, a revisão anterior e o conjunto de recibos vistos. O método intencionalmente retorna sempre `BLOCKED`. Não acoplar a emissor de tickets reais nem à ativação.

## Componentes
- `atlasquant_aion_p0_signed_enrollment_proof_lab.py`: verificador isolado sem rede, gravação ou autorização. Assina-se no teste um objeto JSON canônico com domain-separation específica. Chave pública Ed25519 vem de `pinned_issuer` **sintético de teste**.
- `test_atlasquant_aion_p0_signed_enrollment_proof_lab.py`: 39 casos adversariais e positivos limitados (incluindo assinatura válida mas sem autoridade) congelados antes da execução; chaves temporárias do pytest não são reais.
- `.github/workflows/aion-p0-owner-signed-enrollment-lab.yml`: CI Linux+Windows, permission `contents:read`, 39 novos + 27 controles de matrícula + 69 originais/negativos + 6 A74, hashes pinados para quatro arquivos críticos A118, sem mudança de produto.

## Semântica do recibo
Deve haver assinatura separada da proposta, ligada a: owner/tenant/workspace, ID de credencial, fingerprint exata da chave que seria cadastrada, nonce de desafio, issuer/key_id, propósito exclusivo de matrícula, revisão, evidência ID, issued/expires. Se qualquer coisa divergir -> `BLOCKED`.

Mesmo que a assinatura tenha sido matematicamente verificada, saída `P0_SIGNATURE_CONSISTENT_BUT_ISSUER_CUSTODY_UNVERIFIED`, sem emissão de identidade ou mudança de registro. O replay-control e a revisão, neste LAB, são apenas entradas NÃO autenticamente persistidas.

## Evidência que ainda FALTA para o P0 real
1. **Matrícula externa independente**: verificar quem é o proprietário humano e vincular ao autenticador por procedimento off-channel verificável, sem autoinscrição e com consentimento explícito.
2. **Trust root fora do domínio controlado pela aplicação**: selecionar custódia independente, política de troca/revogação e fixar chave pública do emissor por canal confiável. Não aceitar a chave fornecida junto com o recibo.
3. **Nonce/high-water durável e atômico**: registro independente, antirollback após crash/restauração, verificação contra revisões atuais no ponto de ação; prova de que assinatura não pode ser reapresentada.
4. **Credencial real**: selecionar passkey/WebAuthn (Windows Hello/Android) ou chaves Ed25519 com custódia adequada e verificação do dispositivo; modelo passkey exige origin/RP-ID/UV, e é distinto do mecanismo Ed25519 existente. Não afirmar suporte já implementado.
5. **Aprovação e decisão separadas**: primeiro vincular pessoa/credencial, depois consentimento por operação e autorização externa, preservando V2.24/25/26, A74, F1/T1 e ZERO_AUTO_RESEND.
6. **Teste físico e auditoria independente**: Windows/Android real, interrupção, perda e recuperação, troca de chave, bloqueio de tenant cruzado, revoked root, concorrência e rollback. Nada disso foi homologado pela CI simulada.

## Política sem custo novo
Não criar conta externa, assinatura, nova chave de produção, alterar Render/GitHub rulesets, habilitar Worker, fazer merge/deploy, gerar gastos ou coletar dado sensível sem decisão do proprietário. Quando o proprietário tiver acesso ao computador/dispositivo de autenticação, escolher um modo específico e registrar evidências físicas. Por enquanto os seis P0 permanecem ABERTOS.

## Atenção à interpretação dos resultados
- `LAB SIGNATURE PASS` = integridade criptográfica de *recibo sintético* verificada.
- `HUMAN_OWNER REAL VERIFIED` = **NÃO COMPROVADO**.
- `OWNER ENROLLMENT AUTHORIZED` = **FALSE** em todas as saídas.
- `HARD NO-GO` = permanece, mesmo que todos os cenários de CI fiquem verdes.
