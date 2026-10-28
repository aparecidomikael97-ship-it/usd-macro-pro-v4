# A226 — Duas fontes concordam. São mesmo independentes?

**Situação:** somente simulação em Draft. **HARD NO-GO · P0 externo 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.** Nenhum testemunho, assinatura, chave, fornecedor, corretora ou administrador real foi consultado.

## A diferença que importa

Imagine duas pessoas mostrando a mesma declaração: “O teste da chave passou”. Se a mesma pessoa escreveu os dois papéis, não existem duas confirmações independentes. **Dois nomes e dois hashes iguais não provam duas autoridades.**

O A211 já verificava se checkpoints *alegados* eram coerentes. O A226 adiciona uma pergunta diferente: **as duas fontes declaradas compartilham controlador, principal de assinatura ou depósito de auditoria?** E quando declaram ser totalmente separadas, como evitar acreditar somente no que o host contou?

| Duas alegações fornecidas pelo host | Sinal que o código observa | Decisão segura |
|---|---|---|
| Mesmo controlador, mesmo operador de assinatura ou mesmo armazenamento de auditoria | Sobreposição explícita nos rótulos apresentados | `EXPLICIT_SHARED_HOST_LABELS_NOT_INDEPENDENT` |
| Dizem coisas diferentes (digests divergentes) | Contradição local | `HOST_CLAIMS_DISAGREE_NO_INDEPENDENT_PROOF` |
| Dizem a mesma coisa e usam nomes/domínios diferentes | Concordância apenas estrutural | `TWO_COHERENT_DISTINCT_HOST_LABELS_INDEPENDENCE_UNPROVEN` |

**Nenhum dos resultados acima autentica identidade, provas externas ou confiança.** Um invasor com controle do host pode fabricar até os rótulos “domínio A” e “domínio B” e produzir dois hashes coerentes. O laboratório não tem como observar a independência real.

## Que provas exigiremos numa etapa externa futura (ainda sem executar)

1. **Identidades dos emissores verificadas fora do host:** papéis, chaves e cadeia de confiança não devem ser aceitos apenas por texto local.
2. **Separação efetiva de domínios de controle:** administração, assinatura, aprovação, testemunho e logs não podem colapsar nas mesmas credenciais ou permissões comprometíveis.
3. **Desafio e observação independentes:** nonce, origem e resultado precisam ser confrontados fora do sistema que está tentando provar sua própria segurança.
4. **Âncora de revisão independente:** histórico, revogação e checkpoints devem ser verificáveis sem depender do host sob ataque.
5. **Recibo financeiro independente:** confirmação de operação depende do provedor real, não da assinatura do root nem de duas testemunhas concordantes.
6. **Revisão e autorização humanas separadas:** antes de testes reais, solicitar escopo e responsabilidades concretos. O formulário não escolhe pessoas ou fornecedores.

## Limites do código A226

O validador recebe duas descrições de fontes **host-controlled** e exige vínculo de escopo owner/tenant/workspace com um rascunho A225 ainda não confiável. Para cada fonte são apenas campos sintéticos: `source_id`, `claimed_controller_id`, `claimed_signing_principal_id`, `claimed_audit_store_id`, `claim_digest` e marcadores de que **nenhuma identidade ou recibo externo foi verificado**.

Quando ambas as descrições são válidas, o código consegue detectar somente sobreposições **declaradas** e igualdade/desigualdade de digests **locais**. Isso é útil para recusar alegações inconsistentes, mas não pode declarar verdadeira independência, mesmo se todos os campos declararem entidades diferentes.

Os resultados sempre mantêm `False` em:

- `actual_independent_issuers_verified`, `actual_domain_separation_verified`, `owner_anchor_verified`, `independent_evidence_accepted`, `owner_signoff_valid`, `provider_final_effect_verified`;
- `may_accept_security_proof`, `may_select_model`, `may_contact_person`, `may_run_external_challenge`, `may_commit_budget`, `may_provision`, `may_generate_key`, `may_sign`, `may_connect`, `may_confirm`, `may_auto_resend`.

O P0 externo permanece **0/6** e nenhum dado foi enviado para fora do laboratório. SHA-256 aqui é apenas digest de rascunho, **nunca assinatura ou prova de autenticidade**.

## Artefatos

- `labs/a226_claimed_source_independence.py`: verificação pura das duas alegações declaradas, sem I/O.
- `labs/test_a226_claimed_source_independence.py`: **50 testes novos** (rótulos compartilhados, divergência, falsos “verificados”, cross-tenant, digest replay, ordem e JSON hostil).
- `.github/workflows/aion-a226-source-independence-readonly.yml`: **50 novos + 655 regressões A202–A225 = 705 testes por SO** Ubuntu/Windows.

Referências que orientam a necessidade de segregação, mas não aprovam fornecedores:

- [NIST SP 800-57 Part 1 Rev. 5](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final)
- [AWS KMS — segregação de administração e uso](https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html)
- [Google Cloud KMS — separação de funções](https://docs.cloud.google.com/kms/docs/separation-of-duties)

**Conclusão A226: concordância não é independência. Dois nomes não são dois domínios de confiança comprovados. HARD NO-GO.**
