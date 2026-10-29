# A237 — Barreiras de fsync do diretório na restauração SQLite de staging

**HARD NO-GO · P0 homologados 0/6 · \`UNCERTAIN=ZERO_AUTO_RESEND\`.** Alteração isolada no staging em Draft; sem merge, Worker, deploy, serviços externos, credenciais, clientes, pagamentos ou gastos.

## Diferença entre encerrar processo e cortar energia

A236 criou \`<destino>.aion-restore-pending\` com \`flush()+fsync()\` do **arquivo** antes de publicar o banco. Testes reais de \`os._exit\` demonstraram que o marcador sobrevive a encerramentos de subprocessos em Ubuntu e Windows. Isso **não prova** que a entrada de diretório referente ao marcador tenha sido persistida antes da publicação em um corte físico de energia: o filesystem ou controlador pode armazenar mudanças de nomes e bytes em ordens diferentes.

## O que mudou nesta revisão

- \`_sync_staging_restore_directory(directory)\` solicita \`os.open(..., O_DIRECTORY)\`, \`os.fsync(fd)\` e \`os.close(fd)\` em sistemas POSIX com essa capacidade. Em sistemas sem a API, retorna \`False\`, isto é, **não suportado/não atestado**, jamais uma falsa certificação.
- O staging solicita a barreira **três vezes**: (1) após escrever e sincronizar o marcador, **antes** de \`os.link(temp,target)\`; (2) imediatamente após o link, **antes** de tratar o resultado como publicação local; (3) depois de remover o arquivo temporário e o marcador, antes de retornar sucesso local.
- Erro na barreira antes do link causa \`StorageUnavailableError\`; a tentativa permanece interdita pelo marcador.
- Erro em qualquer barreira depois de \`os.link\` causa \`RestorePublicationUncertainError\`: o banco pode já estar visível; nenhuma repetição automática é permitida.
- O retorno de sucesso inclui \`directory_sync_requested\` (**True somente quando a chamada POSIX retornou**) e o campo explícito **\`power_loss_durability_verified=False\`**. Nem chamar \`fsync\` com sucesso equivale a testar queda física ou atestar a cadeia do storage.
- A proteção do A234 contra overwrite, do A235 contra incerteza de publicação e do A236 contra restart com marcador pendente permanece em vigor.

## Ensaios

\`labs/test_a237_sqlite_restore_dirsync.py\` adiciona **15 testes** em bancos temporários com SQLite real:
- Barreiras de diretório solicitadas, retorno de capacidade sem confundir com homologação;
- Falha de \`fsync\` antes de publicar, imediatamente após publicar e após remover o marcador;
- **Subprocessos encerrados abruptamente com \`os._exit(73/74/75)\`** depois da primeira, segunda e terceira barreiras;
- Recuperação observada na reinicialização e recusa de uma nova tentativa automática;
- Simulação de plataforma sem suporte de sincronização de diretório, com ausência de alegação de durabilidade.

Workflow \`.github/workflows/aion-a237-sqlite-restore-dirsync.yml\`: Python 3.12, Ubuntu/Windows, ações pinadas por SHA, **1.095 testes por sistema esperados** (15 novos + 1.080 anteriores); conferir contagem exata nos logs.

## O que NÃO fica comprovado

1. **Nenhum teste de desligamento elétrico real**, sistema de arquivos específico, cache de controlador, UPS ou \`fsync\` com falha física; POSIX \`fsync\` solicitado não é garantia de atestado externo.
2. **Windows:** sem caminho universal confiável de \`O_DIRECTORY\` no Python usado. \`directory_sync_requested=False\`, \`power_loss_durability_verified=False\` mesmo após \`RESTORE_VERIFIED\`, que é somente sucesso local de staging.
3. O host com controle do filesystem ainda pode apagar/restaurar marcador e banco juntos. Não há testemunha monotônica fora do host, nem autenticação nativa VFS/FD, nem reconciliação de COMMIT/recibo financeiro.
4. Não existe autorização para mudar \`UNCERTAIN=ZERO_AUTO_RESEND\`, fechar P0-4/5/6, selecionar fornecedor, custo ou implantar.

**Conclusão:** A237 fortalece a ordem solicitada de persistência de metadados no POSIX e mantém falha fechada; não substitui ensaios físicos controlados nem confiança externa.
