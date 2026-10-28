# A224 — Catálogo de testes de segurança da raiz (laboratório, NÃO EXECUTADOS)

**Prioridade de pesquisa:** escolha **1 — Segurança e controle máximo**, informada pelo usuário no A223. Esta é uma intenção conversacional **não autenticada**, não uma assinatura, homologação, escolha de modelo ou autorização para testar sistemas reais.

**Estado atual:** `HARD NO-GO` · `P0 externo = 0/6` · `UNCERTAIN = ZERO_AUTO_RESEND`. As 13 provas descritas abaixo seguem **pendentes**.

## O que será exigido antes de confiar numa arquitetura

Cada linha do catálogo contém (a) ataque a investigar, (b) modelo ao qual se aplica, (c) comportamento seguro esperado, (d) função independente que precisará produzir ou conferir evidência e (e) modalidade futura de desafio. Tudo é uma **pergunta de verificação**; não há chave, HSM, fornecedor, aprovação, custo ou infraestrutura criada.

| Situação adversarial | Aplica-se a | Comportamento esperado numa comprovação futura |
|---|---|---|
| Host tenta ler chave privada/backup offline | Offline | Negar acesso ao material privado |
| Host tenta se passar por custodiante físico | Offline | Rejeitar impersonação do custodiante |
| Host tenta usar `Sign` na raiz KMS | KMS/HSM | Negar assinatura ao host |
| Host tenta alterar política do KMS | KMS/HSM | Negar edição de política |
| Host tenta assumir papel com privilégio | KMS/HSM | Negar escalada de função |
| Host fabrica aprovação de Mikael | Ambos | Rejeitar aprovação sem origem independente |
| Admin, operador e aprovador se confundem/coludem | Ambos | Exigir separação verificável entre principais |
| Host repete nonce antigo | Ambos | Rejeitar replay |
| Host reutiliza chave revogada | Ambos | Rejeitar raiz revogada |
| Host apaga/reescreve auditoria | Ambos | Detectar perda, fork e rollback |
| Falha de rede/serviço provoca reenvio | Ambos | Falhar fechado; zero reenvio automático incerto |
| Assinatura da raiz é usada como falso comprovante financeiro | Ambos | Exigir recibo final autoritativo do provedor |
| Host substitui identidade de outro tenant | Ambos | Rejeitar alegação fora do escopo |

**Não se conclui que a raiz offline ou o KMS/HSM venceu.** Exigências e riscos são diferentes. Sem teste autorizado e evidência externa, não existe vencedor técnico demonstrado.

## Como a futura prova deverá ser avaliada

1. **Autorização separada:** primeiro será preciso definir pessoas e escopo de um eventual teste externo. Escrever o catálogo não concede essa autorização.
2. **Negação verificável:** observar em ambiente aprovado que um host com permissões limitadas não consegue ler a raiz, assinar, alterar política ou assumir outra função.
3. **Testemunha fora do host:** a execução e o resultado devem deixar evidência auditável, independente das permissões sob ataque; uma frase do próprio host não vale como prova.
4. **Falhas adversas:** checar perda de contato, indisponibilidade, repetição, revogação, rollback, troca de tenant e recibos financeiros falsos.
5. **Revisão humana:** revisor independente avaliará a procedência, cobertura, prazos, divergências, recuperação e risco residual, **antes de qualquer decisão real**.
6. **Homologação externa P0:** permanece processo separado. Um teste de laboratório verde não altera os seis P0.

## Barreiras do código

O A224 exige a ligação a uma matriz A222 ainda não preenchida e a uma nota A223 de prioridade de pesquisa, por hashes locais canônicos. Eles identificam apenas conteúdo de rascunho; **não autenticam identidade nem provam custódia**. Alterar proprietário, tenant, workspace, modelo, fonte/escopo do protocolo, linha de ataque, resultado ou estado gera rejeição.

Todos os registros de teste devem permanecer:

- `execution_state=NOT_EXECUTED`
- `external_proof_state=NOT_OBTAINED`
- `independent_review_state=UNASSIGNED`
- `remediation_state=NOT_STARTED`

Os resultados válidos também mantêm, invariavelmente: `owner_identity_verified=False`, `owner_signoff_valid=False`, `independent_tests_executed=False`, `independent_proof_accepted=False`, `custody_model_selected=False`, `external_p0_homologated=0`.

Todas as capacidades externas ficam bloqueadas: executar desafio, contatar pessoa, selecionar modelo, comprometer orçamento, provisionar, gerar chave, assinar, conectar, confirmar, reenviar automaticamente.

## Artefatos e contagem

- `labs/a224_security_proof_test_catalog.py`: 13 especificações estáticas coerentes com A220 (ataques) e A221 (funções e modalidades de prova).
- `labs/test_a224_security_proof_test_catalog.py`: **50 testes novos** de integridade, escopo, recusa de estados falsos, ordem canônica, hashes e não autorização.
- `.github/workflows/aion-a224-security-proof-catalog-readonly.yml`: **50 novos + 555 regressões A202–A223 = 605 testes por sistema operacional** em Ubuntu e Windows.

As boas práticas de gerenciamento de chaves e separação de responsabilidades orientam as perguntas, sem selecionar fornecedores:

- [NIST SP 800-57 Part 1 Rev. 5](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final)
- [AWS KMS — separação de administração e uso](https://docs.aws.amazon.com/prescriptive-guidance/latest/encryption-best-practices/kms.html)
- [Google Cloud KMS — separação de funções](https://docs.cloud.google.com/kms/docs/separation-of-duties)

**Conclusão A224:** 13 protocolos de teste descritos; **zero** desafios externos executados; **zero** provas independentes aceitas; **zero** autorização operacional; `HARD NO-GO`.
