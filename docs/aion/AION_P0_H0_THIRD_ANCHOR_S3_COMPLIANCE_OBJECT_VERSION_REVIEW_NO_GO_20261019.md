# ATLASQUANT / AION — P0 H0: terceira âncora imutável fora da Cloudflare

**Revisão arquitetural de 19/10/2026. PROPOSTA, NÃO CONTRATAÇÃO.** **0/6 P0 homologados; HARD NO-GO; Worker desligado; ZERO_AUTO_RESEND.** Nenhuma conta AWS/Cloudflare criada, nenhum bucket/Worker/deploy, nenhuma chamada S3, credencial, custo novo, envio ou ação externa.

## Resumo da decisão

**Escolha para investigação, não implantação:** (1) AION/SQLite local; (2) Cloudflare Durable Objects em domínio administrativo separado para **CAS e serialização de tentativas**; (3) **Amazon S3 Object Lock em modo COMPLIANCE, com versionamento e em conta AWS administrada separadamente**, como candidato a reter eventos históricos identificados por *version ID* imutável. Um quarto componente lógico ainda necessário é **a identidade verificável e o readback autêntico da âncora**, sob credenciais/chave fora do AION e da Cloudflare. Esse desenho não é garantia absoluta de disponibilidade, permanência após encerramento da conta, recuperação da chave de criptografia ou resistência ao comprometimento conjunto de administradores.

Cloudflare Durable Objects por si só suporta point-in-time recovery (PITR), logo pode retroceder junto com o executor. Um bucket **Cloudflare R2 Bucket Lock não é independente em termos de administração e seu bloqueio pode ser removido** via painel, CLI ou API por administrador com permissões; é inadequado como âncora isolada contra o próprio administrador. O AWS S3 COMPLIANCE proporciona proteção significativamente mais forte de retenção para **cada versão do objeto**, inclusive contra exclusão pelo root antes da data de retenção, dentro das limitações do serviço. Isso NÃO prova que o objeto foi gravado, consultado de forma autêntica ou é o registro mais recente. A AWS observa ainda a possibilidade de fechamento da conta.

### Documentação oficial pesquisada

- S3 Object Lock (versioning obrigatório; diferenças COMPLIANCE/GOVERNANCE; delete marker; nova versão de mesmo nome): https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- Retenção, metadata e leitura por `HeadObject/GetObject` com versão identificada; impacto de perder chaves KMS: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html
- S3 conditional PUT `If-None-Match: *`, que **só inspeciona a versão corrente**; se houver delete marker, novo PUT pode ser permitido apesar de uma versão antiga preservada: https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html
- Cloudflare R2 Bucket Locks, regras removíveis: https://developers.cloudflare.com/r2/buckets/bucket-locks/
- API para substituir lock rules R2: https://developers.cloudflare.com/api/resources/r2/subresources/buckets/subresources/locks/methods/update/
- Cloudflare Durable Objects SQLite: https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/

## Exatamente o que o S3 Object Lock COMPLIANCE protege — e não protege

**Protege:** uma versão de objeto retida não pode ser sobrescrita, excluída, encurtada ou convertida para GOVERNANCE por admin/root da conta enquanto sua retenção COMPLIANCE permanecer válida. AWS protege a **versão armazenada**, não o ponteiro lógico para "último objeto".

**NÃO protege automaticamente:** o nome lógico do objeto, a visibilidade de seu HEAD padrão (delete marker pode ocultar), nova versão sob mesma chave, criação de ramificações/forks, estado mais recente do livro, retenção após expiração, perda da chave de criptografia, isolamento administrativo real, perda de acesso à conta, disponibilidade da AWS, a identidade do produtor externo, prova de que uma SMS não foi enviada, e assinatura de testemunha com chave separada. Um `PutObject(If-None-Match:*)` **não fecha** o bypass por delete marker em bucket com versioning. Não usar ETag ou SHA local como prova de custódia.

### Contrato proposto de escrita, ainda não implementado

O evento de âncora carregaria exclusivamente identificadores opacos, sem telefone, conteúdo, CPF ou documento:

```text
schema_version; independent_issuer; key_id/key_version;
scope_digest(owner/tenant/workspace/host autenticados);
intent_id; action_digest; idempotency_key_digest;
epoch; sequence; predecessor_digest;
cas_reserved_head; attempt_id; state=ATTEMPT_RESERVED_BEFORE_EFFECT;
nonce; issued_at; object_key; S3 VERSION_ID;
retention_mode=COMPLIANCE; retain_until;
digest do recibo autenticado e atestado de readback específico de versão.
```

Ordem proposta (todas as falhas ficam **BLOCKED**, nunca retry de efeito):

1. Autenticar owner/scope de modo independente e validar que a intenção é inédita antes da primeira ação externa.
2. Reservar intenção única via CAS remoto transacional no Durable Object, sob credencial/admin separada. Timeout após commit => `UNKNOWN`; nunca fazer nova reserva com nova intenção apenas para "corrigir".
3. Persistir **âncora de evento** no S3 com retenção COMPLIANCE suficiente, chave/versão individualizada, IAM mínimo e metadados de retenção. Uma resposta de PUT com status desconhecido exige investigação, não novo disparo.
4. Obter a **S3 VERSION_ID** efetivamente gravada; readback dessa exata versão e suas propriedades de retenção, validar conteúdo/digest/epoch/seq/nonce e proveniência autenticada por canal separado. Não confiar em GET padrão "latest" nem apenas no retorno local do primeiro PUT.
5. Confirmar que a âncora está amarrada ao head CAS e que não houve fork, rollback, PITR ou credencial revogada; qualquer divergência é **HARD NO-GO**. Se Cloudflare CAS funcionou mas S3 falhou, a tentativa remota continua reservada e o efeito é proibido.
6. Só depois disso, e de **TODOS OS OUTROS P0 HOMOLOGADOS**, pode-se estudar a passagem ao primeiro efeito do fornecedor. A confirmação da âncora NÃO concede autoridade ao Worker, não garante produtor confiável e não converte timeout/SMS sem idempotency key em retry seguro.

Não há transação atômica distribuída pronta entre Cloudflare DO e AWS S3; o desenho é um protocolo de estado com falhas possíveis. "CAS remoto concluído, âncora incompleta" deve permanecer bloqueado e investigável. Separação de contas/keys é condição necessária, não suficiente: controle simultâneo de ambos os lados, root de ambas as contas ou conta AWS encerrada ainda limita as garantias.

## Regras de segurança para o custo e LGPD

- **Não criar conta AWS, Cloudflare, bucket, token, IAM ou retenção COMPLIANCE sem aprovação expressa.** O S3 Compliance não permite encurtar uma retenção já aplicada, e versões retidas podem gerar custo até expirar.
- Estimar **storage (incluindo versões), PUT/GET/HEAD/ListVersions, operações de retenção, KMS, logs, tráfego e impostos**, com teto global vigente R$200/mês e bloqueios proativos. Não assumir que 5 GB gratuitos no DO tornam AWS gratuito.
- Revisar jurisdição, confidencialidade, retenção LGPD e finalidade antes de persistir hashes. Pseudônimos e hashes estáveis podem ainda constituir dados pessoais dependendo do contexto.
- Acesso mínimo ao gravador; administrar custódia separadamente e com MFA; readback verificável e monitorar credenciais/revogação. Não conceder ao executor `s3:DeleteObject`, `s3:PutBucketObjectLockConfiguration`, `s3:BypassGovernanceRetention` ou permissões amplas de versão/account.
- Auditoria de disponibilidade e proteção contra fechamento de conta ou comprometimento do root requer evidência operacional independente. Não usar o próprio GitHub LAB como terceiro registro imutável.

## Artefato LAB verificável da rodada

`atlasquant_aion_p0_h0_third_anchor_design_review_lab.py` é um **preflight de proposta** que rejeita arquiteturas que alegam ser imutáveis mas carecem dos controles definidos, incluindo R2 rules removíveis, S3 GOVERNANCE, versionamento ausente, leitura por nome em vez de `version ID`, delete marker, prazo insuficiente, custódia de chaves, vínculo de epoch/digest e timeout que dispara reenvio.

`test_aion_p0_h0_third_anchor_design_review_lab.py` cobre 28 cenários (inclusive alegações maliciosas `verified=true`, objetos hostis e proposta aparentemente perfeita). O relatório SEMPRE diz `state=BLOCKED`; todos os campos `third_anchor_enrolled`, `third_anchor_signature_authenticated`, `third_anchor_retention_verified_remotely`, `third_anchor_version_verified_remotely`, `external_highwater_compared`, `first_effect_allowed`, `automatic_retry_allowed`, `worker_arming_allowed` ficam `False`, MESMO quando a proposta descreve todos os controles. **A ferramenta não consulta S3, não é uma API de segurança produtiva e não confere nenhuma das declarações com serviços externos.**

## Critério honesto para avançar

Para passar de PROPOSTA a experimento controlado, seria necessário: autorização de contas/limites, revisão de custos e IAM, onboarding de identidade/assinatura de witness, mínimo duas contas administrativas independentes, S3 VersionID e metadata de retenção reais, teste de delete markers/novas versões, Cloudflare PITR, reexecução após timeout pós-PUT, blackout Windows, comparação H0 obrigatória e bateria Quality/Security canônica. Tudo permanece pendente.

**HARD NO-GO, 0/6 P0 homologados, Worker desligado, ZERO_AUTO_RESEND e nenhuma contratação.**
