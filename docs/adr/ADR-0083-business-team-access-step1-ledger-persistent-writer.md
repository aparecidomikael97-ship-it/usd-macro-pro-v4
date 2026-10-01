# ADR-0083 — Step 1 Persistent Lifecycle Ledger Writer V1

- Título: Step 1 Persistent Lifecycle Ledger Writer V1
- Data: 2026-10-01
- Status: ACCEPTED
- Escopo: AtlasQuant / AION Business / Equipe & Acessos

## Contexto

ADR-0082 congela a decisão de append do receipt canônico do Step 1. Essa decisão verifica digests e não grava o ledger. A próxima camada precisa transformar esse contrato em um plano de escrita persistente sem executar a escrita.

## Problema

Um writer que grave assim que a decisão de append estiver verificada confundiria revisão com autorização de persistência. O ledger também pode mudar entre o preflight e um commit futuro, e uma frase genérica não pode substituir prova presa ao estado exato.

## Alternativas consideradas

1. Gravar o append assim que `EXPLICIT_STEP1_LEDGER_APPEND_DECISION_VERIFIED` for verdadeiro. Rejeitada: a decisão de append não é autorização de persistência.
2. Implementar já o replace atômico e um comando `--apply`. Rejeitada neste bloco: nenhuma mutação física foi autorizada.
3. Manter somente o contrato de append e adiar o writer. Rejeitada: o plano, o lock e a recusa de apply precisam existir antes de qualquer gravação futura.

## Decisão

Criar um writer de lifecycle ledger cujo modo padrão é `PLAN_ONLY`.

O preflight só lê o ledger sandbox e só pode chegar a:

`READY_FOR_EXPLICIT_STEP1_LEDGER_PERSISTENCE_AUTHORIZATION`

Esse estado não autoriza gravar.

O plano exige, ao mesmo tempo:

- `ledger_append_decision_digest` recalculado;
- `source_ledger_digest` igual ao payload lógico GENESIS;
- `target_ledger_digest` igual ao preview;
- binding ao `canonical_receipt_digest` e ao `receipt_review_digest`;
- binding ao Step 1 original;
- source em estado GENESIS;
- `previous_entry_digest` GENESIS;
- sequence/index monotônico;
- ausência de append ou receipt duplicado;
- digest de bytes para detectar alteração depois do preflight;
- diretório permitido absoluto, com `sandbox` no caminho, sem symlink e sem path traversal;
- lock local exclusivo, sem escrever o ledger.

A escrita futura, quando uma autorização separada existir, deve usar arquivo temporário, fsync e replace atômico, com backup do preimage antes da troca. Este bloco descreve essa estratégia e não a executa. `apply_step1_ledger_persistence` recusa e não grava.

A autorização futura fica preparada para Windows Hello ou FIDO2 e deve amarrar source digest, target digest, canonical receipt digest, append decision digest, administrador, sessão, freshness e nonce. A V1 registra o binding e não verifica a prova. Reconhecimento facial não é aceito. Frases genéricas não autorizam persistência.

## Consequências

- O plano verificável existe e permanece fail-closed.
- Nenhum ledger real é modificado por este ADR.
- Step 2, executor, produção, deploy e runtime externo continuam desligados.
- A persistência física continua pendente e exigirá autorização criptográfica ligada ao estado exato.

## Componentes afetados

- `atlasquant_aion_business_team_access_step1_ledger_persistent_writer.py`
- `validate_team_access_step1_ledger_writer_preflight.py`
- `test_atlasquant_aion_business_team_access_step1_ledger_persistent_writer.py`
- visão administrativa 57 em `atlasquant_aion_admin.py`
- Checkpoint Mestre 2026-09-30

## Segurança

- sandbox-only nesta V1;
- nenhum segredo, token ou credencial é persistido;
- receipt e ledger permanecem sanitizados;
- symlink e caminho fora do diretório permitido falham fechado;
- lock local impede duas escritas concorrentes no desenho futuro;
- alteração do arquivo depois do preflight invalida o plano;
- `--apply` no CLI é recusado.

## Compatibilidade

Complementa ADR-0069 e ADR-0082. Não substitui o contrato de append e não autoriza Step 2.

## Rollback/migração

Nenhuma migração de ledger foi executada. O plano de rollback futuro é `PREIMAGE_BACKUP_BEFORE_REPLACE`, com backup ainda não criado. Reverter este bloco é remover a camada de preflight; o ledger existente não muda.

## PR/commit relacionado

Branch `cursor/aion-business-team-access-step1-ledger-persistent-writer-v1-8499`, empilhada sobre a Draft PR #470 (`288cfb4454152385d8203fb162a115f67d0fb547`). Draft PR separada. Sem merge.

## Supersedes

Nenhum.

## Superseded by

Nenhum.
