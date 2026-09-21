# AtlasQuant — Contrato de deploy no Render

## Objetivo

Fixar no repositório a configuração esperada para a aplicação de produção e evitar que
`atlasquant-private.onrender.com` execute código de branch ou commit diferente da release
validada na `main`.

## Fonte oficial

- Repositório: `aparecidomikael97-ship-it/usd-macro-pro-v4`
- Branch de produção: `main`
- Aplicação: `usd_macro_pro_v4_cloud.py`
- Build: `pip install -r requirements.txt`
- Start: `streamlit run usd_macro_pro_v4_cloud.py --server.address 0.0.0.0 --server.port $PORT --server.headless true`
- Health check: `/_stcore/health`
- Auto deploy esperado: somente depois dos checks da branch passarem.

O arquivo `render.yaml` registra esse contrato para uso com Render Blueprint.

## Regra de segurança

A existência do `render.yaml` não prova que o serviço já está gerenciado por Blueprint.
Enquanto o Browser Smoke não enxergar o fingerprint do source bundle correspondente à
`main`, a produção deve permanecer classificada como **SOURCE_IDENTITY_UNVERIFIED**.

Não reduzir o Browser Smoke para transformar falta de identidade em sucesso.

## Ajuste externo necessário para o serviço existente

No dashboard do Render, o serviço `atlasquant-private` deve apontar para:

1. repo correto;
2. branch `main`;
3. Auto-Deploy = **After CI Checks Pass**;
4. root directory vazio/repositório raiz;
5. build/start commands iguais ao contrato acima;
6. health check `/_stcore/health`.

Depois de salvar, disparar um deploy da `main` atual e confirmar no Browser Smoke:

- HTTP 200;
- source build presente;
- fingerprint igual ao checkout da `main`;
- desktop e mobile renderizados;
- transição móvel Iniciante → Avançado → Decisão → Radar;
- zero `stException`;
- zero overflow horizontal material.

## Secrets

Secrets continuam fora do Git. Variáveis sensíveis devem permanecer no secret store do
Render. O Blueprint não deve conter API keys, passwords, tokens ou hashes de usuário.
