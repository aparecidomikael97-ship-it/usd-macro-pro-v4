# AION Operational Readiness V1 — Draft isolada

Base imutável de referência: AION Core V1 Technical Closure Candidate #951,
`662eab4dc4f5bb009fa1ca89f87530df74d30ddf`.

## Autorização

Implementação autorizada pelo HUMAN_OWNER em 2026-10-06 exclusivamente em Draft
isolada, sem merge, deploy ou escrita no runtime.

## Objetivo

Fechar três gaps operacionais sem reabrir o Core V1:

1. Temporal Project Memory V2.
2. Controlled Execution Handoff V1.
3. Developer Physical Execution V1.

## Limites

Esta branch não autoriza merge, deploy, runtime oficial, assinatura da cerimônia
de Core Freeze, Worker activation, produção, finanças, trading real, alteração
de segredo/credencial ou autoelevação de permissão.

## Temporal Project Memory V2

Preserva evento, data, evidência, estado e relações recíprocas de supersessão.
Consulta por data/range/topic/domain/state/source retorna UNKNOWN quando a
evidência ainda não foi ingerida. Histórico não concede autoridade.

## Controlled Execution Handoff

O handoff usa diretamente o caminho criptográfico V2.13 já existente:
TrustRootRegistry + Ed25519 + PersistentNonceRegistry +
Trusted Authority Bridge.

Não existe callback genérico de "verificador confiável". A autoridade é
verificada uma única vez, o nonce é registrado de forma durável e o handoff
carrega somente a linhagem pública da verificação. Mesmo READY não executa.

## Physical Evidence Attestation

Medições físicas também não são confiáveis porque um chamador colocou
`verified=true`. A prova física recebe uma attestation Ed25519 separada,
ligada ao:

- handoff digest;
- input digest;
- physical evidence digest;
- probe principal/session;
- conjunto completo de provas;
- janela temporal;
- nonce durável;
- key id/version da trust root pública.

Replay, adulteração após assinatura, proof-set incompleto e trust root inválida
falham fechados. Chaves privadas de teste são efêmeras e nunca persistidas no
repositório.

## Developer Physical Execution

O pre-execution gate só chega a `READY_FOR_PHYSICAL_EXECUTOR` quando a
attestation verificada e a evidência bruta correspondem exatamente. Mesmo
assim:

- não roda comando;
- não aplica patch;
- não escreve no repositório;
- Core protegido e runtime de produção ficam read-only;
- rede continua default deny;
- merge/deploy continuam false;
- o adaptador físico deve revalidar imediatamente antes do uso;
- receipt começa em OUTCOME_UNKNOWN;
- retry automático continua proibido.

## Prova Windows real

CI pode testar a criptografia e o fail-closed com chaves efêmeras, mas não pode
afirmar isolamento físico do PC do HUMAN_OWNER. A medição real permanece para
o host Windows autorizado quando disponível.

## Definition of Done desta Draft

- testes focais verdes;
- Quality tests verdes;
- red-team de falsificação/tamper/replay;
- nenhum caminho de merge/deploy/runtime;
- #951 inalterado;
- prova física real não pode ser inferida de CI.
