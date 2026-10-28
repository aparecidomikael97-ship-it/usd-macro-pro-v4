# A225 — Provas falsas de segurança: rejeição obrigatória (laboratório)

**Situação:** Draft sintético e puramente local. **HARD NO-GO · P0 externo 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.**

O A224 descreveu **13 desafios de segurança que ainda não foram executados**. O A225 pergunta: *“E se o próprio computador invadido apresentar uma tela, hash ou declaração dizendo que o teste passou?”*

**Resposta exigida:** o Núcleo jamais deve interpretar essa afirmação como prova independente, autorização de Mikael, proteção real da raiz ou recibo financeiro final.

## Oito maneiras de tentar enganar o Núcleo

| Simulação ofensiva | Alegação falsa | Regra de segurança |
|---|---|---|
| 1. Autoaprovação do host | “Todos os controles passaram.” | Texto do host não comprova nada externamente. |
| 2. Aprovação forjada do proprietário | “Mikael assinou.” | Falta autenticidade verificada fora do host. |
| 3. Testemunha falsa | “Um auditor independente confirmou.” | Falta identidade e prova externa da testemunha. |
| 4. Hash antigo reaproveitado | “O digest coincide.” | Hash local não é assinatura nem proteção contra replay. |
| 5. Recibo financeiro inventado | “A corretora confirmou.” | Assinatura/print não substitui consulta ou recibo autoritativo. |
| 6. Captura de política KMS | “A permissão `Sign` foi negada.” | Print do host não demonstra a política efetiva. |
| 7. Captura de custódia offline | “A chave não está acessível.” | Print do host não demonstra guarda física independente. |
| 8. Pressão por indisponibilidade | “Pode reenviar porque deu timeout.” | `UNCERTAIN` deve manter **zero reenvio automático**. |

As 8 táticas foram cruzadas com os **21 pares válidos de cenário e arquitetura** dos 13 ataques A220: **168 combinações sintéticas**. Em todos os casos, a implementação rejeita qualquer promoção da alegação para uma prova verdadeira. Isso *não* representa 168 ataques reais a nuvem, hardware ou corretora.

## O que o A225 realmente verifica

1. **Escopo da pesquisa:** owner/tenant/workspace, cenário, modelo e controle têm que corresponder ao catálogo A224 ainda não executado.
2. **Vínculo local do rascunho:** o digest do catálogo A224 deve coincidir; esta é uma checagem de consistência, não de identidade, integridade externa ou autenticidade.
3. **Afirmações continuam host-controlled:** mesmo hashes de 64 caracteres e nomes de auditores são textos fornecidos por uma origem não confiável.
4. **Passagem para autoridade é proibida:** o resultado válido é `HOST_FORGED_PROOF_LOCALLY_WELL_FORMED_BUT_NO_EXTERNAL_PROOF_HARD_NO_GO`.
5. **Mentiras explícitas são recusadas:** P0 positivo, papel de auditor aprovado, assinatura do proprietário, recibo confirmado, liberação de retries, troca de tenant, modelo errado, JSON duplicado ou oversized.

Os estados obrigatórios do input incluem: `claim_origin=HOST_CONTROLLED_UNTRUSTED`, `claimed_execution_state=HOST_CLAIMS_PASS_UNVERIFIED`, `issuer_identity_state=UNVERIFIED`, `external_proof_state=NOT_OBTAINED`, `independent_review_state=UNASSIGNED`, `owner_approval_state=NOT_REQUESTED` e `provider_receipt_state=NOT_OBTAINED`.

Mesmo quando o input é bem formado, o resultado mantém sempre **false** em:

- `owner_identity_verified`, `independent_issuer_verified`, `independent_witness_verified`, `external_proof_accepted`, `owner_signoff_valid`, `provider_final_effect_verified`;
- `may_accept_security_proof`, `may_select_model`, `may_contact_person`, `may_run_external_challenge`, `may_commit_budget`, `may_provision`, `may_generate_key`, `may_sign`, `may_connect`, `may_confirm`, `may_auto_resend`.

`external_p0_homologated` permanece **0**. O sistema não envia qualquer ordem, consulta, e-mail, chamada de nuvem ou comando a HSM.

## Limite importante

**Este laboratório verifica que o código não confia automaticamente numa alegação.** Ele não consegue provar que um recibo verdadeiro foi emitido, que chaves estão fora do host ou que uma testemunha real existe. Essas provas exigirão mecanismos independentes, escopo e autorização expressos em outra etapa. O catálogo A224 continua **não executado**.

## Artefatos e testes

- `labs/a225_untrusted_security_proof_rejection.py`: classificador puro de alegações sintéticas não confiáveis.
- `labs/test_a225_untrusted_security_proof_rejection.py`: **50 testes** contra falsas aprovações, reaproveitamento, provas trocadas, JSON ambíguo, cross-tenant e falso P0.
- `.github/workflows/aion-a225-untrusted-proof-rejection-readonly.yml`: **50 novos + 605 regressões A202–A224 = 655 testes por SO**, Ubuntu e Windows.

Referências de base, sem escolha de fornecedor:

- [NIST SP 800-57 Part 1 Rev. 5 — gerência de chaves](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final)
- [AWS KMS — separação de funções](https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html)
- [Google Cloud KMS — separação de funções](https://docs.cloud.google.com/kms/docs/separation-of-duties)

**Conclusão:** nenhuma prova externa verificada, nenhum modelo escolhido, nenhum envio, nenhum reenvio automático, nenhum gasto, nenhuma alteração de ambiente. **HARD NO-GO.**
