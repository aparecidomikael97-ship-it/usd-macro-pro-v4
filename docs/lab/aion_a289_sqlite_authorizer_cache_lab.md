# A289 — SQLite authorizer cache: local revocation counterexamples

**AtlasQuant/AION LAB only. HARD NO-GO. P0 homologados 0/6.
ZERO_AUTO_RESEND. Sem Worker, provider send, ordens ou deploy.**

## O que foi confirmado antes de abrir a PR

No CPython 3.12 com SQLite nativo, um callback set_authorizer()
baseado num booleano dinâmico pode negar novas instruções e mesmo
assim permitir reexecutar uma instrução UPDATE previamente compilada.
A autorização é verificada na **compilação** SQL, não a cada etapa
de execução.

Fonte primária:
- SQLite: https://www.sqlite.org/c3ref/set_authorizer.html
- Python: https://docs.python.org/3.12/library/sqlite3.html

O Python usa cache de instruções compiladas (parâmetro
cached_statements). Não é seguro assumir que mudar uma variável
Python de "permitido" para "negado" revalida uma instrução cacheada.

## Experimentos nativos, sempre descartáveis

| Modo | Controle | Resultado esperado |
|---|---|---|
| cached_dynamic | UPDATE repetido, booleano de concessão retirado | Repetição pode executar sem novo callback, valor 1→2→3 |
| uncached_dynamic | cached_statements=0 | Nova compilação bloqueia repetição, valor final 2 |
| reinstall_after_revoke | set_authorizer(callback) novamente | Recompilação e negação, valor final 2 |
| distinct_sql | SQL textual diferente após revogação | Nova compilação e negação, valor final 2 |
| disable_authorizer | Conexão bruta invoca set_authorizer(None) | Remoção explícita do guard permite outra gravação |
| SELECT cache | SELECT compilado sob concessão, acesso depois revogado | Leitura cacheada pode retornar sem reavaliação |

Adicionalmente, o laboratório usa o verdadeiro
SQLiteChatStore(strict_local_data_version=True) da A288 para escrever
diretamente em store.db, na mesma conexão, sem o marcador de commit
protegido. data_version local não muda; saúde e quick_check continuam
verdes. Isso demonstra precisamente um **limite** do guard A286/A288:
o objeto Python de conexão bruta não é uma fronteira de confiança.

## Interpretação proibida

- "Desativar cache" ou "reinstalar autorizer" só altera este
  contramodelo local. Não autentica o código proprietário, o FD/VFS
  nativo, o histórico de intents, o host, o disco nem um witness externo.
- Uma parte com acesso à própria conexão Python consegue desabilitar o
  authorizer. Logo o callback não é uma autoridade independente.
- Os resultados dependem de versão da API e cache; por isso CI executa
  provas reais em Ubuntu e Windows Python 3.12. Não se admite resultado
  inventado/simulado como teste da API.
- A escrita direta no LAB demonstra a necessidade de não expor a
  conexão bruta e reforça o requisito de custódia externa. Não autoriza
  reenvio automático, recuperação silenciosa nem operações reais.

## Bateria

16 casos novos A289, regressões A285–A288, sem novas dependências.
Usa GitHub Actions padrão (Ubuntu/Windows) gratuito para este
repositório público. Nenhum arquivo do núcleo operacional é modificado.

**Próxima decisão:** avaliar uma interface de escrita sem exposição de
store.db em um candidato isolado; mesmo isso não homologaria P0-5/P0-6.
