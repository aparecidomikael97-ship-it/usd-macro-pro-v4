# A318 — Duas testemunhas Ed25519 e limites da raiz de confiança (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem merge/Worker/deploy/ordens/provedores/custos adicionais.**

## Situação herdada

A317 (#1769), base desta PR, passou em **Ubuntu e Windows (225 testes executados em cada plataforma, sem falhas inesperadas)**. Validou compromisso Ed25519 da intenção contra um snapshot sintético SQLite, mas a chave da testemunha, o hash da cabeça anterior, o relógio e o desafio ainda eram fornecidos pelo mesmo ambiente. Portanto, um resultado matematicamente correto **não autentica custódia externa**.

A318 acrescenta **duas testemunhas matematicamente distintas** num contrato de *HOLD*. Continua sendo um **laboratório sem raiz independente**.

## Contrato de verificação

`labs/a318_two_witness_root_contract_lab.py` aceita exatamente **duas** declarações Ed25519, de **dois root IDs diferentes** com **dois public keys diferentes**, também diferentes da chave da assinatura A317. Cada declaração assina bytes canônicos em um domínio exclusivo, contendo:

- Identidade da raiz e geração da chave;
- SHA-256 do compromisso A317 completo e assinado;
- Sequência e hash da cabeça anterior da cadeia;
- Época do incidente, nonce do desafio, janela de validade;
- Decisão `HOLD_ONLY`, que não concede execução.

O verificador exige dois votos, proíbe ID repetido, raiz revogada na lista recebida, geração errada, assinatura inválida, nonce/época divergente, replay de sequência e expiração. **Depois disso**, também chama diretamente o verificador da A317, que lê de modo somente-leitura o banco SQLite descartável e compara o snapshot real. Não confia em um campo de resultado `PASS` fornecido pelo solicitante.

Os retornos são:

- `LAB_TWO_SIGNATURES_MATCH_STILL_NO_EXTERNAL_AUTHORITY` — quorum criptográfico 2/2 e A317 coerentes. **Ainda é HARD NO-GO**.
- `LAB_ROOT_QUORUM_VETO` — algum requisito de duas assinaturas, geração, revogação ou cabeça/cadeia falhou.
- `LAB_LOCAL_ANCHOR_VETO` — as duas testemunhas podem estar assinadas, mas o SQLite ou a prova A317 não confere.

## Cenários negativos críticos

Os testes verificam falta da segunda assinatura, uso da mesma chave duas vezes, substituição de chave pinada, rotação não homologada, raiz revogada, chave igual à da A317, nonce/epoch/time/head adulterados, assinatura trocada, campos inesperados, dados mal tipados, remoção de recibo, alteração de mensagem e assinatura A317 inválida com duas assinaturas A318 aparentemente boas.

**Contraprova de falsa independência:** quando o mesmo computador controla a lista de chaves confiáveis, ele consegue gerar **três novas chaves**, recriar cabeça e assinaturas e obter novamente 2/2 assinaturas válidas. Também pode editar o dado local e assinar um snapshot atualizado. A318 trata esses cenários como evidência de que **a raiz de confiança continua ausente**, não como homologação.

Na saída, `roots_independently_pinned=False`, `revocations_independently_attested=False`, `external_high_water_authenticated=False`, `trusted_time_proven=False`, `off_host_custody_proven=False`, `can_resume=False`, `can_resend=False`, `can_authorize_real_effect=False`, `hard_no_go=True`, `zero_auto_resend=True` e `p0_homologated=0` **sempre**.

## Limites explícitos

Os dois signatários sintéticos não estão em hosts distintos, não são controlados por autoridades independentes e não possuem HSM/serviço de custódia, ACL externa nem recibos de fornecedor. A lista de revogações é recebida do próprio chamador, e o mesmo chamador pode simplesmente omitir uma revogação ou promover uma nova chave. Os campos de geração e cabeça anterior não constituem antirollback se o invasor puder apresentar uma referência diferente. **Nenhuma P0 é encerrada.**

A318 não altera `aion_chat/store.py` e não ativa escritor real. Apenas acrescenta contrato e testes. O risco de P0-5/P0-6, autenticação do titular (P0-1), recibo externo (P0-2), custódia/rollback (P0-4) e idempotência de efeitos fora do host (P0-3) permanece.

## Testes e próximo avanço

`python -m unittest -v labs.test_a318_two_witness_root_contract_lab`

No GitHub Actions: Ubuntu e Windows, `cryptography==46.0.4` no runner e regressões A317–A299, incluindo provas de UID e `SO_PEERCRED` Linux. Nenhum serviço pago ou rede de custódia é acionado.

O avanço realmente necessário depois do LAB é ter **pelo menos uma raiz pública pré-fixada fora do controle do operador do SQLite**, com revogação, rotação e cabeça antirollback atestadas independentemente. A318 somente especifica o formato e testa as recusas; não estabelece essa fonte.
