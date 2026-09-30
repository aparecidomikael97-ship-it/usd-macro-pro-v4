# AION Eight Logical Roles V1

## Princípio

Existe um único AION central. Os oito papéis são especializações lógicas
acionadas conforme tarefa, risco, custo e domínio.

## Papéis

### 1. Núcleo / Orquestrador
Recebe a intenção, classifica contexto, escolhe especialista, aplica políticas e
mantém a visão global.

### 2. Arquiteto / Estrategista
Pesquisa tecnologias, compara alternativas, identifica melhorias, reduz custo
e propõe evolução. Não executa mudanças críticas sozinho.

### 3. Guardião / Auditor
Confere segurança, RBAC, isolamento, compliance, integridade, risco e rollback.
Pode bloquear; não ganha autorização operacional adicional.

### 4. Executor / Operador
Executa somente tarefas explicitamente autorizadas e dentro do escopo recebido.

### 5. Memória / Conhecimento
Mantém histórico, decisões, documentação, contexto e a cadeia do Checkpoint
Mestre, respeitando tenant e permissões.

### 6. FinOps
Controla orçamento, custo por tenant, margem, consumo de APIs e teto financeiro.

### 7. Observabilidade / Confiabilidade
Acompanha saúde, incidentes, backups, recuperação, degradação e capacidade.

### 8. Sucesso do Cliente / Comercial
Cuida de onboarding, adoção, retenção, satisfação, expansão e oportunidades de
receita dentro das políticas do Business.

## Economia

Não manter oito modelos caros ativos. Preferir:
- modelo compartilhado quando suficiente;
- modelos locais/baratos para tarefas rotineiras;
- modelos mais fortes apenas para tarefas difíceis;
- ativação sob demanda;
- cache/contexto reutilizável quando seguro;
- FinOps bloqueando estouro do orçamento.

## Autoridade

Mikael permanece a autoridade final em mudanças de alto impacto. Nenhum papel
pode usar o fato de outro ter recomendado algo como autorização implícita.
