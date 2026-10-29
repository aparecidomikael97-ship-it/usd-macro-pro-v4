# A252 — Backup SQLite coordenado com writers cooperantes (LAB)

**Estado: HARD NO-GO · 0/6 P0 homologadas · sem deploy, Worker, merge, custos ou operações reais.**

## Problema

O método `backup_to` poderia executar `require_healthy`, checkpoint FULL do WAL e copiar o SQLite enquanto outro processo cooperante se encontrava entre COMMIT e limpeza do marcador de tentativa incerta. A ausência de serialização com `append_message`, `create_conversation`, arquivamento, anexo, checkpoint e resumo pode produzir falso veto temporário ou uma cópia cuja ordem relativa à operação não está definida pelo nosso protocolo.

## Mudança A252

- `SQLiteChatStore.backup_to` agora utiliza `@_local_commit_gate`, o **mesmo lock cooperativo local/kernel** das seis rotas de escrita A251.
- Todo o ciclo do backup — checagem de saúde, checkpoint FULL, cópia, validação e publicação create-only — ocorre depois de concluir qualquer COMMIT cooperante anterior e antes de liberar writers cooperantes que aguardam.
- Não modifica a publicação create-only, proteções de WAL/backup e regras de resultado incerto de A234–A239.
- O lock não é autenticado pelo host; concorrentes SQL que não cooperam podem ignorá-lo.

## Ensaios

1. Backup verificado convencional preserva mensagem.
2. Subprocesso real conclui COMMIT e **deliberadamente mantém a trava e o marcador por ~850 ms antes de confirmar**. Pedido de backup em outra instância deve aguardar, concluir após limpar o marcador e incluir a mensagem confirmada.
3. Subprocesso é encerrado com `os._exit` **depois de COMMIT real**, antes de limpar marcador. A trava do kernel é liberada, mas o backup continua negado pelo veto local pendente; nenhum arquivo é publicado.
4. Contenção real da trava + timeout curto de teste: backup negado antes de criar destino.
5. Inventário exige `@_local_commit_gate` no método de backup.
6. **XFAIL proposital:** conexão SQLite direta e não cooperante pode escrever enquanto a trava consultiva do AION está adquirida. Este é um risco real ainda aberto.

CI: Ubuntu/Windows, suíte A252 e regressões A251–A233, além das baterias SQLite de backup/restore existentes.

## Limites

- Lock consultivo não previne SQL externo, manipulação de arquivos por administrador, ABA, rollback de mesmo inode, erro físico de energia ou VFS/FD sem atestado.
- `wal_checkpoint` independente e conexões externas não são cobertos pela serialização de `backup_to`; mais revisão necessária.
- A verificação do backup demonstra consistência local, **não** evidência de autoridade/cronologia independente nem recibo externo de efeitos.
- Falhas esperadas de A252 e A251–A245 não podem ser usadas como P0 aprovadas.
- AION completo continua em desenvolvimento para o Trader sob demanda, motor econômico compartilhado com Investimentos, Negócios congelada.

**UNCERTAIN=ZERO_AUTO_RESEND · HARD NO-GO operação real · P0 0/6.**
