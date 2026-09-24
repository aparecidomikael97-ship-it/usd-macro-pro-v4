# AtlasQuant — AION Provider + Voice + Build Proof — 2026-09-23

## Objetivo

Fechar o próximo bloco do AION sem ativar custos automaticamente:

1. deixar um adaptador de inteligência externa pronto, mas fail-closed;
2. manter Custo Zero como padrão;
3. exigir aprovação por solicitação paga;
4. adicionar voz contextual opcional em todas as áreas do AION;
5. provar automaticamente qual bundle de código chegou à produção depois de cada merge em `main`.

## Adaptador de inteligência externa

Criado `atlasquant_aion_provider.py`.

O adaptador suporta uma rota OpenAI Responses API, mas só chama o provedor quando TODOS os gates abaixo estão válidos:

- `AION_FF_EXTERNAL_LLM=true`;
- `AION_MODEL_PROVIDER=openai`;
- chave de API presente;
- modelo rápido configurado;
- modelo de raciocínio configurado;
- preço de entrada por milhão de tokens configurado;
- preço de saída por milhão de tokens configurado;
- orçamento mensal positivo e permitido pelo administrador;
- custo estimado da solicitação dentro do saldo;
- aprovação explícita daquela solicitação;
- conteúdo não classificado como sensível.

Se qualquer gate falhar, o AION usa a rota local e não envia a solicitação.

## Variáveis esperadas

A configuração externa usa:

- `AION_MODEL_PROVIDER`
- `OPENAI_API_KEY`
- `AION_OPENAI_FAST_MODEL`
- `AION_OPENAI_REASONING_MODEL`
- `AION_OPENAI_INPUT_USD_PER_MTOK`
- `AION_OPENAI_OUTPUT_USD_PER_MTOK`
- `AION_OPENAI_MAX_OUTPUT_TOKENS`
- `AION_OPENAI_TIMEOUT_SECONDS`

Nenhum valor secreto é exibido pelo painel.

## Regra de custo

O AtlasQuant não embute preço comercial como verdade permanente.

Os preços usados para preflight ficam em configuração administrativa, permitindo atualização sem alterar o código.

Sem preços configurados, a chamada paga é bloqueada.

O consumo é registrado como **estimativa técnica de custo**, nunca como prova de fatura do provedor.

## Regra da verdade

Resposta de modelo externo recebe:

`MODEL_OUTPUT_UNVERIFIED`

Isso significa:

- inteligência do modelo não vira fato confirmado automaticamente;
- as evidências canônicas continuam separadas;
- o modelo não pode afirmar que publicou, cobrou, fez merge, deploy ou executou operação;
- ações continuam dependentes de Guardian/integradores reais.

## Privacidade

O roteador mantém local solicitações com sinais de:

- senha;
- token;
- segredo;
- credencial;
- chave de API;
- CPF/CNPJ;
- cartão;
- conta bancária.

O prompt externo também passa por redaction de padrões comuns de segredo antes do envio.

## Central AION

A Central agora prevê dois modos:

### Local / custo zero

É o padrão.

### Inteligência externa

A opção só aparece utilizável quando o provedor está realmente `EXTERNAL_READY`.

Mesmo assim:

1. o custo máximo estimado aparece;
2. o administrador marca que quer usar a inteligência externa;
3. o administrador aprova aquela solicitação;
4. o roteador verifica novamente orçamento e privacidade;
5. só então o adaptador pode chamar o provedor.

## Voz contextual

Todas as áreas do AION receberam assistente de voz contextual opcional:

- Central;
- Secretaria;
- Trading;
- Studio;
- Negócios;
- Laboratório;
- Desenvolvimento;
- Promoções.

A voz:

- nunca toca automaticamente;
- informa o contexto da área;
- mantém texto disponível quando TTS não estiver configurado;
- avisa que gerar áudio pode consumir um provedor pago configurado.

## Build Proof de produção

Criado workflow:

`.github/workflows/production-build-identity.yml`

Ele roda após push em `main` e:

1. calcula o fingerprint exato do bundle esperado;
2. abre a produção com Chromium;
3. espera o deploy;
4. lê `#atlasquant-source-build-marker`;
5. compara o fingerprint da produção com o fingerprint do commit;
6. falha se a produção não corresponder;
7. salva relatório e screenshot como evidência.

Isso fecha a lacuna entre:

- “servidor está online” e
- “o código novo realmente chegou à produção”.

## O que permanece desligado

- feature flag de LLM externo por padrão;
- orçamento pago por padrão;
- publicação automática em redes sociais;
- marketplace real;
- pagamentos;
- promoções reais;
- auto-merge;
- deploy comandado pelo AION;
- trading real.

## Gate antes do merge

Este bloco só pode entrar na `main` com:

- Quality Tests verde;
- Release Readiness verde;
- UI Smoke verde;
- Mobile DOM verde;
- revisão do diff.

Depois do merge, o novo Production Build Identity deve provar o fingerprint exato em produção antes de chamar o deploy de validado.
