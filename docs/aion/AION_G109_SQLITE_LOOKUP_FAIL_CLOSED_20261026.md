# AION G109 — Falhas SQLite no registro final da reserva (LAB)

Data: 2026-10-26. Base: G107 PR Draft #1598. PR: #1599. Sem merge nem deploy.

**Reprodução RED** — [run 40360398619](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40360398619): Ubuntu 50 testes, 4 erros; Windows 50 testes, 4 erros. As falhas foram tabela SQLite ausente, sqlite3.OperationalError, sqlite3.DatabaseError e sqlite3.ProgrammingError. A consulta final de G107 não convertia essas falhas, e o callback de admissão não as capturava. O Outbox já continha uma barreira adicional, que negava o envio em caso de exceção.

**Correção LAB:** a consulta local converte sqlite3.Error ou OSError em CustodyUnavailable, fecha a conexão via contextlib.closing e não recria uma tabela ausente. O verificador de admissão agora também captura sqlite3.Error diretamente e retorna literal False. Falha posterior à reserva mantém operação incerta/gasta, nunca autoriza reenvio automático. Nenhuma regra de provider SEND ou Worker foi alterada.

**GREEN** — [run 40360641263](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40360641263): Windows 50/50 aprovados; Ubuntu 50/50 aprovados. Os testes incluem os controles G107 herdados e conferem operação UNCERTAIN, zero envios simulados e custódia com contador 1 após uma falha de leitura.

**Auditoria canônica A184 na mesma alteração** — [run 40360641040](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40360641040): Ubuntu Quality 6449/6449; Security unittest 368/368; Security pytest 2825/2825; pip-audit sem vulnerabilidades conhecidas. As cinco exigências externas continuam reprovadas em Windows e Ubuntu, sem waivers.

**Limites:** chaves, consultas e atestador ainda são sintéticos e controlados pelo host. Esses testes não constituem custódia realmente independente, raiz externa protegida, autenticação imutável da identidade de negócio, identidade nativa VFS ou garantia pós-rollback e primeiro SEND real.

0/6 P0 homologadas. HARD NO-GO. Sem merge, deploy, Worker, envios reais ou fundos.
