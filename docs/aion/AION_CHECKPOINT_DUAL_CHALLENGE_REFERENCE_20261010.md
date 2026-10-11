# AION — referência offline de desafio da testemunha em dois domínios

**Data:** 10/10/2026. **Escopo:** P0 [#1178](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1178). **Base:** Draft #1183 HEAD `0167e4acb08cee38bcde3b6cac933a9293c2aa6a`.

**Status:** PROTOCOLO MATEMÁTICO OFFLINE / NÃO INTEGRADO / `PARTIALLY_CLOSED / HARD NO-GO`.

## Por que este bloco era necessário

Os contratos anteriores (#1179 e referências V2 do witness) verificavam assinaturas e um piso de sequência, mas um HEAD assinado com poucos minutos de frescor e *sem* responder a um desafio exclusivo **poderia ser repetido dentro da janela de validade**. Cloudflare CAS e S3 Object Lock COMPLIANCE, isoladamente, não demonstram de qual versão atual o cliente recebeu a resposta. Não há no projeto um serviço real de matrícula de chaves/witness aprovado e conectado.

## Entrega

- `atlasquant_aion_checkpoint_dual_challenge_reference_v1.py`: `review_challenge_bound_dual_head` verifica matematicamente três assinaturas Ed25519 sob três chaves distintas, envelopes canônicos fechados, domínios de assinatura separados para source/coordinator/segunda âncora, nonce hex de 256 bits, scope de owner/tenant/workspace e repo/branch/path, epoch, sequência, SHA e relógio limitado. Não usa rede, não cria chaves, não abre GitHub/S3/Cloudflare nem acessa secrets.
- `test_atlasquant_aion_checkpoint_dual_challenge_reference_v1.py`: provas com três chaves efêmeras de teste; troca de empresa e recurso, desvio de config, resposta com nonce anterior, assinaturas forjadas, head de época/seq/SHA incompatíveis, relógio alterado, offline second domain e `UNKNOWN` como bloqueio — com saídas sempre sem dados, custo ou autoridade.
- `.github/workflows/aion-checkpoint-dual-challenge-reference-v1.yml`: Python 3.12, dependência criptográfica fixada, testes offline em Windows e Linux, sem secrets, com `contents:read`.

### Limite crítico: *matching signatures* NÃO implica autoridade real

As chaves, o floor e o nonce são passados pelo chamador/teste, sem um canal de confiança. Um atacante capaz de fabricar os três keypairs também consegue criar envelopes válidos. **Inclusão do nonce bloqueia replay apenas quando** ele é gerado por CSPRNG confiável, nunca reutilizado, associado a uma chamada autenticada e validado contra a resposta do serviço correto. Reusar um nonce já utilizado com seu antigo transcript ainda pode passar matemática dentro da janela de frescor — o contraexemplo é testado.

Uma segunda assinatura emitida por um componente controlado pelo mesmo administrador **não** é testemunha independente. O segundo servidor precisa comprovar que recuperou o head **mais recente** do domínio resistente a rollback, não apenas assinar a cópia que o chamador entregou. Mesmo dois serviços de contas separadas podem ser controlados pela mesma pessoa/credencial e não provar independência.

**A função de referência NÃO aceita ou retorna checkpoint bruto**; sua saída positiva é exclusivamente `REFERENCE_MATCH_UNTRUSTED` com `worker_authorized=false`, `source_trust_production_verified=false`, `freshness_independently_verified=false`, `latest_head_independently_verified=false`, `automatic_retry_allowed=false`, `deployment_authorized=false`. Não estabelecer integração com o gate real a partir de dados autodeclarados.

## Matrícula/custódia real, ainda não executada

1. Aprovação do HUMAN_OWNER sobre operador da matrícula da chave pública da fonte, operador/credenciais do coordenador e do segundo domínio; custódia separada, onboarding, rotação, revogação, recuperação e custo.
2. Fonte confiável de owner/tenant/workspace → recurso exato, fora do checkpoint, sessão ADMIN e repositório GitHub. Chaves públicas verificadas por canal/out-of-band; pins recebidos do chamador não contam.
3. Leitura challenge-response autenticada e atual de ambos os serviços: nonce CSPRNG novo, scope, epoch floor protegido em domínio independente e `latest sequence + SHA` obtidos **pelos próprios servidores** com consistência contratada; não aceitar um head autoenviado.
4. Antirollback também após crash/fork: heads divergentes ou atraso na publicação DO/S3 = `UNKNOWN_OUTCOME`/quarentena, sem retry automático, com reconciliação segura.
5. Só depois das provas externas reais: testes Win/Linux/Windows físico, avaliação LGPD, cotação até teto de R$200/mês e **autorizações explícitas distintas** para enrollment, eventual gasto, merge, deploy e ativação de Worker.

**Core V1 congelado, runtime Worker bloqueado pela Draft #1180, readiness bloqueada pelas #1181/#1182.** Nenhuma operação real autorizada.
