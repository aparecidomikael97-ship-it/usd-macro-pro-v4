# A179 LAB — Entrada de recibo condicionada a testemunha independente sintética

**22/10/2026 — PR Draft #1469 sobre A178 #1468. Núcleo HARD NO-GO; P0 homologados: 0/6.**

## Problema endereçado
A178 validava matematicamente recibo Ed25519 de fornecedor simulado, mas não precisava que uma testemunha externa confirmasse, a cada recebimento, conhecimento da intenção, sequência de reserva e uma raiz de confiança inalterada. Chave pública fixada pelo mesmo chamador e contador high-water exclusivamente local permaneciam manipuláveis.

## Contrato A179 (somente LAB)
`aion_chat/witness_admission_lab.py` compõe verificações de **dois signatários distintos** em uma interface `evidence_verifier` da A177:
1. Primeiro: assinatura Ed25519 do fornecedor sintético sob chaves públicas já configuradas em A178, vinculadas a decisão, escopo e efeito.
2. Segundo: chamada `witness_provider(challenge, request)` para **cada** proposta, com desafio aleatório de 256 bits. Resposta contém `RESERVED`, identidade/key ID da testemunha, desafio único, hash integral do recibo assinado, hash da lista de chaves de fornecedor e revogações, kind, ID da operação, receipt ID, sequência do recibo, sequência monotônica declarada pela testemunha e janela de validade (máximo 90 segundos). A testemunha assina a resposta Ed25519, sob chave pública **separada** da chave do fornecedor.
3. Falha de rede/callback da testemunha, resposta ausente, assinatura inválida, ausência de RESERVA, divergência de chave/escopo/recibo, revogação, sequência velha, janela vencida ou desafio reapresentado ⇒ **não aceitar** `EFFECT_CONFIRMED` ou `EFFECT_ZERO`. A A177 conserva `UNCERTAIN/SENT` sem autorizar reenvio.
4. O protótipo mantém também contagem e IDs vistos **na memória do processo**, exclusivamente como salvaguarda LAB; não é custódia durável. O signatário sintético de testes mantém um conjunto de reservas apenas em memória.

## Casos adversariais criados
São **21 testes A179**: duas assinaturas válidas de LAB, reconciliação após UNKNOWN sem novo envio, testemunha ausente, exceção/offline, reutilização de assinatura de desafio antigo, assinatura de testemunha não confiável, separação obrigatória de chaves, revogação, hash da pinagem adulterado, assinatura com corpo alterado, sequência testemunha inferior ao high-water esperado, resposta expirada, recibo e intenção divergentes, reapresentação na mesma instância, reinício do verificador preservando testemunha, restauração deliberada de estado de testemunha, substituição da raiz de confiança, formato inválido, evidência negativa com duas assinaturas sem retry, assinatura de fornecedor inválida.

## Contraprovas IMPORTANTES não fechadas
- `A179_WITNESS_STATE_ROLLBACK=REPLAY_ACCEPTED_NOT_ATTESTED`: restaurar o próprio conjunto de reservas/contador da testemunha, mesmo com assinatura válida e novo desafio, permite reconhecer novamente um recibo. **Exige custódia independente monotônica realmente resistente a rollback ou autoridade/quórum verificável.**
- `A179_CALLER_REPINS_WITNESS_ROOT=FAKE_AUTHORITY_ACCEPTED`: se a chave de testemunha é fixada por um chamador não confiável, ele pode fazer sua própria assinatura de autoridade falsa passar. **Exige registro/provisionamento confiável da chave, separação organizacional, identidade verificada, revogação real.**
- O desafio prova frescor de resposta **somente em relação à chave configurada e ao relógio local**, não garante a honestidade nem a durabilidade externa da testemunha.
- O callback de testemunha é simulado localmente. Não há rede/provedor externo real, noção verificável de quórum ou prova de efeito zero de um sistema externo. Apenas chaves privadas sintéticas nos testes.
- Mesmo uma testemunha genuína para recibos não garante que a primeira operação foi reservada **antes** do envio, nem fornece atestado do descritor SQLite nativo, anti-rollback de todo histórico ou autenticação do HUMAN_OWNER.
- Não há Quality canônica completa nesta etapa.

## Evidências de CI
Preencher após checagem dos logs da bateria Windows + Ubuntu, incluindo as regressões SQLite.

## Segurança operacional
Sem custo, novas chaves reais, provisionamento, chamadas reais ao provedor, Worker, merge ou deploy. Os seis P0 continuam **0/6 homologados, HARD NO-GO**. `ZERO_AUTO_RESEND` não pode ser relaxado por assinaturas sintéticas ou testemunha local.

### Próxima prioridade técnica
Exigir prova durável de reserva da **primeira tentativa antes de cruzar a fronteira externa**, consultar uma fonte de confiança que não possa ser substituída pelo adaptador/host local, obter atestados de quórum ou custodiantes independentes e caracterizar recuperação após restauração/rollback real.
