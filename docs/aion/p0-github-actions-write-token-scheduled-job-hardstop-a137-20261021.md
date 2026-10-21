# AION P0 A137 — Inventário dos workflows e hard-stop LAB de credenciais de escrita

**Data: 21/10/2026. Escopo: branch Draft empilhada sobre PR #1420. NÃO é uma configuração aplicada à main.**

## Achado reproduzido

Na main, `.github/workflows/autopilot-v107.yml` e `.github/workflows/coleta_automatica.yml` têm trigger schedule, `permissions: contents: write` e expõem o token github.token ao fluxo Python. No Autopilot também existe um step Global Worker tick condicionado a variável do repositório; esta condição não é evidência de ativação, e o kernel do Worker possui travas anteriores.

Autopilot roda o script `autopilot_setup_audit_v114.py`; Coleta roda `coleta_automatica_v86.py`. Ambos podem acessar dados de runtime e dependem de credenciais. Isso é uma capacidade de escrita presente no desenho do workflow, não demonstra PUT indevido, execução de Worker nem cron efetivamente habilitado ou processado.

Os jobs de `aion-runtime-checkpoint-bootstrap.yml` e `aion-runtime-checkpoint-migrate.yml` contêm comandos `gh api --method PUT` para `dados/aion/checkpoint_master.json` e declaram contents: write, mas já estão negados por `if: ${{ false }}`. A137 não os desbloqueia nem altera os scripts.

## RED-first

Em CI com rede do produto não utilizada, antes de tocar nos dois jobs agendados, os 13 testes A137 tiveram **3 FAIL / 10 PASS** (Unix), correspondentes a Autopilot, Coleta e regra agregada dos quatro jobs. Referência: https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39685182994 . Isso verifica postura textual do YAML, não reproduz escrita real de checkpoint.

## Mitigação candidata, somente Draft/LAB

Em `autopilot-v107.yml` e `coleta_automatica.yml`, o job principal agora contém `if: ${{ false }}`; `permissions.contents` foi reduzido de write para read. Assim, nessa versão candidata, não executam scripts, não usam chaves de dados e não invocam o Global Worker pelo job. Os workflows e suas agendas permanecem no código, mas os jobs são pulados.

Essas duas mudanças são duas barreiras defensivas independentes; **desativariam também a coleta legítima e a atualização de mercado** se integradas à main. Como isso impacta produto, NÃO devem sofrer merge, deploy ou aprovação presumida sem plano de continuidade, operação read-only e decisão explícita do proprietário.

Workflow do teste A137: read-only GitHub Actions Ubuntu/Windows, sem segredos, com checkout persist-credentials:false; testes de texto sintético e varredura estática de todos os workflows. Verifica quatro jobs críticos e a ausência de poder write nos dois jobs agendados. Tem limites: analisador textual não é parser YAML completo, não resolve actions externas, scripts em outras linguagens, tokens PAT, configurações IAM/regras do repositório, eventos GitHub ou permissões efetivas.

A conexão de leitura atual não permitiu consultar a API administrativa de configuração default do GITHUB_TOKEN. **NÃO** foi auditada essa configuração por este pacote. Não é prova de chaves externas matriculadas nem de alta disponibilidade.

## Próximos gates antes de restaurar operação normal

1. Definir serviço/witness externo realmente independente com custódia, política de chaves, revogação, sequência monotônica, READ fresco e CAS verificável.
2. Separar credenciais do coletor de mercado dos direitos de gravar `dados/aion/checkpoint_master.json`, preferencialmente com políticas independentes fora do mesmo token amplo.
3. Desenhar continuidade segura de dados de mercado (read-only, cache e efeitos/custos) antes de considerar desligamento em produção.
4. Validar com administrador do GitHub as políticas reais de token, proteção de branch, permissões das GitHub Apps/Actions, workflows antigos e execução histórica; YAML sozinho não prova o estado vivo.
5. Reexecutar critérios P0, H0, Quality/Security e receber autorização explícita para qualquer ação real.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND · nenhum merge, deploy, restore ou gasto.**