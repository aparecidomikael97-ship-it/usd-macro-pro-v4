# A217 — Contrato declarado de raiz fora do host (não ativa confiança)

**HARD NO-GO: 0/6 P0 externos homologados; UNCERTAIN=ZERO_AUTO_RESEND.**

## Motivo

A216 chegou até duas assinaturas matematicamente válidas, mas ambas as chaves podiam ser produzidas pelo mesmo host. Para uma raiz de confiança externa, faltam aquisição autenticada fora da máquina, cadeia de custódia comprovável, testemunhas independentes e proteção contra replay/rollback fora do host.

Este LAB **não finge possuir essas provas**. Ele apenas checa se declarações de uma suposta cerimônia apresentam os campos e vínculos necessários para uma revisão humana futura.

## Proposta de contrato

Arquivo labs/a217_outofhost_anchor_claims.py:

1. Exige A216 integralmente válido no laboratório: recibo sintético, certificado de chave sintético, challenge A214, fingerprints e sequências locais.
2. Recebe três envelopes **não confiáveis**: reivindicação de aquisição manual fora do host, observador A e observador B.
3. Exige ID de cerimônia, referência de revisão do dono, identidade/organização do coletor, formato de SHA-256 do artefato, nonce e horário de coleta.
4. Exige dois observadores e organizações/canais declarados distintos, também diferentes do coletor, vinculados à mesma cerimônia, raiz provisória e challenge.
5. Rejeita trocas de tenant/owner/workspace, raiz, provedor, digest da intenção, nonce, observação fora da janela, histórico declarado repetido, campos extras de 'verified' e JSON ambíguo.
6. Mesmo para três organizações sintéticas aparentemente distintas: claimed_separation_coherent=True, mas **independent_origin_verified=False, may_activate=False e may_confirm=False**.

## O que o laboratório NÃO consegue verificar

- Se o operador realmente esteve com um dispositivo isolado do host.
- Se os observadores pertencem a organizações distintas e não coludidas.
- Se os canais são realmente independentes e autenticados.
- Se a chave pública veio de hardware, HSM ou provedor legítimo.
- Se a referência de revisão corresponde ao consentimento humano real.
- Se as hashes são de artefatos externos autênticos, não gerados pelo próprio host.
- Se nonce/revogação/epoch estão ancorados em um registro fora da máquina.
- Se um efeito no provedor realmente ocorreu ou se uma prova de inclusão em log externo é válida.

Todos os documentos, IDs, times, hashes, pins e históricos são **argumentos manipuláveis pelo chamador**. Portanto, três declarações coerentes NÃO são prova de independência. O LAB usa JSON próprio; não afirma conformidade com RFC 5280/9162/8785/9421.

## Exigências reais para uma futura homologação P0

- Definir **qual instituição/pessoa/dispositivo** controla a raiz fora do host e obter aprovação operacional e escopo.
- Capturar material verificável por canal genuinamente separado, com assinatura e chave cuja autenticidade tenha sido estabelecida fora do processo requisitante.
- Estabelecer prova de inclusão e consistência de log imutável, quando pertinente, e ancoragem anticópia/antirollback sob controle independente.
- Demonstrar revogação, rotação, perda de confirmação, replay e fraude adversarial em ambiente de homologação isolado.
- Integrar verificações de identidade do provedor e efeito real sem quebrar as garantias de idempotência, lease CAS e zero auto-resend.
- Cada uma das **6 obrigações P0 externas** precisa de evidência independente e aceite auditável próprio; nenhuma está homologada por este contrato.

## Testes

labs/test_a217_outofhost_anchor_claims.py: 35 casos adversariais com Outbox SQLite real, chaves Ed25519 efêmeras, três organizações fabricadas, troca de raiz, identidade, canal, cerimônia, nonce e hora; assinatura A216 inválida, JSON ambíguo, replay e nenhuma escrita em ledger.

A CI A217 executa regressão completa A217–A202 e Outbox/saga/caos em Ubuntu/Windows, além de Security Gate, Certification, Unified Core e Quality.

Referências:
- NIST SP 800-57 Parte 1 Rev.5 (gestão de chaves): https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final
- RFC 5280 (cadeia PKI): https://www.rfc-editor.org/rfc/rfc5280.html
- RFC 9162 (logs e provas de consistência): https://www.rfc-editor.org/rfc/rfc9162.html

**Decisão A217: apenas requisitos de evidência. Nenhuma raiz aprovada; nenhuma autoridade operacional; HARD NO-GO.**
