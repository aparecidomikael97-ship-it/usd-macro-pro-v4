# AION FinOps — Auditoria das superfícies de custo existentes V1

**Data:** 08/10/2026  
**Prioridade:** meta inicial de até R$ 200/mês em despesas operacionais do proprietário  
**Estado:** IMPLEMENTATION SAFE — relatório estático CI-only, sem merge/deploy  
**Base:** PR #1075; cadeia FinOps #1070–#1074.

## Por que sair dos testes apenas simulados

As PRs #1070–#1075 prepararam contratos para orçamento, fila, reserva,
hardware e avaliação de modelos. Elas **não instalaram um interceptador
no código real que envia requisições**. Uma IA pode possuir excelente
teste de teto em um módulo isolado enquanto outro módulo ainda pode
enviar chamadas pagas sob autorização/budgetos diferentes.

Este relatório examina **oito arquivos conhecidos e concretos** da
branch, sem consultar o ambiente de produção. O scanner usa AST da
biblioteca padrão para identificar determinadas chamadas dentro de
funções Python — não faz import dinâmico dos módulos reais, não executa
rede, não procura chaves secretas e não tenta avaliar todas as 1.705
entradas do repositório. É deliberadamente parcial e não concede
autorização de alteração de produção.

## Evidências encontradas no código fonte

| Superfície | Evidência | Limite de interpretação |
| --- | --- | --- |
| `atlasquant_aion_provider.py` | `execute_openai_answer` chama `client.post` para a Responses API e usa `budget_decision` + orçamento estimado em USD, além de flags de habilitação e aprovação | O código **não chama diretamente** `preflight_owner_paid_request` (#1070) nem um método identificado de reserva durável de BRL. Isso exige auditoria e integração antes de confiar num teto global; não prova que houve cobrança real |
| `atlasquant_aion_model_gateway_v2.py` | `route_model_request` admite lane `LOCAL_DETERMINISTIC`, orçamento USD e roteamento sem executar provedor | A lane local pode representar lógica determinística; não certifica um modelo generativo de IA instalado, com RAM/VRAM/latência comprovadas |
| `atlasquant_aion_finops_metering.py` | Controles existentes de chamadas, tokens e `window_budget_usd` | Medição em USD não é automaticamente o teto mensal global BRL, nem impede cobrança diretamente no fornecedor |
| `atlasquant_aion_owner_brl200_finops_ceiling_v1.py` | Teto-meta de 20.000 centavos, limites de alerta e preflight que não aprova pagamentos | É planejamento, não interceptação real |
| `atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1.py` | SQLite `BEGIN IMMEDIATE` com guard de runner GitHub CI | Reserva efêmera não é ledger de produção, nem saldo real do banco/cartão |
| `render.yaml` | Serviço web Python definido; `autoDeployTrigger: off` | Arquivo de blueprint não prova estado atual de todos os serviços da conta Render, nem plano gratuito/pago, banco provisionado ou faturamento |
| `requirements.txt` | `requests` instalado como dependência declarada | Dependência HTTP não prova tráfego; a revisão deve incluir fontes de dados e outras chamadas de rede em etapa posterior |
| `atlasquant_aion_chat_render_production_composition_v1.py` | Configuração opt-in de PostgreSQL de produção | Não prova banco ativo, fatura real, custo ou persistência já habilitada |

### Gaps concretos, em ordem de importância

**P0 — fronteira de despesa:** é necessário projetar e testar a ligação
entre todas as chamadas pagas e o controle único de orçamento em BRL,
com reserva durável, escopo de cliente, autenticação de autorização,
limites por fornecedor e política de retry/timeout. O scanner estático
pode detectar nomes de chamadas, **mas não provar a ordem correta nem
a autenticidade dos parâmetros**. Requer testes de integração
adversariais e revisão de código. NÃO habilitar gateway de pagamento
apenas porque o scanner passou.

**P0 — fontes verdadeiras de despesa:** descobrir o inventário real de
assinaturas, cobranças por uso, compras anuais, renovação, impostos,
armazenamento, APIs de dados, voz/vídeo e infraestrutura; identificar
o que é pessoal versus do AtlasQuant; conferir faturas nas contas dos
fornecedores com aprovação do proprietário. Não transformar e-mails
de divulgação ou recibos antigos em mensalidades confirmadas hoje.

**P1 — limite dentro dos fornecedores:** contas de API e hospedagem
podem gerar cobranças externas mesmo que o AION esteja offline.
Configurar alertas e *hard limits* do próprio fornecedor quando forem
oferecidos; alguns produtos têm apenas avisos e NÃO um bloqueio
efetivo. Inspecionar isso manualmente antes do uso pago.

**P1 — IA local real:** coletar RAM, CPU, VRAM e armazenamento no PC
com consentimento, validar licença/bytes de modelos e fazer benchmark
concreto por tarefa, qualidade, latência, consumo de energia e carga.

**P1 — empresa paga seu custo:** custo por tenant, margem depois de
impostos, suporte, APIs e infraestrutura compartilhada. O teto R$200
não é promessa de suportar centenas de clientes 24h.

### Como verificar sem credenciais e sem deploy

`python scripts/aion_finops_known_cost_surface_audit_v1.py`

A ferramenta lê somente oito caminhos versionados explícitos, em
modo texto, com limitação de tamanho e rejeição de symlinks. Exibe JSON
com verificações, achados, riscos, caminhos relativos e hashes do
código. Não exibe conteúdo dos arquivos, parâmetros secretos,
tokens, valores de variáveis de ambiente, banco ou pastas pessoais.

A execução dentro do runner GitHub Windows/Linux valida apenas
**o estado da branch, não o da nuvem**. Ela retorna um estado
`KNOWN_COST_SURFACES_STATIC_REVIEW_REQUIRED` quando identificou
os arquivos conhecidos, inclusive seus gaps esperados, para orientar
a correção posterior. O teste passa **apesar de existirem lacunas
bloqueadoras para produção**; isso não significa sistema financeiramente
seguro. Rejeita a auditoria se desaparecer um endpoint conhecido,
o limite BRL ou a configuração de deploy desligado.

O arquivo `render.yaml` preserva a condição definida de
`autoDeployTrigger: off`. A PR não modifica esse arquivo.

## Limites não negociáveis

A auditoria NÃO confirma preço, boleto, saldo, fatura, consumo atual,
prestadores não listados, cobranças de APIs de mercado, renovação de
domínios, descontos de SaaS, orçamento completo ou custo mensal
efetivo. Não controla gasto real nem cancela assinatura. O teto-meta
de R$ 200/mês exclui computador, internet e eletricidade, que continuam
custos econômicos reais.

**Nenhuma alteração de gateway/adapter de produção, deploy, Worker,
merge, Render, banco, assinatura, API paga, computador do proprietário
ou configuração de chaves é autorizada nesta PR.**

### Próxima ação de maior valor

Em uma etapa separada, ainda em Draft, construir um interceptador
**executável com adaptador de rede falso** em testes de integração,
injetado ao limite conhecido `execute_openai_answer` e nunca
acionável com credenciais reais no CI. Mapear posteriormente cada
outro adaptador pago com evidência, e integrar uma reserva durável
somente após autenticação externa e aprovação explícita para
qualquer efeito real. Paralelamente, obter inventário de faturas
autênticas e benchmark no PC, ambos com consentimento do proprietário.
