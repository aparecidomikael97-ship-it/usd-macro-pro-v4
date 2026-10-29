# A215 — Ponte de procedência sintética, somente leitura

**HARD NO-GO, 0/6 P0 externos homologados; UNCERTAIN=ZERO_AUTO_RESEND.**

## Objetivo

O A214 vincula um candidato de efeito ao registro real do Outbox SQLite, mas não verifica assinatura nem origem externa. O A212 prova somente a matemática de uma assinatura Ed25519, usando chaves **sintéticas** fornecidas pelo chamador, sem custódia externa.

O A215 junta esses dois contratos em um **laboratório de diagnóstico**:

1. Recupera o snapshot do Outbox do escopo real e exige o preflight A214 completo em SENT ou UNCERTAIN.
2. Confronta os campos comuns do candidato e da declaração assinada: identificador do provedor, evento, efeito, resultado, checkpoint, sequência e horário. Se houver discrepância, nega antes da verificação de assinatura.
3. Deriva valores esperados da operação local (owner, tenant, workspace, action, idempotency_key e digest de desafio A214) e da alegação host-controlled (root e digest do suposto recibo).
4. Executa o contrato de assinatura **sintética** A212 com chave pública fornecida no laboratório. Pode retornar signature_math_valid=True somente se os bytes da assinatura conferirem e os campos declarados corresponderem.
5. Em **todos** os casos retorna independent_origin_verified=False e may_confirm=False.

O resultado positivo LOCAL_AND_SIGNATURE_MATH_MATCH_BUT_ORIGIN_AND_EFFECT_UNPROVEN significa apenas que **duas representações host-controlled concordam e a matemática da assinatura bate com uma chave host-supplied**.

## Ameaças analisadas

- Substituição do provedor, evento, effect_ref, payload/autorizações do Outbox, timestamp ou tentativa.
- Alteração do checkpoint, raiz declarada, sequência de testemunha, nonce e vínculo com o payload.
- Recibo com JSON duplicado ou campos extras alegando verificação externa.
- Public key trocada, assinatura inválida, replay declarado e checkpoint antigo.
- Assinatura real sob chave gerada no próprio host: **matematicamente válida, mas sem independência**.
- Par de histórico de eventos e nonce informado por host comprometido: **não prova armazenamento externo durável**.
- Repetição da mesma declaração assinada sem escritura em SQLite e sem reenvio.

## Limites explícitos

- Arquivos A215 ficam **somente no diretório labs/**. Nenhuma importação ou caminho novo de produção, hook de CONFIRMED, rede, endpoint, deploy ou confirmação foi adicionado ao Outbox.
- Não cria/guarda chaves no código do laboratório; só os testes geram chaves efêmeras em memória.
- Não existe raiz confiável adquirida fora do host, autoridade independente de provedor, assinatura oficial, log verificado com prova de inclusão/consistência, testemunhas separadas ou antirollback durável.
- Os digests do A214 são compromissos locais e a assinatura A212 tem wire format próprio. **Nenhum deles implementa RFC 8785, RFC 9421 ou RFC 9162.**
- Um resultado math-OK nunca constitui decisão de permissão. Testes positivos simulam um adversário capaz de gerar sua própria chave e falso recibo.

## Testes e CI

- labs/test_a215_synthetic_origin_bridge.py: **35 testes adversariais** contra Outbox SQLite real e testes sintéticos de assinatura Ed25519.
- Executa também 30 testes A214, A213 e A207 originais e todas as regressões de Outbox/saga/caos e contratos A208–A212 em Ubuntu e Windows.
- Quality tests, Core Security Gate, Core Certification e Unified Core também devem permanecer aprovados no Draft.

Referências de desenho (não implementadas como conformidade):
- RFC 9162 Certificate Transparency 2.0, inclusão e consistência: https://www.rfc-editor.org/rfc/rfc9162.html
- RFC 8785 JSON Canonicalization: https://www.rfc-editor.org/rfc/rfc8785.html
- NIST SP 800-57 Parte 1, gestão e origem de chaves: https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final

**Decisão:** A215 oferece somente uma ponte de diagnóstico estrutural e assinatura sintética. **HARD NO-GO, 0/6 P0 independentes, nenhum autoenvio, nenhuma confirmação.**
