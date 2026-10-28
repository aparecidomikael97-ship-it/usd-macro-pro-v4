# AION A212 — prova causal assinada de efeito (somente sintética)

**28/10/2026 · DRAFT · HARD NO-GO · 0/6 P0 externas verificadas**

## Problema concreto a resolver (A207 ainda RED)

Os testes A207 demonstram que o ExecutionOutbox pode escrever CONFIRMED quando um adapter malicioso retorna confirmed=True e um effect_ref inventado, tanto no send como no reconcile. Não existe efeito real nesses testes. A209–A211 propuseram raiz, rotação e testemunhas, mas ainda não autenticaram um efeito no sistema de destino.

O A212 aumenta a rigorosidade do laboratório: valida **assinaturas Ed25519 reais sobre mensagens sintéticas** e detecta alterações de campos que ligam a alegação à operação original. Isso é uma prova matemática de assinatura de *bytes*, **não** uma prova de que o efeito aconteceu; nenhuma transição Outbox foi alterada.

## Contrato sintético V0

Arquivo: labs/a212_synthetic_signed_effect_preflight.py

Assinam-se, sob o domínio textual fixo ATLASQUANT-AION/A212/SYNTHETIC-EFFECT-STATEMENT/V0, os campos:

- Escopo: owner_id, tenant_id, workspace_id e operation_kind;
- Intenção: intent_digest, idempotency_key, subject_digest e receipt_nonce_hex;
- Destino alegado: provider_id, provider_event_id, effect_ref e effect_state;
- Cronologia: occurred_at e witness_sequence;
- Testemunho alegado: witness_root_id e witness_checkpoint_hash;
- Identificação do schema sintético.

O campo signature_b64 é externo à mensagem assinada; a serialização é JSON UTF-8 com chaves ordenadas e separadores definidos. Essa convenção **não implementa RFC 8785 nem HTTP Message Signatures (RFC 9421)**. É um envelope de laboratório específico.

Exigir correspondência exata de todos os campos originários da intenção já conhecida pelo chamador. Rejeitar assinatura inválida, token alterado, chave errada, evento repetido, nonce repetido, relógio impossível e sequência não crescente em relação à âncora apresentada. O comparador A211 continua responsável apenas por simular divergências de checkpoints. A212 NÃO prova que a âncora apresentada seja externa.

A função decode_strict_json_receipt recusa chaves duplicadas, JSON não finito e payload excessivo para não transformar parses ambíguos em aprovação.

## Ponto essencial: assinatura válida não significa efeito verdadeiro

- Os testes A212 geram chaves Ed25519 efêmeras **apenas em memória**, no processo de teste. Não existe chave externa, comercial, do proprietário ou de provedor. Nenhuma chave privada é gravada no repositório.
- A chave pública que o verificador recebe é apresentada pelo próprio chamador. Sem origem externa pinada e independente, o invasor pode assinar uma *mentira* com sua própria chave e fornecer a chave correspondente.
- Uma assinatura matemática válida sobre EFFECT_CONFIRMED apenas autentica a afirmação de quem possui a chave; **não demonstra causalidade de execução real**.
- A sequência e os históricos de eventos/nonces chegam como argumentos do chamador, e podem ser revertidos por um host comprometido.
- O campo de operação e o idempotency_key não são uma consulta ao provedor de destino. Até haver leitura independente do estado real, manter UNCERTAIN e ZERO_AUTO_RESEND.
- Mesmo um payload bem formado, assinado e matematicamente válido retorna **may_confirm=False** invariavelmente. O resultado matematically_valid_signature=True significa somente Ed25519 aceitou os bytes da mensagem sob a chave **candidata**.

## Adversários sintéticos cobertos

Testes: labs/test_a212_synthetic_signed_effect_preflight.py (39 casos)

1. Validar Ed25519 real; não elevar decisão.
2. Assinar efeito falso com chave de teste: ainda não autoriza CONFIRMED.
3. Trocar efeito/evento depois da assinatura: falha matemática.
4. Reassinar intenção, idempotência, nonce, owner, tenant, workspace, provider, tipo de operação, subject, raiz ou checkpoint diferentes: falha de correspondência mesmo com criptografia válida.
5. Repetir provider_event_id, nonce ou sequência: bloqueio.
6. Assinar evento fora da janela de autorização.
7. Trocar algoritmo implícito ou domínio de assinatura: falha matemática.
8. Recusar campo host-inventado independently_verified, JSON duplicado e valores de tipo ambíguo.
9. Caso com gap de sequência artificial: pode verificar matematicamente, mas NÃO comprova o trecho ausente nem autoriza.
10. Verificar imutabilidade do resultado.

CI A212 roda testes A212 mais A211/A210/A209/A208/A206 no Ubuntu e Windows. Bibliotecas de teste: cryptography==44.0.3 e requests==2.34.2. Não inclui A207 RED como verde ou corrigido.

## Caminho para transformar hipótese em evidência externa — FUTURO, NÃO A212

1. Identificar o efeito real de cada tipo de operação (evento do sistema de destino, ID e estado definitivo), não apenas uma resposta HTTP positiva.
2. Definir fonte de verificação independente de adapter.send/reconcile e guardiã externa das chaves do emissor. Atentar a identidade do domínio e rotação de chaves.
3. Estabelecer uma autoridade HUMAN_OWNER externa ao host para intenção e acesso; não aceitar uma chave do payload como raiz de confiança.
4. Obter receipt autêntico com antirollback independente (A211) e provar vínculo causal com a mesma intenção, idempotência e nonce.
5. Executar testes ponta a ponta contra A207: adapter falsifica CONFIRMED, provedor não vê efeito; nenhum ledger CONFIRMED. Validar os dois caminhos SEND e RECONCILE.
6. Revisar formalmente autorização, custos, privacidade e riscos antes de qualquer conexão ou alteração operacional.

Este A212 NÃO executou etapas 1–6 contra serviços reais.

## Referências primárias verificadas

- RFC 8032 (Ed25519): https://www.rfc-editor.org/rfc/rfc8032.html
- PyCA cryptography (Ed25519 verify lança InvalidSignature se falhar): https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
- RFC 9421 (requisitos gerais de chaves confiáveis e componentes vinculados em assinaturas HTTP): https://www.rfc-editor.org/rfc/rfc9421.html

São referências de engenharia; o envelope A212 NÃO afirma conformidade com RFC 9421.

## Estado de segurança e mudanças proibidas

**0/6 P0 externas. HARD NO-GO. A207 RED sem correção.** O código permanece isolado em labs; não muda ExecutionOutbox, Worker, roteamento, flags, acesso, serviços externos, produção nem Negócios. Sem envio, deploy, merge, uso de credenciais, criação de recursos Azure/AWS, custo ou consulta a provedores. UNCERTAIN=ZERO_AUTO_RESEND. O HUMAN_OWNER terá de autorizar separadamente qualquer etapa externa futura.
