# A190 G16 — SQLite file_control na conexão nativa (LAB isolado)

## Motivação e escopo

G14 guardava o nome e um UUID local; um clone preservando UUID enganou leitura. G15 mostrou que inferir o descritor a partir de `/proc/self/fd` pode associar a conexão errada a um descritor legítimo.

G16 usa **exclusivamente SQLite sqlite3_file_control associado à própria conexão aberta**, exposto por APSW apenas nos testes de laboratório. O runtime existente do AION continua na biblioteca-padrão Python `sqlite3`, sem importar APSW, sem instalação em produção e sem migrar dados.

### API C documentada

- `SQLITE_FCNTL_HAS_MOVED` (opcode 20): pede ao VFS da conexão que informe se seu arquivo foi movido. Em VFS sem suporte, nega.
- `SQLITE_FCNTL_WIN32_GET_HANDLE` (opcode 29): pede ao VFS Windows o **HANDLE real da conexão**; compara `GetFileInformationByHandle` no handle retornado e em um segundo anchor de caminho; identidade OS **local** apenas.
- `Connection.file_control("main", code, pointer)` da APSW chama o SQLite real. Cuidado com buffer vivo e negação para opcodes sem suporte.

Fontes primárias:
- SQLite: https://www.sqlite.org/c3ref/file_control.html
- SQLite opcodes: https://www.sqlite.org/c3ref/c_fcntl_begin_atomic_write.html
- APSW (autor do pacote): https://rogerbinns.github.io/apsw/connection.html
- Windows File ID: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle

### O que testar

1. Arquivo original aberto de modo legítimo: `HAS_MOVED=0` se VFS dá suporte.
2. No Linux, mesmo pathname transitório e clone com mesmo marcador: `HAS_MOVED=1` deve distinguir o arquivo real aberto.
3. No Linux, conexão errada pré-aberta + conexão decoy correta: consultas à **conexão exata** devem retornar observações diferentes, evitando o falso-positivo do G15.
4. No Windows, extrair HANDLE do SQLite, obter `volume serial + file index` e comparar com segundo HANDLE do arquivo esperado; demonstrar caminho correto e caminho distinto.
5. VALIDE apenas em bancos temporários sintéticos; `WAL` e `-shm` não provam custódia externa.
6. Falsos componentes de `file_control` controlados por host continuam capazes de fabricar resultados; sem identidade confiável do componente, o status é meramente diagnóstico.

### Limites da evidência

Mesmo resultado positivo só confirma um **recorte local da conexão APSW que rodou o teste**, no instante da consulta. Não valida:
- conexão `sqlite3.Connection` atualmente usada pelo serviço, compatibilidade total ou integração ao AION;
- prova de conteúdo legítimo, integridade de `-wal`/`-shm`, replay, rollback ou custódia externa;
- adversário com privilégios de host, VFS adulterado, fornecedor ou identidade do proprietário;
- operação sobre todos os tipos de filesystem Windows, ReFS, SMB etc.

A plataforma sem suporte ou resultado incerto deve ser **DENY**; efeitos já realizados continuam `UNCERTAIN` e **nunca** autorizam reenvio.

**0/6 P0 homologados · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.**

## Dependências e custos

APSW `3.54.1.0` fixada no workflow CI **somente para LAB**, instalada como wheel de PyPI `--only-binary=:all:`. Nenhuma dependência adicionada ao runtime ou implantação; nenhuma credencial nova, provedor pago, Worker ou serviço externo.
