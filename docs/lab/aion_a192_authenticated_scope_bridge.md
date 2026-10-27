# AION A192 — senha verificada + leitura SQLite real (somente LAB, sem implantação)

Data: 2026-10-27. **0/6 P0 homologadas / HARD NO-GO.**

## Qual lacuna estamos enfrentando?

A191 mostrou que SQLiteChatStore separa dados corretamente *quando recebe* o Scope
correto, mas um caller com acesso ao objeto Python Scope ou ao banco consegue
criar outro Scope. Isto não é autenticação.

A192 ensaia uma fronteira de leitura **local** que:
1. Confere a senha com o autenticador PBKDF2 existente do projeto, contra o
   cadastro AccessUser fornecido pelo serviço, jamais por texto/claims do prompt.
2. Exige ADMIN ativo e um vínculo de owner/tenant/workspace obtido de configuração
   de servidor de laboratório, sem aceitar role, owner_id ou tenant_id do pedido.
3. Permite somente **AION, Trader e Investimentos pessoais**. Negócios permanece
   congelado (não há permissão de read nessa fachada).
4. Recupera uma conversa real por SQLiteChatStore usando o Scope derivado.
5. Nega senha errada, usuário inativo, perfil divergente, ausência de registro,
   outro owner, tenant ou workspace, path injection e exclusões/revogações.
6. Jamais executa tarefas; não fornece token, permissão geral, trade, cobrança,
   chamadas de nuvem, provider ou execução de Worker.

**Não confundir com login pronto para rede:** a prova é um fluxo síncrono
local senha→perfil da fixture→SQLite. Não estabelece MFA, sessão HTTP protegida,
cookies seguros, CSRF, credencial real do HUMAN_OWNER, ACL nativa do sistema
operacional, custódia externa ou proteção da própria configuração.

## Quatro contraexemplos RED documentados

- O helper existente has_permission() recebe só uma role auto-declarada;
  isso NÃO autentica usuário (a ponte A192 deliberadamente não confia nele).
- Qualquer código que obtenha a referência do SQLiteChatStore pode construir
  Scope com strings conhecidas e acessar outro escopo. A ponte não corrige
  consumidores que contornem a fronteira.
- Com SQLiteChatStore fechado, a chamada crua get_conversation ainda dispara AttributeError. A fachada A192 devolve STORE_CLOSED de maneira controlada, sem fallback e sem alterar o store original.\n- Se o atacante controlar simultaneamente cadastro AccessUser e perfil OWNER
  'do servidor', ele pode autenticar sua própria senha e vincular-se à
  identidade de outrem. **Não existe raiz externa independente hoje**.
  A função A192 não resolve root enrollment, P0 G122 ou anti-rollback.

Os quatro testes mostram o fato e imprimem RED. O sucesso desses testes representa
um contraexemplo confirmado, NÃO uma vulnerabilidade corrigida.

## Critérios para a próxima etapa

- Identificar o entrypoint de chat real e onde autenticação ocorre, antes de
  qualquer ligação ao runtime. **Não ligar A192 automaticamente**.
- Autenticar a requisição por sessão validada pelo servidor, sem aceitar
  credenciais/claims como base de IAM nem confiar em metadados do cliente.
- Impedir acesso ao SQLiteChatStore fora da camada autorizada, sob revisão;
  proteger credenciais, processo, sistema de arquivos e dados cifrados.
- Testar resolução de Scope após logout, troca de senha, revogação, concorrência,
  transição de workspace e substituição de root com adversário real.
- Não converter esta bateria em homologação P0; G122 externa continua RED.

## Limites e prioridade

Negócios congelado por decisão expressa do proprietário em 27/10/2026;
sem desenvolvimento comercial adicional e sem apagar histórico anterior.
Zero serviços novos pagos até 05/11/2026; a partir de 06/11 apenas reavaliar,
somente após autorização expressa para qualquer contratação.

A192 não altera componentes de produção: **duas fontes de LAB,
documentação, workflow Windows/Ubuntu**. Sem AWS, Sign, dados de cliente, reais,
cobrança, Worker, provider SEND, trades, merge ou deploy.
