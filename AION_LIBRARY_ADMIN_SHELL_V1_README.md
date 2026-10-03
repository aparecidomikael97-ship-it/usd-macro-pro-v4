# AION Biblioteca — Admin Workspace Shell V1 (SANDBOX ONLY)

Checkpoint de implementação para a issue de segurança #477, empilhado sobre a Draft PR #487 do AtlasQuant/AION. Este **não** é o Portal do Cliente nem libera a ingestão de PDFs.

## O que está preparado

- Novo workspace `📚 Biblioteca` dentro da área administrativa AION, sem alterar a tupla das **nove áreas históricas**. A opção só entra no seletor quando o próprio host satisfaz todos os controles abaixo.
- Gate independente que exige, simultaneamente: `ATLASQUANT_ENV=SANDBOX`; `AION_LIBRARY_SHELL_PREVIEW=true` definido exclusivamente por configuração do servidor; modo `AUTHENTICATED`; sessão `ADMIN` íntegra; usuário ativo, cargo e fingerprint presentes no **registro atual**; permissão administrativa atual; validação existente de tempo absoluto/ociosidade.
- Ao desligar a flag ou perder autorização, uma seleção antiga da Biblioteca volta para `🧠 Central` antes da montagem da interface.
- Interface textual responsiva com estado claramente bloqueado, pendências técnicas e sem botões, upload, banco de dados, API, chaves, consentimentos falsos nem acesso a conteúdo.
- Um módulo puro `atlasquant_aion_library_workspace_shell.py` e testes isolados; mudanças mínimas em `atlasquant_aion_admin.py` e workflows. 

## Estados obrigatórios

A tela é **somente informativa** mesmo no sandbox. A visibilidade do menu não significa autorização para visualizar dados. O código **não instancia** o adaptador PostgreSQL #487, não busca documents, não chama provedores nem escreve dados. A flag não pode ser alterada pelo cliente, prompt, parâmetro URL ou estado da tela.

O login atual do AtlasQuant continua sendo a autoridade de navegação; futuras leituras exigirão a ACL persistente por usuário/tenant/domínio, autorização de cada requisição no host e verificação da cadeia de auditoria PostgreSQL; todas essas rotas continuam **desligadas**. `OPEN`, `PREVIEW`, `PRODUCTION`, `LOCAL` e `TEST` não liberam nem esta casca.

## Verificação

- Local: teste do módulo em fixture compatível do login (não no app completo), 27 testes descobertos, 26 executados, 1 teste de ligação ao módulo administrativo reservado para o checkout completo do GitHub. Suíte local consolidada (incluindo contratos anteriores): 448 testes descobertos, 425 executados, 23 ignorados (22 PostgreSQL + 1 ligação administrativa). Nenhuma falha; compilação Python aprovada.
- A validação definitiva do novo bloco exige que o GitHub execute a suíte usando `atlasquant_access_control.py`, `atlasquant_access_panel.py` e o `atlasquant_aion_admin.py` reais da branch. A atualização do workflow inclui compilação do arquivo administrativo e verificação estática de ligação do menu. Não afirme que a UI foi renderizada em navegador a partir desses testes.
- O backup incremental neste ZIP inclui **apenas arquivos novos** e instruções de ligação. As modificações reais no módulo administrativo existente e workflows pertencem à Draft PR da branch, não ao pacote ZIP.

## Pendente antes de qualquer exposição operacional

1. Persistir ACLs e revogações no servidor; restringir o PostgreSQL com credenciais SELECT-only; montar a fachada #487 apenas na camada backend autenticada, com verificação por operação.
2. Testar a interface verdadeira em Android/PC (navegação, sessão vencida, isolamento por tenant, concorrência, logs, cache e estado de erro), sem vazamento de metadados.
3. Validar direitos/licenças reais e custódia externa da auditoria; ensaio de backup externo/PITR; revisão independente de segurança.
4. Revisão administrativa por Mikael antes de **qualquer** merge, deploy, ativação de flags ou ingestão. Nunca usar a aprovação desta casca como autorização para conteúdo/produção.

A PR #472 e a área Negócios permanecem separadas. A tarefa #483 do AION English não sofre alterações.
