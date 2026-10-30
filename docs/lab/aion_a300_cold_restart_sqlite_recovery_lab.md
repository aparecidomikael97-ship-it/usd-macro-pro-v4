# A300 — Reinício frio SQLite, WAL e custódia do COMMIT incerto

**Isolado em LAB. HARD NO-GO. ZERO_AUTO_RESEND. P0 homologadas: 0/6. Sem custos novos.**
PR draft sem merge, Worker, deploy, provider, ordens, cliente real ou alteração do core.
Nenhuma extensão C nativa foi compilada ou carregada.

## Ensaio 1 — recuperação fria de uma cópia incompleta

- Cria conversa e faz checkpoint da base anterior.
- Confirma uma mensagem real no WAL através do SQLiteChatStore.
- Mantendo a origem aberta, copia deliberadamente só o arquivo principal .db,
  separadamente usa a API SQLite Connection.backup para criar backup lógico.
- Fecha a conexão original e reabre original, cópia raw e backup lógico com uma
  nova instância SQLiteChatStore e strict_local_data_version=True.
- Verifica integridade local, estado HEALTHY e mensagens de cada histórico.

**Critério de contraprova:** a cópia raw .db sem WAL reabre como HEALTHY e
aparenta integridade, mas perde uma mensagem antes confirmada e visível por
segunda conexão; o original e o backup pela API SQLite preservam a mensagem.
Não há defeito alegado na API de backup; mostra perigo de copiar somente
o arquivo .db com WAL ativo e depender de health local após reinício.

## Ensaio 2 — banco restaurado sem marcador do ACK incerto

- Injeta erro sintético **após COMMIT efetivo** durante append_message.
- Verifica que a origem conserva o veto .aion-message-commit-pending e recusa
  reinício sem revisão manual.
- Faz snapshot lógico **somente do SQLite** com conexão separada.
  Este ensaio não usa SQLiteChatStore.backup_to/restore_from_backup.
- Reabre o snapshot lógico por pathname diferente; o efeito está lá, mas o
  marcador de incerteza **não acompanha o arquivo**.

**Critério de contraprova:** o novo histórico parece saudável, mas perdeu
a informação de ACK incerto. Esse resultado não é autorização para reenviar,
executar ordens, liberar Worker ou apagar marcador. Só confirma que dados,
marcadores e custódia de intenção exigem contrato único e autenticado.

## Segurança e limites

- Apenas bancos descartáveis em TemporaryDirectory; a origem não é restaurada
  ou substituída. Zero resends automáticos e zero efeitos externos.
- Não mede queda física de energia ou durabilidade do dispositivo.
- Não autentica FD/VFS nativo SQLite (P0-5) nem durabilidade/ACK/WAL,
  marcador independente ou custódia externa (P0-6).
- Regressões A299, A293 e A292 em Windows e Ubuntu, Python 3.12,
  sem novas dependências. **Verde significa contraprova reproduzida**,
  não aprovação operacional.

Próxima investigação sugerida: contrato offline de manifesto de recuperação
que vincule snapshot SQLite, estado de intenção e comprovante independente
com recusa explícita quando um componente faltar. Sem homologar P0.
