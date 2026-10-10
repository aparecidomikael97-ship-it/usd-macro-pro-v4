# AION — revisão independente da consolidação + Drafts #1164–#1166

Data: 2026-10-10. **Estado: PARTIALLY_CLOSED / #1117 HARD NO-GO**.

## Fonte e preservação
- Novo worktree isolado, sem branch de trabalho e em detached HEAD `5a064ca4b0a6cdc28d62d5e1ccf9a1383a5a4473`, base da Draft #1156.
- Patch local incremental dos **17 arquivos staged** do Codex `codex/aion-consolidation-reconciliation-v2`, aplicado a esta nova cópia, sem modificar seu worktree, seus estágios, nem seus arquivos originais.
- Recebidos por fetch *somente leitura* os objetos da Draft #1166, HEAD `dd5d63a84edb0493964eb2cfacb5ed5be9446e70`.
- Aplicado nesta nova cópia apenas o delta de `e4f931444efb923eede08c416fadd7f6e02f4aa9` (#1162) até o HEAD #1166, incluindo inventário da #1164, truth model da #1165 e proteção de continuidade da #1166. Isso não reaplica o velho guard da #1161.
- A união inicial contém **30 caminhos afetados** (17 Codex + 14 posteriores com sobreposição em `autopilot_v107.py`); este relatório novo é o 31º caminho.
- A aplicação teve **zero conflitos de conteúdo**. Um aviso de whitespace no delta posterior foi corrigido no patch na nova cópia.
- Nenhuma modificação de Core V1 congelado, `main`, Render, Worker, serviço remoto, TPM, credenciais reais, fornecedores pagos ou equipamentos físicos.

## Ajuste de integração indispensável
- A suíte AST da #1164 tinha o teste `test_budget_retry_shape_detected_in_this_ancestry`, que esperava `budget_reported_conflict_retry_shape=true` na base da #1162.
- A consolidação **já inclui a correção da #1156**: 409 e 422 no `GitHubStore.save` provocam `BudgetUnavailable`, não `False` que reautorizaria a volta de `Budget._change`.
- O teste foi **corrigido exclusivamente nesta cópia** para exigir `budget_reported_conflict_retry_shape=false`; documentação AST ajustada. **Não** foi reduzida a exigência de recibo/readback, nem restabelecido o replay.

## Testes desta revisão (Windows local, offline)
- `python -B scripts/aion1155_closure_audit.py`: **341/341 PASS**, exit code 0.
- Inventário AST: **10/10 PASS**, exit 0.
- Modelo de verdade da persistência: **18/18 PASS**, exit 0.
- Testes antigos do journal: **7/7 PASS**, exit 0.
- Novos testes do journal: **10/10 PASS**, exit 0.
- **386 execuções de casos de teste aprovadas nos grupos listados**; não alegar que são 386 testes exclusivos ou independentes.
- CLI de inventário: exit 0, **12 sinks genéricos** inventariados; dois callsites Shadow/Flight sob guard; `budget_reported_conflict_retry_shape=false`.
- Cinco auditores estáticos herdados: write response, GET response, GET token/no redirect, write destination e paid egress: todos exit 0.
- `git diff --check` aplicado à cópia após correção do whitespace: sem achados.

## Interpretação dos resultados
- O bloqueio conservador Autopilot da #1162 continua impedindo execução de Shadow/Flight sem claim durável. A assinatura de função usada no código do Codex não fornece liberação automática.
- O journal de eventos passou a conservar o candidato de cobertura 24h sem apresentar falsa confirmação operacional `continuous_runtime_confirmed=true` ou `continuous_24h_confirmed=true`.
- O inventário e a referência de verdade são **ferramentas de auditoria**, não provas de persistência, admissão, autoridade ou durabilidade.
- **A linha reunida não executou CI remoto própria**, pois não houve commit/push/PR; os workflows verdes de #1166 são de outra árvore Git. Não extrapolar.
- Suites dependentes do aplicativo completo e pandas/Streamlit, isolamento real multiempresa, integração de UI e dispositivos físicos não foram certificados neste trabalho.

## Bloqueios HIGH restantes
1. Captures Shadow/Research ainda guardam quarentena por sessão em RAM, vulnerável a nova sessão/processo.
2. Escritas genéricas do Autopilot e stores chamados diretamente ainda não têm um protocolo completo de claim durável e CAS multiprocesso.
3. Falta testemunha independente protegida contra rollback, prova causal de saída e reconciliação validada; mera presença de ID, HTTP 201 ou readback mesmo conteúdo não bastam.
4. Identidade do tenant/workspace/actor/task autenticada não está integralmente integrada às fronteiras reais dos consumidores/stores.
5. Monitoração de erros e retorno de processo não equivalem a certificado de persistência.

**Nenhum bloqueio de #1117 pode ser retirado.** `PARTIALLY_CLOSED` é a única classificação sustentada.

## Próximo gate humano
Solicitar autorização específica, **se desejado**, para commit/push e **nova Draft PR** da consolidação (sem merge nem deploy). Antes disso, revisar o patch de 31 caminhos, executar CI Windows/Linux no HEAD exato publicado e reconciliar as branches Draft para evitar duplicidade.
