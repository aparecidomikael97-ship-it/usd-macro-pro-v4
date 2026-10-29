# A264 — Plano administrativo verificável para proteger a branch main

**LAB / proposta, não aplicada. HARD NO-GO, 0/6 P0 homologadas, sem merge, deploy, Worker ou novos custos.**

## Fato observado — não há enforcement comprovado

- Em 29/10/2026, GitHub GET `/branches/main` retornou `protected=false`, sem checks obrigatórios; GET `/rulesets?includes_parents=true` retornou `[]`. A verificação detalhada `/branches/main/protection` devolveu **403** para esta integração. A263 registrou este resultado em um job LIVE vermelho intencionalmente.
- O projeto é um repositório público com a branch principal `main`. O GitHub documenta regras de repositórios públicos nos planos gratuitos; criar/alterar a regra requer papel de administrador ou permissão explícita de edição de regras. **Não há essa ação administrativa nesta conexão**.
- O arquivo `.github/CODEOWNERS` atual nomeia apenas `@aparecidomikael97-ship-it`. O autor **não deve** aprovar sua própria PR. Exigir uma revisão independente sem ter um segundo revisor autorizado tornará o merge impossível. **Isso é desejável durante HARD NO-GO, mas deve ser reconhecido explicitamente**; não tente burlar a regra para passar.
- O workflow `.github/workflows/quality-tests.yml` declara `name: Quality tests`, o job `test` e gatilho `pull_request` para `main`. A proposta usa o contexto de check **candidato** `test` associado ao GitHub Actions app ID `15368`. **A identificação exata do check e da origem deve ser conferida na interface administrativa durante a instalação**, não somente presumida pela análise estática.

## Arquivo proposto — não é uma regra instalada

`docs/lab/a264_main_ruleset_admin_proposal.json` é um **rascunho do payload da API GitHub** para revisão por administrador, com:
- `enforcement: active`, `target: branch`, `conditions.ref_name.include: ["refs/heads/main"]`, `bypass_actors: []`;
- proteção contra exclusão de branch (`deletion`) e force-push (`non_fast_forward`);
- `pull_request` com **uma aprovação obrigatória**, `require_code_owner_review=true`, `require_last_push_approval=true`, `dismiss_stale_reviews_on_push=true` e `required_review_thread_resolution=true`;
- `required_status_checks` exigindo o check `test` do GitHub Actions (app ID `15368`) e atualização para a última base (`strict_required_status_checks_policy=true`).

Não execute `POST /repos/.../rulesets` copiando esse JSON sem revisão de permissões, revisor independente e disponibilidade de check. Isso pode bloquear todo o desenvolvimento de `main`. A intenção, por enquanto, é manter a `main` congelada e validar o plano.

## Passos para o administrador quando houver autorização específica

1. Entre em **GitHub → repositório → Settings → Rules → Rulesets → New branch ruleset**. Exige permissão administrativa. Verifique se o repositório continua público e se a branch de destino é `main`.
2. Escolha somente a branch `main`, **nenhuma exceção de bypass**, bloqueio de exclusão e force-push, PR obrigatório, ao menos uma revisão independente, revisão Code Owners, descarte de aprovações após mudanças e aprovação do último autor diferente de quem fez o último push.
3. Em **Required status checks**, selecione o check de qualidade que aparece efetivamente na interface de uma PR direcionada à `main`. Compare o nome `test` com o job do `Quality tests` e fixe a origem no GitHub Actions, se disponível. Não invente um nome de status: checks não produzidos podem travar merges sem verificar código.
4. **Antes de ativar aprovação obrigatória**, confirme a existência de **pelo menos outro revisor humano confiável, diferente do autor**, com permissão de escrita. CODEOWNERS sozinho não fornece essa pessoa.
5. Faça a ativação com avaliação explícita de impacto e audite via leitura da branch e ruleset; registre ID, versão, alvo, regras ativas, bypass, check e resultado de uma PR de teste. Não desligue a regra para fazer um merge apressado.

Nenhuma etapa foi feita nesta A264. Não adicionamos colaboradores, não emitimos token de admin e não modificamos configurações GitHub.

## Verificação de LAB

`labs/a264_ruleset_blueprint_review.py` confere offline o conteúdo exato do rascunho, seu vínculo estático com `CODEOWNERS` e com `Quality tests`. Um resultado `proposal_structure_valid=true` significa só formato: **`admin_ruleset_applied_verified=false`, `independent_human_reviewer_confirmed=false`, `main_protection_applied_verified=false`, `permits_merge/deploy=false`**. A CLI retorna código **3** por desenho, não autoriza publicação.

Os testes adversariais rejeitam enfraquecimentos de escopo, bypass, aprovação zero, alteração de CODEOWNERS, stale reviews, check inventado, origem do check falsificada e campos host-controlled `trusted` ou `p0_homologated=6`.

## Limites que permanecem

- Regras de merge no GitHub **não substituem** custódia externa de chave, HUMAN_OWNER, identidade de evento, witness monotônica, FD/VFS/COMMIT SQLite ou recibos finais; **P0 0/6**.
- O bloqueio de webhook A262 está em PR draft, não na `main`. Configurar regras da `main` não impede, por si só, deploy via UI/API Render.
- A proposta pode exigir revisor que ainda não existe e checks que ainda não são estáveis. É intencional não ativá-la automaticamente.

**HARD NO-GO · UNCERTAIN=ZERO_AUTO_RESEND.** Prioridade Trader; Investimentos preparado; Negócios congelada; sem novos gastos.
