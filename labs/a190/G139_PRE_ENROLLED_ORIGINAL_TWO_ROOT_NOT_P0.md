# G139 — pré-cadastro original obrigatório, ANTES de qualquer recibo de custódia

**Draft empilhado sobre G138 #1630. 0/6 P0 homologadas, HARD NO-GO, UNCERTAIN/ZERO_AUTO_RESEND.**

## Brecha real isolada
Uma assinatura de primeira reserva pode ser matematicamente válida para uma identidade inventada naquele instante. O G139 acrescenta uma exigência separada: **o cadastro econômico original precisa ter sido assinado por uma autoridade de inscrição anterior, com raiz distinta da autoridade de custódia**, antes de criar o challenge G138.

## Contrato de laboratório
- O construtor exige registro original retido (event_id, original_sha256, owner_id, tenant_id, workspace_id), raiz Ed25519 de **pré-cadastro** com issuer, key_id, epoch, fingerprint, sequência anterior e uma segunda raiz Ed25519 **de custódia**, com issuer, epoch, fingerprint e floor. Não há chaves padrão, autorregistro ou `trust-on-first-use`.
- A prova de cadastro cobre `enrollment_id`, `enrollment_sequence`, `enrollment_epoch`, `issued_at`, o registro original exato e **o hash da raiz de custódia**. A assinatura tem domínio distinto `ATLASQUANT:G139:SYNTHETIC_PRE_ENROLLMENT_V1\x00`.
- A primeira tentativa de verificar o cadastro é **one-shot**, mesmo se o resultado for ausente/inválido. Cadastro posterior ou início da prova de custódia sem cadastro válido é recusado.
- Após cadastro, um challenge aleatório permite conferir o recibo G138 sob chave de custódia diferente, com identidade econômica idêntica, sequência maior que floor, validade/epoch/raiz e retorno explícito `permits_send=False`, `permits_retry=False`, `external_homologation=False`.
- Não há servidor real, provedor ou Worker neste experimento. Todas as chaves, dados e raízes usadas nos testes são **criadas e fornecidas pelo chamador**. Não existe um cadastro externo anterior verdadeiro.

## 18 casos executáveis
1. Cadastro sintético válido + prova de custódia distinta, sem SEND.
2. Nenhum cadastro: nenhum challenge, nenhum TOFU.
3. Cadastro ausente: tentativa consumida, sem autorreinscrição.
4. Assinatura de cadastro sob chave desconhecida: recusa.
5. Identidade original, owner, tenant, workspace ou digest alterados: recusa.
6. Issuer/key id errados ou enrollment_id inválido: recusa.
7. Pré-cadastro apontando para outra raiz de custódia: recusa.
8. Epoch, sequência antiga e booleano indevido: recusa.
9. Cadastro com tempo futuro, muito antigo ou sem timezone: recusa.
10. Prova de cadastro reapresentada na mesma sessão: recusa.
11. Mesma chave para enrollment e custody: recusa.
12. Raízes ausentes, alteradas ou floors inválidos: recusa.
13. Campos extras ou assinatura/base64 inválida: recusa.
14. Custódia com nonce, identidade, raiz, epoch ou assinatura inválida: recusa.
15. Floor de custódia intacto recusa sequência antiga.
16. ACK desconhecido/ausente consome a sessão, sem reenvio automático.
17. **RED:** o host troca ambas as raízes, inventa novo cadastro original e comprova matematicamente um primeiro evento falso — **não P0**.
18. **RED:** acesso administrativo ao SQLite forja ticket G137 e consegue staging local na Outbox SEM passar por G139 — **não SEND e não P0**.

## Limites e exigência de solução real
O G139 apenas deixa o contrato mais rígido. Uma implementação real exige provisionamento de confiança e autenticação do HUMAN_OWNER **fora do domínio de alteração do host**, raízes/epoca/floors retidos independentemente e custody owner/provedor com garantia antirollback. SQLite nativo READ/WRITE sobre mesmo inode continua aberto, assim como a vinculação à recepção real de provider e o bypass por acesso direto ao banco.

**Mesmo que os 18 testes e G125 fiquem verdes, G122 deve continuar cinco FAIL por sistema até existir prova externa genuína.** Nenhum merge/deploy/Worker/SEND real, dados de cliente, segredos externos ou custo adicional.
