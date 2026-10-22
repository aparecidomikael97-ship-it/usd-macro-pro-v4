# AION P0 A142 — SQLite URI `mode=rw` sem recriação implícita após race (LAB)

**Data local: 21/10/2026.** Base #1425 (A141). Somente branch LAB empilhada/Draft, sem merge, deploy, Worker, restart real, acesso a provedor/mercado ou gasto.

## Falha reproduzida e correção

Em `_connect` do ledger A140/A141, a sequência `_check_path()` → `sqlite3.connect(str(path))` permitia, por comportamento padrão da API SQLite, que uma conexão RECRIASSE o arquivo de quota se um outro agente o removesse entre as duas operações. A segunda checagem de identidade normalmente bloqueava o uso, mas o arquivo vazio já existia. Isso viola a expectativa de nenhum novo banco surgido de um caminho de operação.

**RED-first:** [CI #39698229386](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39698229386), Ubuntu **2 FAIL / 9 PASS** entre 11 novos testes: `test_01` (conexão sem `uri=True`/`mode=rw`) e `test_03` (arquivo criado após remoção durante `sqlite3.connect`). Nenhuma gravação ou consumo real foi realizada.

**Correção LAB:** `sqlite3.connect(self.path.as_uri()+'?mode=rw', uri=True, timeout=0.25, isolation_level=None)`. A API agora EXIGE que o arquivo exista; se sumir após a checagem inicial, SQLite falha sem recriar o banco. `Path.as_uri()` codifica os caracteres de caminho `#`, `%`, espaços e `&`; o teste contempla o mesmo código em Windows e Ubuntu. A inicialização A140 continua explicitamente usando abertura exclusiva `xb` somente quando não há arquivo, seguida de conexão sem permissão de criar.

**Portabilidade:** o primeiro ensaio pós-correção passou no Ubuntu, porém a fixture de testes usou `?` em nome de diretório — inválido em Windows (`WinError 123`) e não uma falha SQLite. A fixture foi ajustada para caracteres permitidos em Windows. Não houve alteração de asserts, seleção de suítes, waivers nem contorno do gate.

## Prova direcionada

- [CI GREEN #39698468900](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39698468900): **11 A142 + 22 A141 + 45 A140 + 30 A139 + 25 A138 + 14 contratos = 147 PASS por SO, 294 PASS total**.
- Os 11 testes novos incluem URI mode=rw observada por mock, caracteres especiais e falta do DB entre checagem e connect, nenhuma recriação no caminho de reserva, read e output, comportamento normal de reserva/digest e marcações honestas sobre custódia externa.
- A Quality/Security originais serão executadas no commit final. Não modificar baseline de 85 falhas históricas.

## Limites de autoridade e execução

1. **Ainda existe auto-bootstrap em `SQLiteLabReservationLedger.__init__` se o DB não existir.** Um NOVO objeto depois de exclusão completa do banco pode inicializar DB vazio e readmitir um run_id. A142 corrige apenas operações em instância existente; NÃO é no-create global nem recuperação confiável após restart. Próxima mudança deverá separar bootstrap explicitamente autorizado de admissão de DB já matriculado.
2. `mode=rw` NÃO significa read-only; permite atualizar um banco existente. A segurança de escrita depende de ACL real, política de processo e integridade do destino. O token GitHub deste workflow é `contents:read` e scripts de fornecedores não são chamados.
3. Não foi criado vínculo atômico ao handle do diretório ou do banco: continuam possíveis janelas TOCTOU/ABA/junction, sob atacante local privilegiado, além de problemas de acesso concorrente e armazenamento comprometido.
4. `mode=rw` não detecta rollback válido de arquivo in-place nem nova instância após rollback. High-water por instância A141 não tem autoridade externa e não sobrevive a reinício.
5. Nenhum Ed25519 assinado com chaves sintéticas autoriza produção. Não existe emissão, custódia, leitura autenticada de latest head, CAS monotônico, owner autenticado nem recibo de efeito/no-effect do fornecedor aprovado no P0.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND · SEM MERGE, DEPLOY OU GASTOS.**