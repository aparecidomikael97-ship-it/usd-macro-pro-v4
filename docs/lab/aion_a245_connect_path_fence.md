# A245 — Pre/post-connect SQLite pathname fence (LAB, P0-5 / P0-6)

Status: **HARD NO-GO · 0/6 P0 homologadas · apenas LAB · sem merge, Worker ou deploy**.

## Problema

A240 compara `(st_dev, st_ino)` capturado **depois** de `sqlite3.connect()` com o nome do arquivo nas operações seguintes. No entanto, um arquivo existente pode ser substituído entre o `connect()` e o primeiro `stat()`: a conexão pode estar presa ao arquivo antigo, enquanto o `stat()` e as operações futuras reconhecem o arquivo novo como identidade inicial. Não há prova do descritor nativo aberto.

## Mudança limitada, verificável

No `SQLiteChatStore.__init__`, para banco que **já existe**, ler `stat(follow_symlinks=False)` antes do `connect()`, rejeitar alvos não regulares e comparar `st_dev/st_ino` com o resultado pós-conexão. Troca visível do arquivo nesse intervalo causa `StorageUnavailableError` e fechamento da conexão. Bancos novos continuam podendo ser criados; estes não adquirem prova de origem.

## Testes A245

1. Banco novo abre e passa no gate estrutural.
2. Banco existente é reaberto sem falso bloqueio.
3. Mudança simulada de inode durante `connect()` é recusada em qualquer SO.
4. Substituição real via `os.replace()` logo após `connect()` é recusada onde o SO permite; caso contrário, **SKIP** justificado.
5. Symlink preexistente é recusado **antes** de conectar.
6. Reportagem `healthy` continua significando somente integridade estrutural/local.
7. **XFAIL intencional:** após fechar conexões, dois registros confirmados são restaurados para um snapshot antigo escrevendo no **mesmo inode**; reabrir o SQLite ainda passa, mas deveria recusar. O resultado não conta como correção.

## Riscos que continuam sem resposta

- Troca ocorrida entre o pré-`stat` e o `connect` com substituição/ABA que devolve mesmo inode, ou objeto aberto diferente do nome: **P0-5 aberto**. Python `sqlite3` não fornece identidade autenticada do VFS/FD.
- Rollback dentro do mesmo inode ou após reiniciar o host, sem piso monotônico independente: **P0-5/P0-6 abertos**.
- WAL, garantias de COMMIT/ACK, queda física de energia e reconhecimento de efeito externo: **P0-6 aberto**.
- Nenhuma testemunha externa, chave de custódia ou assinatura de origem foi implantada; `healthy` não significa confiança contra adversário.
- Testes de LAB e XFAIL são evidência de **limite**, jamais homologação. Nenhum resend automático de estado UNCERTAIN.

O próximo passo de segurança exige evidência fora do host e verificação independente do FD/VFS em ambiente compatível. As seis P0 permanecem em HARD NO-GO.
