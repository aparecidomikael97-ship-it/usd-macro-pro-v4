# AION BUSINESS External Attestation & Formal Review V1

Schema: `ATLASQUANT_AION_BUSINESS_EXTERNAL_ATTESTATION_V1`

## Objetivo

Fechar os dois gates que ainda podiam depender de declaração do chamador:

1. provar que o CI realmente passou no GitHub para o SHA exato;
2. provar que a revisão humana realmente aprovou a certificação e somente a certificação.

Nenhum dos dois gates ativa runtime.

## Ponte de evidência do GitHub

`atlasquant_aion_business_external_attestation.py` não faz rede sozinho.
O host injeta um leitor somente-leitura. O módulo exige:

- repositório exato `aparecidomikael97-ship-it/usd-macro-pro-v4`;
- SHA exato do pacote;
- `Quality tests` concluído com sucesso;
- `AION Core Security Gate` concluído com sucesso;
- `AtlasQuant - Release Readiness` concluído com sucesso;
- workflow path exato;
- evento aceito;
- contagem positiva de testes;
- fingerprint do pacote ligado ao mesmo SHA e refs.

Se o leitor falhar, retornar payload malformado, workflow faltar, SHA divergir ou o
último run do workflow falhar, o verificador rejeita a prova.

## Revisão humana formal

A certificação BUSINESS agora exige
`ATLASQUANT_AION_BUSINESS_HUMAN_REVIEW_V1`.

O registro precisa estar ligado a:

- especialista BUSINESS;
- versão do contrato;
- `evidence_id`;
- SHA revisado;
- fingerprint técnico revisado;
- identidade textual do revisor;
- data/hora da revisão;
- escopo `CERTIFICATION_ONLY`;
- `runtime_activation_approved=false`.

Além da estrutura correta, um verificador humano independente precisa confirmar
o registro. Um simples `human_review_approved=True` não certifica mais.

## Estados

Com readiness de produto e CI externo verificado:

- sem revisão humana verificada: `TESTED`;
- com revisão formal verificada: `CERTIFIED`.

Mesmo `CERTIFIED` mantém:

- runtime OFF;
- contato externo OFF;
- contrato OFF;
- cobrança/pagamento OFF;
- publicação OFF;
- gasto OFF;
- merge/deploy OFF;
- trading real OFF.

## Princípio

Prova não é autorização operacional. Certificação declara que o especialista
passou pelos gates definidos; qualquer capacidade de agir permanece em gate
separado.
