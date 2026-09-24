# AtlasQuant — Prioridade ao chegar em casa — Render Deploy Hook — 2026-09-24

## Prioridade número 1

Quando o administrador disser **"tô no computador"**, retomar imediatamente daqui.

### Objetivo

Fazer o Render publicar a `main` validada e provar o bundle novo em produção.

### Estado confirmado antes desta tarefa

- `main`: `7652f68d904624b5d41dfd52ce8d95d72f31e9a4`
- Quality Tests da `main`: verde
- Production Health: verde
- Production Build Identity: ainda falhando
- O endpoint do Streamlit responde HTTP 200
- O container do AtlasQuant aparece
- O marcador de source build não aparece
- Resultado observado: `seen_builds=[]`
- Fingerprint esperado naquela validação: `6041918796e2b9b6`
- O workflow `Render Deploy Control` já existe
- Bloqueio confirmado: secret `RENDER_DEPLOY_HOOK_URL` ausente

## Único passo manual necessário no computador

### Render

1. Entrar no Render.
2. Abrir o serviço `atlasquant-private`.
3. Abrir **Settings**.
4. Localizar/criar o **Deploy Hook** do serviço.
5. Copiar a URL.

**Não enviar a URL no chat.**

### GitHub

1. Abrir o repositório AtlasQuant.
2. Ir em **Settings**.
3. Abrir **Secrets and variables → Actions**.
4. Criar **New repository secret**.
5. Nome exato:

`RENDER_DEPLOY_HOOK_URL`

6. Colar a URL do Deploy Hook como valor.
7. Salvar.
8. Avisar no chat apenas: **"pronto"**.

## O que o ChatGPT/AION executará depois do "pronto"

O workflow `AtlasQuant - Render Deploy Control` deverá:

1. confirmar que o secret existe;
2. enviar POST ao Deploy Hook;
3. aguardar o `/_stcore/health` responder 200;
4. respeitar a janela mínima de estabilização;
5. disparar **Production Browser Smoke**;
6. disparar **Production Build Identity**;
7. manter a validação pós-deploy separada do gate `checksPass`.

## Critério para marcar produção como confirmada

Somente considerar a nova versão publicada quando houver evidência de:

- serviço saudável;
- fingerprint exato do source bundle;
- Browser Smoke verde;
- ausência de regressão de autenticação/segurança;
- nenhuma ativação de trading real.

## O que NÃO fazer

- não compartilhar o Deploy Hook no chat;
- não gravar a URL em arquivo do repositório;
- não colocar a URL em variável pública;
- não chamar produção de atualizada apenas porque HTTP 200 está verde;
- não habilitar trading real;
- não habilitar cobrança, marketplace ou publicação automática como parte deste reparo.

## Depois que o deploy for confirmado

Retomar a prioridade do AION/Interface:

1. confirmar AION ADMIN em produção;
2. validar Central, Secretaria, Studio, Negócios, Laboratório, Desenvolvimento e Promoções;
3. validar voz contextual;
4. validar Checkpoint Mestre;
5. conferir contraste/mobile;
6. somente depois voltar a novos refinamentos operacionais/backtests.
