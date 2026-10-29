# A262 — rotas reais de publicação e HARD NO-GO antes do webhook Render

**Apenas LAB · 0/6 P0 homologadas · HARD NO-GO · nenhum merge, Worker, deploy, contratação ou efeito externo.**

## Auditoria de caminhos reais

A revisão de `render.yaml`, dos workflows GitHub e do arquivo `.github/render-reconcile.trigger` identificou rotas diferentes — não devemos confundi-las:

| Caminho | Função real | Prova de autoridade independente? |
|---|---|---|
| `render.yaml` | Serviço Python usa checkout de `main`, instala `requirements.txt` e inicia Streamlit. `autoDeployTrigger: off` | **Não.** Render UI/manual, outros hooks e origem de artefato continuam fora do controle do código A260/A261 |
| `.github/workflows/render-deploy-control.yml` | Pode ser solicitado por `workflow_dispatch` ou por push `main` que altere `.github/render-reconcile.trigger`; chama `curl -X POST` com `RENDER_DEPLOY_HOOK_URL` | **Não na main atual.** A262 prepara um HARD STOP **somente na PR draft**, antes de ler o secret ou chamar o hook |
| `.github/workflows/production-browser-smoke.yml` e `production-build-identity.yml` | Observam saúde, interface e fingerprint **depois** da publicação | **Não**, não vetam deploy previamente |
| `.github/workflows/production-health.yml` | Verifica saúde e página do serviço | **Não**, observação não é autorização |
| `.github/workflows/atlasquant-source-backup.yml` | Gera ZIP de **backup da árvore fonte**, podendo conter `labs/` | **Não é artefato runtime** nem gate de deploy |
| `.github/workflows/atlasquant-release-readiness.yml` | Revisa condições de preparação, licenciamento e interface | **Não autoriza efeito real** |

O workflow GitHub de deploy tem permissões `actions: write`, usa secret do hook e poderia disparar publicação após execução manual ou alteração do gatilho. Teste de saúde HTTP 200, identidade de build ou botão de CI verde **não são precondições de autoridade P0**.

## Mudança de código restrita à PR A262

Acrescentamos um passo **incondicional** ao arquivo `.github/workflows/render-deploy-control.yml` no ramo experimental, imediatamente **depois** do checkout e **antes** de `Require Render deploy hook` e `Trigger Render deploy`:

```bash
set -euo pipefail
echo "::error::AION HARD NO-GO: 0/6 P0, Render hook forbidden."
exit 2
```

Não há `if`, `continue-on-error` nem entrada secreta. Enquanto esse passo estiver presente e preservado no fluxo, o job GitHub específico é bloqueado antes de qualquer POST. **O workflow não foi disparado**, pois poderia gerar efeitos reais; a CI exercita somente sua análise estática em PR.

A proteção **NÃO está na main e não controla a UI/API do Render nem outro webhook fora desse workflow**. Mesmo que viesse a ser integrada, bloquear uma rota GitHub é apenas uma camada; não autentica emissão de eventos, custódia de chaves, witness externa, SQL VFS ou recibos de provedor.

## Testes e auditoria A262

`labs/a262_publication_surface_hard_stop.py` faz inventário offline de oito arquivos do repositório e verifica, com parser YAML seguro, que o passo guardião é exato e precede a etapa de envio em **cada job que contenha POST ao hook**. Ele veta a conclusão de publicação **sempre**, inclusive quando encontra o bloqueio estrutural correto. A CLI devolve `exit 2` deliberadamente e não possui acesso a secret, provedor ou rede.

São 17 testes novos: rota manual e por gatilho, Render fonte não vinculado ao ZIP A260, remoção do guard, `exit 0`, `if: always()` no hook, `continue-on-error` no guard, segundo job sem guard, YAML duplicado/malicioso, Render autoDeploy ligado, falso preflight no build, distinção de monitoramento e backup, raiz ausente, CLI real código 2, 50 auditorias concorrentes e **XFAIL** demonstrando que Render ainda não exige A262.

CI Ubuntu e Windows executa A262 e regressões A261–A243, Outbox/Saga/Chaos. O resultado do verificador será apenas inventário e recusa, nunca aprovação de publicação.

**HARD NO-GO · 0/6 P0 · UNCERTAIN=ZERO_AUTO_RESEND.** Trader prioritário, Investimentos preparado, Negócios congelada. Nenhuma ativação.
