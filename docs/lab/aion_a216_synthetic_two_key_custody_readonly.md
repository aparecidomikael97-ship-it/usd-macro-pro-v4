# A216 — Custódia sintética de chaves em duas assinaturas (READ ONLY)

**HARD NO-GO. 0/6 P0 externos homologados. UNCERTAIN=ZERO_AUTO_RESEND.**

## O que foi feito

A215 validou duas propriedades isoladas: dados do Outbox A214 em relação ao candidato, e assinatura matemática sintética A212 de um efeito. Isso ainda não estabelece de onde veio a chave signatária.

A216 adiciona o laboratório labs/a216_synthetic_key_custody.py. Ele valida um **certificado de chave sintético assinado por outro par de chaves**, que também é fornecido pelo host:

1. Reusa o preflight A215 para confrontar intenção, operação, assinatura sintética do recibo, checkpoint e sequência.
2. Calcula SHA-256 sobre os bytes da chave pública que supostamente assinou o recibo e o confronta com o certificado.
3. Calcula SHA-256 da chave pública de um suposto emissor provisório e o vincula ao certificado e a um pin também fornecido pelo host.
4. Exige chaves distintas para a função de emissor e a função de assinatura do recibo.
5. Vincula owner/tenant/workspace, provedor, desafio A214 e fingerprint da raiz declarada ao certificado.
6. Valida formato estrito, serial, epoch, janela de validade de até 7 dias, sinalizador de revogação declarado, nonce e histórico declarados pelo chamador, e verifica a assinatura Ed25519 do certificado.
7. Mesmo com matemática correta nas **duas assinaturas**, retorna sempre independent_origin_verified=False, may_confirm=False e SYNTHETIC_TWO_SIGNATURES_VALID_PROVISIONAL_ISSUER_UNTRUSTED.

## Limites de confiança

O host pode criar **ambas** as chaves e **ambas** as assinaturas, além de definir fingerprint, pin, histórico de serial e epoch e relógios. Portanto:

- Um emissor provisório host-supplied NÃO é uma autoridade independente.
- Pin host-supplied NÃO é uma raiz confiável provisionada fora do host.
- Revogação declarada no certificado NÃO substitui consulta autoritativa de revogação.
- Histórico de chave e serial host-supplied NÃO é antirollback durável.
- Continuidade matemática NÃO prova efeito real do provedor, inclusão em log externo ou custódia por terceiro.
- O formato A216 é um objeto JSON próprio do laboratório. **Não é certificado X.509, cadeia RFC 5280, RFC 8785, RFC 9421 ou RFC 9162.**
- Nenhum caminho de produção, credencial, rede, Outbox CONFIRMED, SEND, reenvio, ação externa, ledger ou deploy foi ativado.

## Testes adversariais

**30 testes com SQLite real, dois pares Ed25519 efêmeros em memória e zero efeitos reais**: falsificação de chave/issuer, pin inconsistente, mesma chave em dois papéis, assinatura inválida, cross-scope, raiz, datas, revogação, epoch rollback/gap, serial replay, JSON duplicado, flag falsa de verificação externa, replay da declaração, imutabilidade do retorno, ausência de escritas e _confirm bloqueado.

A CI A216 executa os 30 testes novos e todos os 255 testes A215/A214 e Outbox/caos/saga e A202–A212 em Linux e Windows, além das outras suites de segurança e qualidade.

Referências de desenho; não há implementação de conformidade com seus protocolos:
- NIST SP 800-57 Parte 1 Rev. 5, gestão de chaves: https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final
- RFC 5280, caminhos de certificação PKI: https://www.rfc-editor.org/rfc/rfc5280.html
- RFC 9162, logs verificáveis e provas de inclusão/consistência: https://www.rfc-editor.org/rfc/rfc9162.html

**Decisão: laboratório apenas. HARD NO-GO, 0/6 P0, nenhuma autoridade ou reenvio automático.**
