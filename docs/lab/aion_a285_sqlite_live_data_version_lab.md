# A285 — SQLite local data_version: alteração sem troca de inode (LAB)

**HARD NO-GO | seis P0: 0/6 | ZERO_AUTO_RESEND.**
Sem merge, deploy, Worker, corretora, provedor, pagamento, serviço
externo ou custos novos. As experiências usam SQLite **nativo**,
porém somente bancos descartáveis e registros sintéticos.

## O cenário que precisa continuar visível

A233 demonstrou restauração de bytes de um banco **depois** de fechar
a conexão. A240/A245 reforçaram controles locais de pathname e troca
visível durante a abertura, mas o P0-5 ainda exige confiança na
identidade/conteúdo do banco realmente utilizado. A285 trabalha em
uma fronteira complementar: **duas conexões SQLite reais abertas ao
mesmo tempo**, com alterações confirmadas por uma delas.

Uma conexão lê a sequência semântica **1 → 2 → 1** enquanto a outra
realiza duas atualizações SQL legítimas:
- O caminho e o inode continuam os mesmos.
- `PRAGMA quick_check` permanece `ok`.
- Um hash apenas do estado atual pode voltar a coincidir com um
  valor anterior; isso **não** prova a história intermediária.
- `PRAGMA data_version`, consultado pela **mesma conexão** antes e
  depois do COMMIT de outra, sinaliza a alteração.

Referência técnica primária:
https://www.sqlite.org/pragma.html#pragma_data_version

## Limite crucial do teste

`data_version` é propriedade **local da conexão**, não contador
monotônico autenticado:
- Não detecta alteração pela **própria** conexão observada.
- Uma nova conexão aberta **após** as alterações começa outra
  referência e não prova o que aconteceu antes.
- Não fecha a janela entre um check e uma operação (TOCTOU).
- Não autentica handle/VFS nativo nem resiste a host comprometido,
  rollback de todo o banco, queda física ou réplica divergente.

O experimento é uma **reversão de valor semântico via SQL**, não
uma restauração de bytes do arquivo vivo. Não o apresentar como
teste de perda de energia ou de ataques de VFS.

O `LocalDataVersionWatch` experimental retém um DENY local
quando vê versão diferente ou handle indisponível. Nunca devolve
autoridade positiva de leitura confiável ou de envio; até a resposta
`UNCHANGED_LOCAL_HINT_NOT_AUTHORITY` permanece inconclusiva.
Esse watch **não é** integrado ao `SQLiteChatStore` operacional.

## Testes e separação de autoridade

- `labs/a285_sqlite_live_data_version_lab.py`: laboratório puro,
  com `TemporaryDirectory` e duas conexões para DELETE e WAL.
- `labs/test_a285_sqlite_live_data_version_lab.py`: 20 cenários
  de alteração externa, retorno ao conteúdo original, reabertura,
  escrita na própria conexão, handle fechado, objeto hostil, and
  não autoridade.
- GitHub Actions Ubuntu/Windows: suíte A285 + regressões de
  SQLite A233/A240/A245/A248/A249, Outbox A267 e pesquisas A284→A282.

## Critério de saída mantido

P0-5/P0-6 continuam **abertos**, pois uma prova final exige vínculo
validado da identidade nativa, recuperação física/antirollback e
provas externas aplicáveis. `PRAGMA data_version` não substitui
custodiante independente. A pesquisa atual não concede SEND/RETRY,
não homologa P0 e não altera segurança de produção.
