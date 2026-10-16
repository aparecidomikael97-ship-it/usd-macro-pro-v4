# AtlasQuant Negócios — desenho executável de integração V1.3 (LAB)
Data: 16/10/2026 · Estado: INSPEÇÃO DE CÓDIGO + CONTRATO DE ACEITE; NÃO É INTEGRAÇÃO IMPLEMENTADA, NÃO É PRODUTO COMERCIAL.

## Fonte imutável efetivamente verificada
Base: commit 99d1bc427a84487f3c1d9688161085ec3c0ea8bf (UI V1.2), ainda não integrada na main.
- labs/negocios_operational_v11/contract.py — Git blob bb1a53de64ec51ba30b2aea4157bb0f068add444; interface efetiva review_record(record, now, review_cutoff), advance_stage(current, target, actor_tenant), render_proposal(scope, price_label), privacy_summary(checklist), request_external_action(action).
- labs/negocios_operational_v11/test_contract.py — 45 casos sintéticos, Git blob 1cff624c3a23f07b39ad355c8ba7aba20814fe28.
- labs/negocios_ui_v12/index.html — blob 36fafccd3b9b971daa31ad84ae4384b8974d38ac; cinco páginas e eventos locais em JavaScript, sem backend autenticado e sem persistência.
- labs/negocios_ui_v12/test_adversarial.py — blob 128db89ef6a9f6b702ecd496e12ac65512468bb6; resultados anteriormente registrados 12/12, NÃO reexecutados nesta rodada.
- atlasquant_aion_business.py e atlasquant_aion_admin.py::_render_business: já têm métricas de negócio/produtos e cockpit interno. atlasquant_sales_center.py é Portal Comercial distinto, não motor CRM B2B.

## Problema concreto
A UI V1.2 chama diretamente funções JavaScript locais e mantém state/tab/stage no navegador; o contrato V1.1 é um oráculo Python puro. Ainda NÃO existe caminho real caso cadastrado -> validação autorizada -> transição guardada -> acompanhamento persistido -> proposta revisável. Unir as telas visualmente não constitui integração, e aceitar actor_tenant passado pelo navegador seria um bypass de isolamento.

## Menor vertical slice honesto — uma única empresa FICTÍCIA
1. Operador entra pelo cockpit INTERNO de Negócios, somente quando futuro backend comprovar sessão e RBAC. No LAB, simulação isolada sem login real nem tratamento de PII. Clientes não verão esta aba.
2. Entrada CONSULTA: gerar case_id sintético e tenant_id imutável, owner_id, state, updated_at com fuso, next_action e due_date. Separar registro de qualificação, estoque e recebimento; nenhum desses estados pode se transformar em outro automaticamente.
3. Em cada consulta/revisão, invocar review_record com now e cutoff explícitos, mostrar warning codes e evidência sintética. Não executar follow-up; vencimento gera pendência, não mensagem.
4. Transição de etapa: primeiro escopo de identidade no servidor (FUTURO, hoje ausente); em laboratório não alegar autorização. Chamar advance_stage somente como VALIDADOR do modelo e registrar motivo. Qualificação exige need_identified, can_serve, interest_to_proceed; OPORTUNIDADE também decision_path_documented, owner e next_action; não pular estágio. Remoção de critério reabre revisão, não mantém falso status positivo.
5. Proposta: render_proposal devolve RASCUNHO NÃO ENVIADO, preço estimado e aviso de ausência de garantia; nenhuma funcionalidade de envio, assinatura ou pagamento. É necessário revisor humano e futuro filtro jurídico/comercial antes de qualquer comunicação real.
6. Painel mostra somente contagens de casos sintéticos, pendências e próximo prazo calculados a partir do mesmo estado revisado; nunca converte orçamento em receita/recebimento. Exibir UNKNOWN/NÃO VERIFICADO e fonte fictícia.
7. Ações SEND, PAY, CHARGE, RESERVE_STOCK, IMPORT_PII, DEPLOY e ENABLE_WORKER permanecem recusadas pelo contrato; frontend NÃO é barreira de segurança.

## Desenho técnico mínimo para futura implementação
Fluxo proposto: UI V1.2 (view) -> controlador local LAB sem endpoints de rede (demonstrativo) -> modelo V1.1 (validadores puros) -> snapshot sintético efêmero (sem persistência de cliente) -> UI.
Somente após desenho de segurança e aprovação específica: backend autenticado -> sessão validada e mapeada em tenant/owner/workspace servidor-side -> RBAC de rota e objeto -> repositório transacional por tenant -> serviço de domínio -> trilha auditável, sem cross-tenant. NUNCA copiar role, tenant_id ou resultado CONFIRMED de body/cookie/JavaScript para autorização.
Implementar composição, NÃO duplicar outro motor paralelo ou fundir CRM com Portal Comercial. Congelar arquivos originais V1.1/V1.2 antes de qualquer patch, criar filha Draft isolada V1.3, executar testes RED na UI antiga antes da mínima integração.

## Gatilhos negativos obrigatórios (aceite funcional e de segurança)
A. Quatro critérios incompletos -> permanece CONSULTA/NAO_QUALIFICADO, nenhuma oportunidade.
B. Qualificação completa com fonte sintética -> somente estágio SIMULADO; não prova contratação.
C. Remover interesse/decisão após promover -> UI e snapshot não continuam exibindo OPORTUNIDADE válida.
D. Tenant A tenta ler/alterar caso de tenant B -> no futuro DENY no backend antes de leitura/escrita; no LAB não alegar RBAC implementado.
E. Próximo prazo vencido -> banner de pendência, zero mensagens.
F. Contato RECUSOU/DESCONHECIDA -> sem disparo mesmo com qualificação completa.
G. Quantidade requerida 4, observada 2 -> insuficiente; rótulo disponível não sobrepõe número.
H. 0.005, notação exponencial, número negativo ou não finito em moeda/estoque -> não aceito; centavos inteiros sem arredondar.
I. Recebido parcial e estado CONFIRMADO -> alerta; nenhuma confirmação bancária afirmada.
J. Proposta com preço/escope inválido -> erro; texto válido permanece RASCUNHO; revisão humana obrigatória.
K. Texto contendo promessa enganosa -> aviso didático não é certificação; não enviar.
L. Checklist LGPD inteiro marcado -> ainda não certificado; não habilitar import de PII.
M. Dois cliques sobre avançar, retorno de página e reinício -> sem avanço silencioso ou contagem duplicada.
N. Falha/desconexão/reload de snapshot -> estado demonstrativo UNKNOWN, não converter em sucesso.
O. Atalho direto para ações sensíveis (inclusive via import Python) -> request_external_action nega.
P. Desktop e mobile: navegação, teclado, aria-current, estados de erro e edição real em formulário DEMO, sem botões ficticiamente operacionais.

## Portas de saída (não atendidas hoje)
G0: modelo sintético coeso, cinco telas V1.2 + oráculo V1.1 preservados; documentação ligada a bugs reais.
G1: testes de integração no mesmo HEAD (contagem real reportada), RED antes de patch, GREEN/Win+Linux quando viável; sem rede nem dados reais.
G2: proprietario aprova revisão de RBAC/autenticação server-side, armazenamento e LGPD, isolados dos bloqueios Core; auditor de segurança confirma ausência de cross-tenant.
G3: revisão trabalhista/fiscal e autorização específica ANTES de cliente, cobrança e acesso a dados.
G4: ativação AION/Worker continua HARD NO-GO: H0/F1/T1/F2 físicos/externos não comprovados, 0/6 P0 homologados e 20/20 FIRST_INSTALL BLOCKED; ZERO_AUTO_RESEND.
G5: medição real do tempo do HUMAN_OWNER após piloto aprovado; sem prometer renda em poucos dias, mensalidade ou ROI sem prova.

**Missão Codex paralela diferente:** hardening financeiro finito em branch LAB local antiga, sem alterar os arquivos V1.1/V1.2 acima. Este documento é o plano de composição a ser testado em versão posterior; não é código executado, nem nova prova de segurança.
