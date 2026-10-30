# A299 — Revisão P0-5/P0-6: SQLite nativo, WAL e limites de prova

**LAB isolado. HARD NO-GO. P0 homologadas: 0/6. ZERO_AUTO_RESEND.**
Sem merge, Worker, deploy, fornecedor, operação financeira, cliente real,
contratação, carregamento de extensão C ou mudança no core de produção.

## Fontes efetivamente examinadas

O código C de G17/G18 foi lido diretamente do commit
`2d4c1b51b8fc968c7ec57b4d6d150abdecfd08d5` da
[PR #1505](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1505).

- [G17 #1504](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1504):
  `labs/a190/aion_g17_native_handle_extension.c` chama
  `sqlite3_context_db_handle` no **mesmo SQLite** que executou o SQL
  e `sqlite3_file_control(..., SQLITE_FCNTL_HAS_MOVED, ...)`.
  Teste isolado Linux 8/8 no PR, não integrado ao runtime.
- [G18 #1505](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1505):
  `labs/a190/aion_g18_win32_native_identity_extension.c` usa
  `SQLITE_FCNTL_WIN32_GET_HANDLE` e
  `GetFileInformationByHandle`. 10/10 testes Windows no PR.
  **Contraprova reproduzida:** após trocar o banco fechado por clone
  antigo, a identidade nativa volta a conferir, mas o conteúdo lido
  é **ERRADO** (`WRONG_CONTENT_NATIVE_MATCH_RED`).
- [A245 #1696](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1696):
  checagem pre/post `connect` do caminho/inode, sem prova VFS/FD.
- [A292 #1743](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1743):
  6 escritores de chat × 2 falhas sintéticas de ACK, com dois
  auxiliares privados SQL sem marcador se chamados diretamente.
- [A293 #1744](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1744):
  alteração por outro processo e rollback de banco fechado aceito
  como saudável, mesmo no modo opt-in estrito após novo startup.

Os commits e descrições destes PRs não equivalem a revisão independente
da cadeia de fornecimento do binário, instalação ou homologação de P0.

## Novo experimento nativo A299 — cópia de somente `.db`

AION `SQLiteChatStore` usa `journal_mode=WAL`.
Com um banco **temporário**:

1. Criamos uma conversa, forçamos checkpoint inicial com
   `PRAGMA wal_checkpoint(TRUNCATE)` para ter schema e conversa no
   arquivo `.db` principal.
2. Criamos uma mensagem real do AION; o COMMIT retorna confirmação.
   Outra conexão SQLite **vê** a mensagem (via WAL).
3. Enquanto a conexão original ainda está aberta, copiamos **só**
   os bytes do `.db` principal com `shutil.copy2`, sem `-wal`.
4. Em paralelo fazemos um backup via a API nativa
   `sqlite3.Connection.backup`, que lê o estado transacional completo.
5. Comparamos as duas cópias, sem tocar o banco original.

**Hipótese adversarial esperada:** a cópia só do principal **não contém
a mensagem confirmada**, mas o backup SQLite contém. O marcador local de
COMMIT está ausente porque o ACK normal foi recebido. Assim, a ausência
de marcador não torna uma cópia física parcial íntegra/durável.

Este teste demonstra comportamento do **WAL de SQLite**, não um defeito
novo do mecanismo de backup normal do AION. Nunca usar a cópia insegura
em dados reais.

## Leitura crítica do código atual

A299 lê estaticamente `aion_chat/store.py` por AST para separar:

| Medida local presente | Limite de confiança |
| --- | --- |
| `_pathname_binding_reason` e identidade do caminho | Não identifica bytes realmente lidos nem FD nativo autenticado |
| `PRAGMA data_version` opt-in | Detecta alguns commits de outra conexão **depois** do efeito |
| Marcador antes de `self.db.commit()` | Coordenador local removível por host; ACK perdido continua UNKNOWN |
| G17/G18 como PRs Draft | C nativo experimental, não carregado ou autorizado no core |

O código A299 **não compila nem carrega** o G17/G18. Extensões
`sqlite3` nativas não assinadas podem executar código arbitrário;
a revisão de segurança e cadeia de fornecimento precedem qualquer
discussão de integração.

## Bateria negativa cruzada

Reexecutar:

- Processo externo grava na SQLite sem passar pelo marcador local.
- Substituição do banco após fechamento reintroduz histórico velho.
- COMMIT grava a mensagem e depois perde o ACK: sticky UNCERTAIN,
  bloqueio de retry e ZERO_AUTO_RESEND.
- Chamadas Python dos auxiliares privados SQL contornam o marcador.

Passar nestes testes significa que continuamos conseguindo **reproduzir
as limitações**, não que estejam corrigidas.

## Próximo avanço gratuito sugerido

**P0-5:** revisão independente do código-fonte G17/G18 e desenho de
vínculo FD/VFS do handle realmente usado, incluindo WAL/SHM e
resistência a rollback do mesmo conteúdo. Nenhuma instalação.

**P0-6:** expandir ensaios de checkpoint, recuperação pós-queda,
durabilidade real e reconciliação de ACK, sem SEND real e com
testes canônicos RED preservados.

```bash
python -m unittest -v labs.test_a299_sqlite_native_p0_5_6_gap_lab
```

**GO-LAB apenas se a CI passar; NO-GO integração; HARD NO-GO real;
0/6 P0.** Nenhuma compra ou novo serviço.
