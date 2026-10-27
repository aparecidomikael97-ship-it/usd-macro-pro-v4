# A190 / G138 — contrato assinado para custódia futura (LAB, NÃO EXTERNA)

**Origem:** #1629 G137. **0/6 P0. HARD NO-GO. UNCERTAIN/ZERO_AUTO_RESEND.**

## Objetivo útil

Especificar e verificar **os bytes que uma futura custódia independente precisaria assinar**, sem contratar/ligar serviço e sem inventar uma prova real. A assinatura usa Ed25519 e domínio distinto `ATLASQUANT:G138:SYNTHETIC_CUSTODY_RECEIPT_V1\0`, sobre um JSON canônico. A resposta tem esquema estrito:

- `schema,status,authority_id,authority_epoch,sequence,challenge,root_sha256,issued_at,expires_at`.
- `event_id,original_sha256,owner_id,tenant_id,workspace_id`, **todos** iguais ao registro original retido em LAB.
- `signature`: Ed25519 de 64 bytes sob chave pública **pré-fixada pelo verificador sintético**, não fornecida/aceita a partir do próprio recibo.
- Challenge de 256 bits gerado por `secrets.token_hex(32)` no verificador; tempo consciente de timezone; duração válida de no máximo 60s; `sequence` maior que o maior valor local retido.
- Resposta aceita retorna `permits_send=False`, `permits_retry=False`, `external_homologation=False`; falha, expiração, ACK desconhecido ou assinatura inválida consomem **aquela sessão**. Nunca criar segunda tentativa automática.

Um subprocesso separado **no mesmo computador** assina um recibo com chaves privadas temporárias **geradas pelo teste**. Ele não é custodiante, não tem banco autoritativo e o usuário do processo pode substituir a chave e o próprio recibo. O contrato verifica integridade matemática, **não** a verdade de que uma primeira tentativa foi realmente custodiada.

## Integração de laboratório sem SEND

Caso dedicado liga:

1. `PinnedOriginalClaimLab` G135 / A183 exige duas assinaturas sintéticas (owner + identity_authority);
2. sessão G138 verifica resposta sintética Ed25519 de custodiante;
3. subprocesso local G134 reserva um ID;
4. registro local de permissão do G137 é criado **pela própria fixture**; gatilho de SQLite exige esse registro antes do `ExecutionOutbox.enqueue` real e consome-o na mesma transação;
5. o `dispatch_claimed` da Outbox padrão mantém estado UNCERTAIN com zero chamadas a `adapter.send`.

Ações em sequência **não são atômicas entre bancos/processos**, não têm autoridade do HUMAN_OWNER genuína e não são acessíveis a Worker real.

## 14 provas e contraexemplos

1. Assinatura sintética feita em outro processo valida identidade/nonce e **não** autoriza SEND.
2. Assinatura alterada é recusada.
3. Hash econômico original adulterado é recusado.
4. ID original/owner/tenant/workspace adulterados são recusados.
5. Nonce/challenge alterado é recusado.
6. Expiração, prova emitida no futuro ou TTL excedido são recusados.
7. Epoch, emissor, root fingerprint ou status adulterados são recusados.
8. Reapresentar prova na mesma sessão e sequência antiga com piso intacto é recusado.
9. Ausência de ACK consome a sessão; sem retry automático.
10. Campos extras e base64 inválido são recusados.
11. Cadeia sintética completa alcança `ExecutionOutbox.enqueue` real sem SEND.
12. **RED:** restauração de high-water local permite obter um novo recibo assinado para **o mesmo efeito** sem qualquer custódia independente real.
13. **RED:** mesmo conteúdo econômico sob outra identidade original, re-pinning de raiz e nova assinatura sintética é aceito matematicamente.
14. Outbox padrão bloqueia `adapter.send` mesmo com todos os comprovantes LAB satisfeitos.

## O que ainda falta para sequer propor GO externo

Uma autoridade economicamente e operacionalmente **independente do host**, com identidade HUMAN_OWNER registrada **antes** da primeira intenção e fonte original autenticada, raiz pública provisionada fora do host, custódia persistente monotônica resistente a rollback, semântica original por efeito de negócio e integração obrigatória não contornável (incluindo SQLite native same-inode). Deve manter provedor real e seu recibo/prova de não efeito de forma independente, resolver ACK incerto sem reenvio automático e cumprir todas as cinco exigências G122 reais. Isto não pode ser simulado com `root_fingerprint` passado pelo chamador, arquivos efêmeros de CI ou campo `lab_verified`.

**Não habilitar Worker/deploy/SEND, não fazer merge, não registrar credenciais/provedor real, sem custo novo ou dados reais.** PR Draft empilhada em G137.
