# AION Core — Checkpoint Mestre de Robustez e Expansão

Data: 2026-09-28
Status: oficial para continuidade do projeto
Branch de registro: `cursor/aion-core-master-checkpoint-2026-09-28`

## Ordem obrigatória

1. Fortalecer e fechar o Núcleo AION com foco em confiabilidade, segurança, governança, execução controlada, resiliência e verificabilidade.
2. Depois incorporar ao Núcleo, sem perder escopo, todas as capacidades já aprovadas para o AION.
3. Só então ampliar autonomia e escala.

Princípio: **núcleo confiável primeiro → autonomia depois → escala por último**.

## Arquitetura central já aprovada

- AION como produto/sistema independente e maestro do ecossistema.
- Central AION como ponto de entrada após login.
- Trader, Investimentos e Negócios como workspaces/módulos opcionais conectados por registry/entitlements, sem o Core depender deles.
- Router/orquestrador por capacidade, contexto, risco, custo e permissão.
- Task OS: objetivo → plano → execução permitida → verificação → entrega.
- Specialists/skills por domínio.
- Guardian/Policy Engine acima de skills e integrações.
- níveis de autonomia graduais: leitura; sugestão; execução após aprovação; automático apenas em tarefas de baixo risco.
- arquitetura multi-modelo e roteamento por qualidade, custo, privacidade e disponibilidade.
- AION Connect para integrações autorizadas, com menor privilégio, escopos, auditoria e revogação.
- Bancos e aplicativos governamentais permanecem fora do escopo.

## Memória, conhecimento e verdade

- Separar `user_memory`, `workspace_memory` e `knowledge_library`.
- Memória persistente governada, versionada, com procedência, validade e histórico.
- Knowledge Vault/Biblioteca para livros, manuais, pesquisas e documentos autorizados.
- Knowledge Graph/Evidence Graph para relacionar conceitos, fontes, conflitos e contexto.
- Livros e documentos não são tratados como verdade cega.
- Distinguir fato bem suportado, opinião do autor, hipótese, conflito, informação desatualizada e desconhecido.
- Para temas dinâmicos, verificar fontes atuais antes de afirmar.
- Memory Quarantine: novo conteúdo não entra automaticamente na memória permanente; deve passar por origem, integridade, validade, conflito e política de promoção.
- Detecção de contradição sem sobrescrita silenciosa.
- Confiança deve ser explícita e calibrada contra desempenho real.

## Robustez, segurança e resiliência aprovadas

- Capability Registry.
- Modo Conselho para tarefas complexas.
- Sandbox Universal.
- AION Evaluator / Evaluation Lab.
- Skill Marketplace interno com certificação.
- Proveniência Total.
- Painel de Observabilidade / Mission Control.
- Modo Privado/Local.
- Self-Healing / Auto Recovery.
- Versionamento e rollback.
- Red Team contínuo.
- Truth/Consistency Engine.
- Temporal Intelligence.
- Secrets Vault.
- Fila de trabalho persistente.
- Digital Twin.
- Benchmark próprio do AION.
- Reputação interna de especialistas baseada em desempenho.
- Modo de contingência/degradação segura.
- AION Constitution executável.

## Arquitetura de três camadas para tarefas críticas

- **AION Prime**: executor/orquestrador principal.
- **AION Shadow**: simula, testa, contesta e tenta quebrar a solução.
- **AION Sentinel**: árbitro independente para evidência, permissão, segurança e liberação.
- Tarefa simples: Prime.
- Tarefa importante: Prime + Shadow.
- Tarefa crítica: Prime + Shadow + Sentinel.
- Divergência relevante deve bloquear ou escalar para aprovação humana.
- Quando possível, revisores críticos usam modelos/fontes independentes para reduzir erro correlacionado.
- Protocol Firewall entre agentes: mensagens críticas devem usar contratos estruturados, nunca texto livre como autoridade.

## Itens adicionais do pente-fino para elevar maturidade do Núcleo

- AION Identity & Zero Trust para agentes, skills e conectores.
- Context Firewall + proteção contra prompt injection em web, e-mail, arquivos, livros e respostas de ferramenta.
- Action Receipt + Flight Recorder com rastreabilidade operacional suficiente e proteção de integridade.
- Blast-Radius Engine para graduar revisão conforme impacto potencial.
- Budget & Loop Governor para limitar passos, tentativas, tempo, custo e chamadas externas.
- Supply-chain security: dependências, análise estática, SBOM, pinagem, secret scanning e proveniência de build.
- Proteção efetiva da `main` com branch protection/ruleset e status checks obrigatórios.
- CODEOWNERS/revisão obrigatória para áreas críticas, quando aplicável.
- Dependabot e CodeQL ou equivalentes, quando compatíveis com o projeto.
- Testes arquiteturais garantindo que o Core funciona com zero módulos AtlasQuant e não importa domínio diretamente.
- Redução de megamódulos e contratos de dependência mais rígidos.
- Chaos Engineering e testes de recuperação.
- RPO/RTO e exercícios reais de restauração.
- Model Registry com benchmark e rollout canário antes de promover novo modelo.
- Data Governance para multi-tenant/comercialização: classificação, retenção, exportação, exclusão, consentimento e isolamento.
- Human Control Center com explicação clara de ação, custo, risco, dados usados, alcance, rollback e motivo da aprovação.

## AION Dev Studio

Objetivo: engenheiro de software completo, não apenas gerador de código.

Fluxo: requisito → arquitetura/dependências → análise de impacto → plano → branch isolada → implementação → testes → lint/segurança/regressão → revisão adversarial → documentação → PR → CI → correção → release review.

Papéis internos: Arquiteto, Implementador, Tester, Security Reviewer e Release Manager.

Regras: um agente produz e outro revisa; rollback/migrações seguras; proveniência; qualidade; performance quando aplicável; sem merge/deploy automático em ações sensíveis sem política/aprovação.

## AION Creative Studio

Objetivo: agência criativa completa.

- Brand Bible por projeto/marca.
- roteiro, storyboard, imagens, cenas, voz, narração, legendas, edição, thumbnails/capas.
- consistência de personagem/avatar/identidade.
- adaptações para YouTube, Shorts, Reels, TikTok e Kwai.
- QA multimodal antes da entrega.
- variações A/B e análise de métricas.
- procedência, direitos, licenças e consentimento quando necessário.

Conteúdo curto para monetização legítima deve incluir pesquisa de tendências permitidas, criação ponta a ponta, calendário, testes A/B e análise de retenção, compartilhamento, clique e conversão. Não prometer viralização nem renda garantida. Publicação automática e gastos exigem integração/permissão e política de aprovação.

## Marketing & Ads Studio

- pesquisa de produto, público, concorrentes e posicionamento.
- criação de copy, imagem, vídeo e campanha.
- variações por canal.
- análise de métricas e otimização.
- possível frente comercial para prestar serviço a empresas.
- nenhum gasto de mídia ou publicação paga sem autorização/política adequada.

## Catálogo de capacidades de trabalho a incorporar

O AION deve ser projetado para executar tarefas digitais de forma modular, não para prometer substituir qualquer profissão inteira. Prioridades de skills:

- Administração e secretaria.
- RH operacional e apoio a processos.
- Atendimento por chat, mensagem e voz/telefone quando houver integração autorizada.
- Documentos e planilhas.
- Pesquisa e verificação.
- Desenvolvimento de software.
- Marketing, vendas e CRM.
- Conteúdo, imagem, vídeo e mídia social.
- Análise de dados.
- Negócios/e-commerce/afiliados/dropshipping dentro das regras do projeto.
- Trader e Investimentos como especialistas/workspaces do ecossistema.

Regra geral: se o AION não souber ou a informação puder estar desatualizada, deve pesquisar/verificar antes de afirmar, sem inventar.

## Guardrails permanentes

- Nunca confundir faturamento com lucro.
- Trading real permanece bloqueado enquanto o modo autorizado específico não existir.
- Ações financeiras permanecem análise/recomendação conforme regras do sistema; nada de movimentar dinheiro por conta própria.
- Não agir fora de permissão.
- Não misturar tenants/workspaces.
- Não esconder incerteza.
- Não inventar capacidade.
- Preservar evidência e rastreabilidade de decisões importantes.
- Conteúdo externo nunca pode alterar Constituição/Guardian/políticas por instrução própria.

## Estado do pente-fino em 28/09/2026

Já existe fundação real no repositório para Router, Capability Registry, Truth/Freshness, memória em camadas, Guardian, resiliência, observabilidade, Digital Twin, Evaluation Lab, tenant isolation, Dev workflow e vários gates de segurança/testes.

Lacunas concretas identificadas nesta auditoria:

- `main` sem proteção efetiva de branch/status checks obrigatórios reportada pelo GitHub no momento da auditoria.
- Core ainda planeja/valida mais do que executa universalmente, por desenho.
- integrações externas, publicação, cobrança, merge/deploy e outras ações sensíveis continuam travadas por desenho e precisam de execução controlada, não liberação indiscriminada.
- ausência observada na árvore atual de CODEOWNERS, configuração Dependabot e CodeQL.
- arquivos muito grandes/megammódulos aumentam risco de manutenção e regressão e devem ser modularizados progressivamente.

Meta de engenharia: perseguir maturidade do Núcleo em faixa 95+ por evidência, testes, segurança e recuperação. Não usar "95/99%" como promessa universal de acerto da IA.

## Sequência de execução travada

1. Concluir pente-fino do Núcleo e transformar achados em backlog priorizado.
2. Fechar proteção da cadeia de mudança: branch/rulesets/checks/supply chain.
3. Consolidar Prime + Shadow + Sentinel e gates adaptativos por risco.
4. Fechar memória/conhecimento governados, quarantine e evidência.
5. Fechar execução controlada, identidade/Zero Trust, prompt-injection defense, receipts, blast radius e budgets.
6. Endurecer avaliações, calibração, chaos/recovery e model registry.
7. Garantir independência do AION Core em relação aos módulos AtlasQuant.
8. Incorporar todos os pilares aprovados: Dev Studio, Creative Studio, Marketing/Ads e catálogo de skills operacionais.
9. Só depois ampliar autonomia e escala/comercialização.

Nada desta lista deve ser descartado silenciosamente. Alterações de escopo devem ser explícitas e registradas.