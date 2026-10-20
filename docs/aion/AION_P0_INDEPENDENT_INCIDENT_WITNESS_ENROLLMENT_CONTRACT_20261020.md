# AION P0 — Contrato de integração de testemunha externa de incidentes, revogação e último head

**20/10/2026 | Documento de arquitetura e testes LAB — não é enrollment.**

**Invariantes: HARD NO-GO, 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND, nenhuma chamada externa.** O projeto [#1356](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1356) demonstrou que `validate_reactivation_gate_for_plan` pode reconhecer um gate como estruturalmente `READY`, mas `validate_reactivation_gate_for_execution` permanece `BLOCKED` sem uma raiz de incidente independente. A Quality canônica mais recente soma **6.562 testes, 52 FAIL + 34 ERROR**, e a Security adversarial permanece RED em A53. A nova proposta não altera tais asserts e não torna o Worker executável.

## 1. Três fatos que não devem ser confundidos

| Camada | Verificação de fato que essa camada admite | O que não pode autorizar |
| --- | --- | --- |
| Estrutural, sintética/offline | Tipos estritos, escopo, epoch e sequência consistentes, identificadores de emissor/versão, nonce sem divergência dentro da fixture, IDs de domínio distintos | Validade da assinatura, identidade e controle dos administradores, frescor remoto, permissão de Worker ou efeitos |
| Raiz externa futura | Assinatura real sobre bytes canônicos de envelope; chave pública previamente matriculada por canal independente; revisão de revogação; last-head monotônico obtido de verificador fora do host | Não autoriza automaticamente efeitos ou a decisão do HUMAN_OWNER |
| Prova causal de operação externa | Recibo autenticado `COMMITTED_EFFECT`, ou cerca terminal `NO_EFFECT_FENCED` do produtor associada à intenção e primeira tentativa; comportamento em timeout/reinício | Não pode ser inferida apenas de uma assinatura de incidentes ou de um `HEAD` no object storage |

`atlasquant_aion_p0_incident_external_witness_proposal_lab.py` só realiza a **primeira camada** e, por design, tem todos os atributos de autorização no valor `False`. `pinned_head` recebido como argumento é **autoafirmado pelo teste**, não um banco monotônico ou observação real do last-head. Uma lista de contas diferentes não prova controle administrativo separado.

## 2. Contrato de evidência externa antes de qualquer integração

- **Emissor e matrícula:** identificar instituição/serviço emissor, controlador do segredo ou HSM/KMS, chave pública e algoritmo aprovado, ID de chave, escopo exato (repo, tenant, workspace e ambiente) e rota de rotação/revogação. Uma assinatura **só conta** após verificação criptográfica de bytes serializados de forma estável contra material matriculado por canal fora do AION e sem recuperação controlável pelo mesmo dono do executor.
- **Frescor e monotonicidade:** obter `latest_epoch`, `sequence`, `head_digest`, última versão e contexto de head junto a um **verificador externo e independente**, com readback de versão, cadeia de causalidade e confirmação de que não há fork/head omitido. Não comparar duas cópias do mesmo SQLite nem confiar só em S3 `HEAD`/Object Lock. O desafio nonce deve ser gerado pelo verificador fora do executor, ligado a request/escopo e registrado em replay-cache durável fora do domínio sujeito a PITR.
- **Revogação:** verificar epoch atual de cada identidade autenticada e seu `credential_revocation_epoch` real no emissor, **antes de criar efeito**, de modo que um snapshot antigo de `access` não readmita credenciais revogadas. Relógio de parede local, timestamp e `credential_fingerprint` autoafirmados não provam validade.
- **Isolamento administrativo:** provar independência das contas root, política IAM de identidade e recurso, SCP/RCP, federation, recuperação de MFA, role-trust, Cloudflare/CAS, conta S3, root do emissor e conta do verificador. Cinco rótulos de controller diferentes são só uma hipótese do checklist.
- **Indisponibilidade e reboot:** timeout, assinatura inválida, 403, 404, epoch conflitante, nonce já visto, rollback de executor/custodiador, restauração PITR e reboot físico sempre produzem `UNKNOWN/BLOCKED`. Não criar `head=0`, não presumir ausência de incidente nem autorizar retry. Com verificador offline, continuar sem primeiro efeito externo.
- **Aprovação humana e fornecedor:** independentemente de um envelope de incidente válido, são necessários HUMAN_OWNER real e recibos de produtor. Twilio não oferece idempotency token na API de mensagens; a busca/listagem posterior não prova `NO_EFFECT_FENCED` de um POST incerto. Os 32 ERROR históricos de Outbox/Saga continuam `OPEN_NOT_WAIVED`.

## 3. Acompanhamento de custo e plano de integração futura

**Nesta rodada:** não provisionar conta, Object Lock, S3, Cloudflare DO, KMS, Token/FIDO ou serviço de SMS. O teto de referência conhecido permanece **R$200/mês**; a possibilidade excepcional de R$250 requer justificativa e autorização. Manter estimativas de IAM, logs, armazenamento/retention, KMS, tráfego, chaves e operação como **não precificadas** até cotações verificáveis.

Sequência documental antes da próxima decisão de custo: (1) revisor técnico independente aprova o mapa de administradores e alçadas; (2) fornecedor responde capacidades de signature/current-head e tempo de recuperação; (3) especificação vinculante de formato assinado e anti-replay com teste off-host; (4) orçamento e autorização humana explícita; (5) piloto isolated/test sem efeito externo; (6) Quality/Security originais, H0 físico e certificação de produção.

## 4. Evidência desta branch

A suíte `tests/test_aion_p0_independent_incident_witness_proposal_lab.py` possui **26 verificações** de formato malicioso, dicionários hostis, mismatch de issuer/tenant/epoch/sequence/revocation/head/nonce, domínios administrativos declarados, claims booleanos, imutabilidade de entrada e execução real dos gates A53/A76 em modo de negação. O workflow Ubuntu/Windows repete também **12 verificações A53/A76 da PR #1356, A74/M71 canônicos, 22 IAM/H0, 17 rollback multi-domínio, 17 testes SQLite #1195, oito hardstops STAGING e os 23 módulos LAB raiz**.

**Interpretação obrigatória:** `PASS` prova que os modelos offline permaneceram conservadores, **não que exista assinatura real verificada, emissor enrolado ou fonte de último incidente fora do host**. Nenhuma regra positiva de `READY` foi acrescentada ao executor.

**HARD NO-GO | Worker OFF | ZERO_AUTO_RESEND | 32 ERROR Outbox/Saga OPEN_NOT_WAIVED | Quality 52 FAIL/34 ERROR | 0/6 P0 homologados.**
