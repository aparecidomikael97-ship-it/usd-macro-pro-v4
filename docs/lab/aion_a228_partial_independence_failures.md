# A228 — Uma falha impede que onze alegações positivas liberem o sistema

**Situação:** simulação interna em Draft. **HARD NO-GO · P0 externo homologado 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.** Nenhuma chave, testemunha, IAM, fornecedor, raiz offline, KMS/HSM ou recibo real foi usado.

## Exemplo simples

Imagine que o host diga que **11 dos 12 requisitos de independência passaram**, mas que um teste de origem da chave falhou. A decisão é **bloqueio**, não “11 votos a favor”. E, mesmo que o host diga que os 12 passaram, isso ainda não comprova segurança: nenhum resultado foi autenticado externamente.

O A227 fixou os 12 requisitos mínimos, todos sem evidência externa. O **A228 testa todas as combinações sintéticas de falhas** nesses mesmos 12 requisitos.

| Resultado simulado | Quantidade de combinações | Decisão |
|---|---:|---|
| Exatamente 1 requisito falha; 11 têm *pass* alegado | 12 | Bloquear |
| Exatamente 2 requisitos falham | 66 | Bloquear |
| Exatamente 3 a 11 falham | 4.016 | Bloquear |
| Todos os 12 requisitos falham | 1 | Bloquear |
| **Total com uma ou mais falhas** | **4.095** | **Bloquear sempre** |

O caso **zero falhas** não foi contado entre os 4.095: ele também **não é aprovado**, porque 12 resultados fornecidos pelo host não equivalem a 12 provas independentes. O pré-voo rejeita explicitamente esse caso com `ZERO_FAILURES_DO_NOT_PROVE_INDEPENDENCE`.

## Como o laboratório funciona

Para cada um dos 12 requisitos do A227, a simulação inclui uma linha com um dos dois rótulos:

- `SYNTHETIC_NEGATIVE_TEST_FAILED`, associado ao desafio negativo exato do requisito;
- `HOST_CLAIMS_PASS_UNVERIFIED`, que é só o host dizendo que teria passado, não um *pass* independente.

Cada linha exige `HOST_SIMULATED_UNTRUSTED`, `NOT_OBTAINED` e `NOT_VERIFIED`. Qualquer tentativa de trocar o rótulo para `VERIFIED_PASS`, o emissor para `EXTERNAL_TRUSTED` ou os estados para `OBTAINED`/`VERIFIED` é recusada. O pré-voo também recusa:

1. Escopo owner/tenant/workspace incorreto e vínculo com A227 adulterado;
2. Contrato A227 invalidado, mesmo quando o host apresenta uma matriz A228 coerente;
3. Contagens diferentes de 12 linhas, duplicatas, campos extras e desafios negativos falsificados;
4. Escolha de modelo, autorização do proprietário, contato externo ou conclusão de P0 forjadas;
5. Tentativa de mudar **`HARD_NO_GO`** para `GO` ou habilitar reenvio automático.

As 4.095 combinações foram exercitadas em **um teste de propriedade combinatória** entre os 50 testes de A228. A contagem 4.095 **não** é quantidade de provas reais nem de testes unitários independentes. Não ocorre tentativa de ataques reais: o módulo é uma função pura, sem I/O.

## Artefatos

- `labs/a228_partial_evidence_failure_matrix.py`: compara somente declarações sintéticas de 12 resultados com o contrato A227 ainda não validado externamente.
- `labs/test_a228_partial_evidence_failure_matrix.py`: **50 testes unitários**, incluindo todas as 4.095 máscaras não vazias.
- `.github/workflows/aion-a228-partial-evidence-failures-readonly.yml`: matriz Ubuntu e Windows, com **50 testes novos + 755 regressões anteriores = 805 por sistema operacional**, sujeitos à confirmação da CI.

O resumo da matriz inclui contagem de **falhas simuladas** e de **passes apenas alegados**, além de um SHA-256 de identificação local (não assinatura). A contagem de `independent_passes_verified` é sempre **zero**. `external_evidence_accepted`, `owner_signoff_valid`, `provider_final_effect_verified` e todos os flags `may_*` permanecem **False**.

## Garantias que o A228 não oferece

O A228 prova apenas o comportamento do **código sintético de pré-voo** sob essas entradas. Não demonstra segregação de deveres real, posse de chave, proteção contra comprometimento de host, autenticidade de testemunho, disponibilidade, nem segurança de um fornecedor. A raiz offline e o KMS/HSM continuam alternativas de estudo, **não selecionadas**.

Referências de princípio: [NIST — trust anchor](https://csrc.nist.gov/glossary/term/trust_anchor), [NIST — out of band](https://csrc.nist.gov/glossary/term/out_of_band), [AWS KMS — segregação de administração e uso](https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html).

**Conclusão A228:** nenhuma maioria de alegações pode autorizar uma ação; sem evidência independente, o bloqueio também vale quando todas as alegações parecem positivas. **HARD NO-GO.**
