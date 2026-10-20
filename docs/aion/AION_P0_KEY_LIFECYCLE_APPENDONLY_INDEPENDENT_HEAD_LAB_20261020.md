# AION P0 — Sequência de chaves, revogação e split-view (LAB NO-GO)
**20/10/2026 | 0/6 P0 | HARD NO-GO | Worker OFF | ZERO_AUTO_RESEND**

## Mudança específica
Avançar do pin estático de chave (#1360) e do formato KMS (#1361) para um contrato sintético de *eventos de ciclo de vida*: ENROLL, ROTATE, REVOKE e RECOVER. Ensaiamos sequências contíguas, epochs crescentes, hashes encadeados, tempo UTC crescente, bloqueio de reuso de chave e alegações divergentes de último head. Nenhum evento se torna autêntico só por bater um hash local.

## Casos que passam a ser explicitamente detectados no LAB
- A mesma chave antiga é reapresentada após rotação ou revogação.
- REVOKE atinge uma chave diferente da ativa, ou RECOVER ocorre sem revogação.
- Há duas versões alegadas do mesmo head no mesmo epoch/sequence (*split view*).
- Dois observadores compartilham administrador, mesmo root de recuperação ou domínio cruzado de administração e recuperação.
- Digest adulterado, parent hash divergente, epoch revertido, sequência pulada e relógio não monotônico.
- Classes Python hostis e esquemas com campos adicionais são recusados.
- O cenário de restauração conjunta de todos os registros *também* pode parecer coerente localmente — e por isso permanece NO-GO.

## Requisitos para qualquer homologação futura
1. **Emissor e proprietário:** auditor comprova identidade, chave pública matriculada por canal fora do host, controle IAM/KMS, recuperação MFA e atribuições de administração. Identificadores digitados pelo executor não são prova.
2. **Revogação:** política assinada e independente com epoch monotônico e caso de emergência; uma chave comprometida não pode autenticar sua própria revogação ou continuação sem validação de autoridade.
3. **Último head:** checkpoints assinados; verificações de inclusão e consistência comparadas contra head anterior guardado fora do domínio de rollback. RFC 9162 fornece referência conceitual; não foi implementado verificador RFC nesta PR. Log append-only e S3 Object Lock em uma versão não provam a visão global mais recente.
4. **Nonce e falha de rede:** challenge do verificador, vinculado a escopo, sessão, request, epoch e head; consumo de nonce durável externo; na ausência de resposta, timeout ou bifurcação: BLOQUEAR sem reenvio automático.
5. **Fornecedor e efeito:** prova autenticada de COMMITTED_EFFECT ou NO_EFFECT_FENCED. A falta de mensagem não demonstra que o primeiro efeito não ocorreu. Os 32 erros Outbox/Saga permanecem bloqueados em separado.
6. **Governança e orçamento:** análise independente de controle administrativo e custos (KMS, logs, retenção e consulta). Nenhuma criação de conta/chave. Teto operacional R$200/mês, exceção até R$250 apenas autorizada.

## Limite do código
A função audit_key_lifecycle_claims_lab recebe exclusivamente valores do chamador. Um histórico e testemunhas perfeitamente coerentes podem sinalizar *sintaticamente consistente*, mas a saída é sempre BLOCKED e allowed=False, com as 17 flags de autorização/efeito falsas. Não há KMS, assinatura real, persistência, leitura externa de head, nonce cache, operações HTTP, nem integração a A53/A76/Worker.

Os 32 testes são negativos/contratuais, não equivalem a autenticação nem homologação. A branch deriva do PR Draft #1361, **não de main**, e nenhum módulo de produção foi modificado. Baseline canônico anterior: Quality 6.562, 52 FAIL + 34 ERROR; Security A53 RED; 0/6 P0.

## Perguntas externas ainda abertas
- Quem controla o root de autenticação e também a recuperação da chave e do testemunho?
- Que fonte independente confirma que não há head mais recente ou fork?
- Qual evidência incontestável mostra que o provedor não executou a primeira operação?

Referências: https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1357 ; https://www.rfc-editor.org/rfc/rfc9162.html ; https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html ; https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
