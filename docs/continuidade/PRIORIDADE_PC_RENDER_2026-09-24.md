# PRIORIDADE AO CHEGAR NO COMPUTADOR — Render / AtlasQuant — 2026-09-24

## Gatilho de retomada

Quando o administrador disser:

**"tô no computador"**

a prioridade número 1 é retomar imediatamente a reconciliação do Render, antes de voltar para novos blocos do AION ou do trading.

## Estado confirmado no momento deste checkpoint

- branch principal: `main`;
- último commit validado em `main` no momento do diagnóstico: `7652f68d904624b5d41dfd52ce8d95d72f31e9a4`;
- Quality Tests da main: verdes;
- Production Health: verde;
- site Render responde HTTP 200;
- Streamlit container aparece;
- Production Build Identity ainda falha;
- fingerprint esperado no último teste: `6041918796e2b9b6`;
- `seen_builds=[]`;
- isso indica que a produção continua em um bundle anterior ao marcador de identidade;
- workflow de redeploy existe;
- único bloqueio externo confirmado: secret `RENDER_DEPLOY_HOOK_URL` ausente.

## Passo manual que exige o computador do administrador

### Render

1. Abrir o serviço `atlasquant-private`.
2. Ir em Settings.
3. Localizar/criar o Deploy Hook.
4. Copiar a URL do Deploy Hook.

### GitHub

1. Abrir o repositório AtlasQuant.
2. Settings.
3. Secrets and variables.
4. Actions.
5. New repository secret.
6. Nome exato:
   `RENDER_DEPLOY_HOOK_URL`
7. Colar a URL.
8. Salvar.

### Regra de segurança

A URL do Deploy Hook é segredo.

**Não colar no chat, em documentação, em issue, commit ou log.**

O administrador deve responder apenas:

**"pronto"**

depois de salvar o secret.

## Execução após "pronto"

Usar o workflow:

`AtlasQuant - Render Deploy Control`

Esse fluxo deve:

1. validar que o secret existe;
2. disparar o Render;
3. esperar o endpoint de saúde;
4. disparar `Production Build Identity`;
5. disparar `Production Browser Smoke`.

## Critério para declarar produção reconciliada

Não basta HTTP 200.

A produção só pode ser chamada de atualizada/validada quando:

- Production Health estiver verde;
- Production Build Identity encontrar o fingerprint esperado da main;
- Production Browser Smoke estiver verde;
- desktop e mobile não apresentarem exceção crítica;
- ordens reais continuarem bloqueadas.

## Se o deploy ainda falhar

Não inventar sucesso.

Verificar, nesta ordem:

1. se o Deploy Hook aponta para o serviço correto;
2. se o serviço Render continua ligado à branch `main`;
3. se o Render recebeu o deploy;
4. logs de build/startup do Render;
5. se a produção expõe `#atlasquant-source-build-marker`;
6. se o fingerprint visto bate com a main atual.

## Depois da reconciliação

Somente depois da prova de produção voltar para:

- Central AION;
- voz contextual;
- Studio;
- Negócios;
- Promoções;
- inteligência externa opcional;
- novos refinamentos do sistema.

## Regra da verdade

Estado atual:

- **código novo em main: CONFIRMADO**
- **site online: CONFIRMADO**
- **bundle novo no Render: NÃO CONFIRMADO**
- **Deploy Hook no GitHub Secret: AUSENTE**
- **trading real: BLOQUEADO**
