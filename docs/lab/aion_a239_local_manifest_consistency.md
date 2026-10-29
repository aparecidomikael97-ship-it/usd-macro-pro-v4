# A239 — Gate de integridade do manifesto SQLite (somente staging)

Derivado da A238 (#1689). **HARD NO-GO; 0/6 P0 homologados.**

## Falha antes da correção

A função `restore_verified_staging_backup` não lia o `.manifest.json` escrito por `create_verified_staging_backup`. Um arquivo SQLite ainda estruturalmente válido, mas alterado depois da criação do backup, podia ser restaurado e receber o rótulo local `RESTORE_VERIFIED` sem qualquer comparação ao hash do manifesto.

## Medida implementada

- O produtor recusa sobrescrever um caminho de manifesto existente, grava o JSON no temporário com `fsync` do arquivo, publica com `os.link` e solicita sincronização do diretório onde disponível.
- O consumidor exige manifesto legível, sem chaves JSON duplicadas, com schema, estado, modo staging, SHA-256, tamanho e caminho de backup coerentes.
- Antes da restauração, confere tamanho e SHA-256 dos bytes com o manifesto; não publica o destino quando falha.
- `SQLiteChatStore.restore_from_backup` agora aceita `expected_sha256` opcional, conferido antes e depois da cópia SQLite, antes da publicação. Chamadas internas legadas sem manifesto continuam suportadas, mas **não devem ser descritas como autenticadas**.
- Uma restauração com manifesto local retorna `local_manifest_sha256_match=True` e `independent_provenance_verified=False`.
- O caminho `manifest_path` personalizado pode ser passado explicitamente na recuperação; tentativa sem o manifesto correto recusa.

## Ensaios

14 testes novos: cenário bom, manifesto ausente, SQLite válido modificado, hash alterado, tamanho inválido, caminho trocado, modo produção forjado, JSON com chave duplicada/inválido, manifesto personalizado, nome já ocupado, symlink, low-level expected digest e entrada malformada. CI Ubuntu + Windows executa também os 1.107 anteriores: **1.121 testes por sistema previstos**, sujeitos a confirmação de logs.

## Limitações de segurança

Este SHA e manifesto são **dados locais sob controle do mesmo host**. Uma pessoa com poder de alterar o banco e o manifesto pode forjar um par coerente; a validação não prova origem real, não impede rollback coordenado e não é assinatura independente. Não garante identidade atômica de FD/VFS, durabilidade perante corte elétrico, testemunha H0, recibo de provedor ou idempotência de primeira intenção.

Uma falha após a publicação do arquivo mas antes do retorno pode deixar arquivos locais que exigem inspeção manual. Não há remoção automática nem retry cego.

**HARD NO-GO · 0/6 P0 · UNCERTAIN=ZERO_AUTO_RESEND · sem merge/deploy/Worker/contratação/operação real.**
