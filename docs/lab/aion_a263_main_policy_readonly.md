# A263 — Main branch desprotegida: observação GitHub e CI que falha de propósito

**HARD NO-GO operacional · P0 0/6 · sem merge, deploy, Worker, gastos ou mudança administrativa.**

## Evidências consultadas em 29/10/2026

Em consulta GET à API GitHub, para `aparecidomikael97-ship-it/usd-macro-pro-v4`:
- `GET /branches/main`: `protected=false`, `protection.enabled=false`, `required_status_checks.enforcement_level="off"`, listas `contexts=[]` e `checks=[]`. SHA observado da `main`: `5744b2b7b17c84331e6f27c569064993ff587782`.
- `GET /rulesets?includes_parents=true`: `[]` (nenhum ruleset retornado para o repositório nessa consulta).
- `GET /branches/main/protection` e seus checks: **HTTP 403, Resource not accessible by integration**. Portanto, a configuração administrativa detalhada de revisões, permissões de bypass e outros controles **não foi inspecionada**.
- `.github/CODEOWNERS` no repositório lista responsável pelos arquivos sensíveis, mas o próprio cabeçalho avisa que precisa de branch protection/rulesets para haver enforcement.
- `.github/workflows/quality-tests.yml` executa testes, mas a observação `contexts=[]` não demonstra que esses testes sejam exigidos antes de mesclar a `main`.
- `render.yaml` tem `autoDeployTrigger: off`; isso não equivale a controle de permissões do Render e nem substitui proteção da `main`.

**Interpretação:** há uma vulnerabilidade observável na governança da `main`. Mesmo que uma PR de LAB tenha 100% de testes aprovados, o GitHub não demonstrou requisito de revisão ou checks obrigatórios na `main`. Não afirmar que todos os usuários podem fazer push: permissões de colaboradores e credenciais são separadas, não auditadas.

## A263 — auditável sem direito de administrador

`labs/a263_main_policy_readonly.py` usa **apenas** GET `/branches/main` e `/rulesets?includes_parents=true`, sem modificar regra, branch, PR, workflow ou serviço. Um avaliador puro classifica respostas malformadas, ausência de proteção, checks não obrigatórios, ruleset inativo e ausência de dados detalhados de aprovação como lacunas. O resultado **sempre** contém `HARD_NO_GO_REPOSITORY_POLICY_NOT_HOMOLOGATED`, `p0_homologated=0`, `permits_merge/deploy/worker=False`, `release_approved=False`.

O comando abaixo imprime JSON e retorna exit code **3** deliberadamente. Mesmo uma coleção sintética com `protected=true` não gera autorização operacional:

```bash
python -B -m labs.a263_main_policy_readonly --live
```

A `.github/workflows/aion-a263-main-policy-readonly.yml` possui jobs separados:
1. **Unidade LAB Ubuntu/Windows:** a A263 e regressões A262–A259/Outbox, sem rede para os testes do módulo e sem deploy; deve passar.
2. **Observação GitHub ao vivo:** consulta somente endpoints públicos autorizados, com `contents: read`, e **FALHA intencionalmente** (`exit 3`) enquanto não houver sistema de aprovação real. Esse job RED é um bloqueio informativo, **não erro de infraestrutura nem autorização para alterar a main**.

CI RED nesse job é o comportamento correto para P0 em aberto. O bloqueio de webhook A262 está ainda apenas na PR em rascunho e **não protege a main**; A263 também não muda qualquer regra de branch.

## Configuração que deverá ser avaliada por administrador, em etapa separada

- Restrição de push direto à `main`, PRs obrigatórias, pelo menos uma revisão independente do autor com aprovação válida, CODEOWNERS efetivamente exigidos quando aplicável e proibição de bypass sem trilha auditável.
- Checks obrigatórios e executados **no SHA a mesclar**, incluindo Quality canônica e gate de segurança, com proteção para que o autor não possa substituir o resultado por um arquivo `verified=true`.
- Política de quem pode alterar workflows, `render-deploy-control.yml`, hooks e `render.yaml`, com segunda revisão e trilha de auditoria.
- Separação de credenciais do Render, controle de deploy por UI/API e redução de permissões do token GitHub; tudo exige inspeção administrativa que esta conexão não oferece.
- Mesmo depois de proteger `main`, **0/6 P0 permanecem abertas** até validação independente de identidade, witness, reserva, SQLite e recibos finais.

**A263 não tenta instalar branch protection, gastar, fazer deploy ou liberar Worker.** O proprietário pode autorizar análise administrativa mais tarde, separadamente. Trader prioritário, Investimentos preparado e Negócios congelada.
