# AION P0 — matrícula de assinatura do núcleo: cerimônia de confiança e antirollback

**20/10/2026. Proposta de homologação futura, laboratório offline.**  
**HARD NO-GO | 0/6 P0 | Worker desligado | ZERO_AUTO_RESEND.**

## Objetivo deste bloco

O [PR Draft #1359](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1359) provou que é possível verificar a matemática Ed25519 com **chaves de teste não matriculadas** e recusar a autorização quando a origem não é confiável. O problema restante não é mais a matemática: é *quem decide qual chave pública é a legítima, quem comprova a revogação e onde fica guardado o último estado que um invasor não pode restaurar junto com o AION*.

**Esta rodada não registra nenhuma chave externa nem oferece uma rota de produção.** Ela adiciona `atlasquant_aion_p0_trust_anchor_bootstrap_preflight_lab.py`, um revisor negativo de **pinning autodeclarado**. Verifica fingerprint SHA-256 da chave pública, key_id, issuer, scope, piso de sequence/epoch/revocation e alegações de separação administrativa. Mesmo que tudo coincida, retorna `BLOCKED`. O pin, inclusive o próprio fingerprint, é fornecido pelo executor e pode ter sido fabricado ou restaurado.

### Duas ameaças que agora ficam explicitamente representadas

**Substituição conjunta do emissor:** se alguém trocar a chave Ed25519 e a cópia local de `public_key_sha256`, o novo material pode satisfazer todas as comparações e as assinaturas de teste. A matrícula só será real quando a autoridade do pin puder ser atestada por *canal externo não controlado pelo executor*, com aprovação verificável e autenticação do custodiante.

**Rollback conjunto de tudo:** mesmo um par `envelope/head` mais velho, combinado com o `pin` também restaurado e o mínimo de sequência antigo, parece consistente. É necessária prova adicional do **último epoch/head monotônico fora do domínio sujeito ao mesmo backup/PITR**. A regra do AION é não inferir frescor da igualdade local.

## Critérios de uma cerimônia real de matrícula (ainda não executada)

| Estágio | Evidência exigida, fora do executor AION | Bloqueio se faltar |
|---|---|---|
| Designação | Identidade jurídica/técnica do emissor, admin e verificador independentes, responsabilidades e recuperação de MFA | `OUT_OF_BAND_BOOTSTRAP_NOT_ATTESTED` |
| Chave inicial | Chave pública Ed25519 fornecida por canal autenticado independente; fingerprint verificado, assinatura do termo, testemunhas e cadeia de custódia | Não confiar em pin local, GitHub README ou mensagem de chat |
| Escopo | Vincular `issuer_id`, `key_id`, ambiente, repo/tenant/workspace e autorização por função | Bloquear cruzamento de escopos |
| Rotação/revogação | Certificado de transição assinado pelo emissor antigo e novo, autorização externa, epoch monotônico; revogado nunca volta a ser aceito por replay | Sem confirmação externa, `BLOCKED` |
| Head atual | Leitura autenticada da versão máxima existente por serviço realmente independente, com prova contra fork/omissão, epoch/seq e retenção adequada | `LATEST_EXTERNAL_HEAD_NOT_AUTHENTICATED` |
| Challenge | Nonce imprevisível emitido pelo verificador externo e salvo em cache durável fora do executor, associado à sessão/tenant/transação | `PERSISTENT_EXTERNAL_NONCE_REPLAY_GUARD_MISSING` |
| Recuperação | Reboot físico, perda de conexão, restore/PITR, rollback do executor e de custodiador, assinatura antiga íntegra, chave revogada e replay | Qualquer conflito/timeout significa NO-GO |
| Operação | Aprovação real HUMAN_OWNER, recibo de efeito do fornecedor e prova de primeira tentativa, em gates separados | Nenhum contrato de assinatura sozinho libera Worker |

**Um requisito importante:** operadores diferentes nominalmente não são suficientes. É necessário provar que contas raiz, administradores, provedores de identidade, políticas de acesso, mecanismos de recuperação e segredos não convergem para a mesma autoridade com capacidade de reescrever todas as evidências. A futura arquitetura deve admitir explicitamente riscos de perda da autoridade independente e indisponibilidade; não prometer falsamente ausência de qualquer ataque.

## Novos testes (31) e regressões mantidas

`tests/test_aion_p0_trust_anchor_bootstrap_negative_lab.py` cobre: 1) key/pin correto porém sem matrícula; 2) atacante troca ambos; 3) troca de chave contra pin inalterado; 4) assinatura pela chave errada; 5) key_id/scope, campos ausentes, extras ou hostis; 6) igualdade maliciosa em `key_id`; 7) administradores coincidentes; 8) chaves `REVOKED` ou `UNKNOWN`; 9) rotação e revogação sem raiz confiável; 10) floors de época/sequência/epoch de revogação; 11) rollback coordenado de pin+head+assinatura; 12) replay repetido; 13) ausência de leitura externa; 14) nenhum caminho de Worker ou token de produção.

O workflow branch-only Ubuntu/Windows executa a nova suíte mais os **34 testes Ed25519 do #1359**, **30 testes do #1358**, **12 A53/A76**, os contratos históricos A74/M71, os **22 IAM H0**, **17 cenários de rollback em três domínios**, o LAB SQLite original, 17 de ciclo de vida do chat, oito hardstops e os **23 módulos raiz LAB**. Testes de Quality/Security completos seguem separados e seus resultados RED não são dispensados.

Os resultados locais com sucesso devem ser classificados como **GO-LAB do filtro negativo**, jamais como `enrollment_complete`. O filtro não fala com KMS, S3, FIDO2, Twilio, AION Worker ou qualquer emissor real.

## Condições de próxima decisão e orçamento

A arquitetura ainda precisa de **avaliação independente, eventual consulta técnica a provedores e orçamento**. Não foram verificados preços atuais de KMS/HSM, assinatura, logs, versionamento/retention, leitura de última versão ou anti-replay; não há licença, conta, fornecedor ou matrícula contratada. Referência atual de orçamento operacional: R$200/mês; exceção até R$250 só se justificada e expressamente autorizada.

**Situação canônica anterior, sem reexecução nesta proposta:** Quality 6.562 testes, 52 FAIL +34 ERROR (86 ocorrências); Security A53 RED; 32 Outbox/Saga ERROR históricos `OPEN_NOT_WAIVED`; original 0/6 P0. A aprovação de LAB não elimina os problemas nem concede autorização a P0/H0.

**Saída deste trabalho:** contrato negativo, matriz de matrícula e testes; sem merge, deploy, Worker, SMS, trade, chaves externas ou gastos.
