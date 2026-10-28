# AION A210 — proposta de cerimônia offline de rotação de raiz (LAB)

**28/10/2026 · DRAFT · HARD NO-GO · 0/6 P0 homologadas**

## Objetivo e limites

A207 demonstrou que um adaptador pode afirmar `CONFIRMED` sem efeito externo.
A208 estruturou um pré-contrato de recibo que jamais autoriza confirmação.
A209 demonstrou em laboratório que uma origem de raiz alegada pelo host não é testemunha independente.

A210 define uma **proposta determinística e auditável** para trocar a raiz
de confiança, antes de qualquer assinatura real, serviço ou aprovação do HUMAN_OWNER.
A proposta não tem chave privada, assinatura validada, autorização nem efeito de ativação.

## Proposta (schema DRAFT V0)

O manifesto imutável pretendido contém:

- `owner_id` e `owner_intent_digest` da solicitação original;
- `ceremony_id`, `nonce_hex` e `requested_at`;
- `previous_root_fingerprint` e `proposed_root_fingerprint`;
- `parent_checkpoint_hash` e `next_checkpoint_sequence`;
- `witness_ref` (somente uma referência, ainda não comprovada).

`labs/a210_offline_root_rotation_proposal.py` rejeita inconsistências,
incluindo:

1. Escopo do proprietário diferente.
2. Reaproveitamento da mesma raiz, pin de origem divergente ou nova raiz malformada.
3. Checkpoint parental trocado e sequência que repete/pula etapas.
4. Nonce reutilizado na história local informada ou formatado incorretamente.
5. Data fora do intervalo e identificadores ausentes.
6. Campo como `owner_approved=True` não previsto no contrato.
7. Digest da intenção inválido.

Quando a proposta é coerente, retorna um compromisso SHA-256 canônico
`proposal_digest`, independente da ordem das chaves JSON.
**Esse hash apenas identifica os dados da proposta; não é assinatura
HUMAN_OWNER, prova antirollback, recibo causal ou ato de aprovação.**

`may_rotate=False` em TODOS os retornos.

## Cerimônia real futura — etapas separadas

1. **PROPOSTA:** gerar compromisso determinístico sem qualquer efeito operacional.
2. **APROVAÇÃO INDEPENDENTE:** proprietário autenticar intenção original e nova raiz fora do host.
3. **TESTEMUNHO:** entidade independente registrar primeiro pin, sequência e hash anterior, protegendo contra rollback.
4. **VERIFICAÇÃO:** assinatura via biblioteca auditada, root pin realmente imutável fora do host, replay/rotação testados.
5. **ATIVAÇÃO:** somente após P0 independentes homologadas, revisão de segurança e uma autorização operacional futura distinta.

Neste A210 só há a etapa 1 e testes de rejeição sintética. Não antecipar as etapas 2–5 com flags, segredos locais ou mocks.

## Testes

`labs/test_a210_offline_root_rotation_proposal.py`: 19 grupos verificam
determinismo, mudança de digest após alteração da raiz, parent/owner, replay,
sequence gap, nonce, clock, ausência de witness e imutabilidade.
CI A210 executa também A209, A208 e regressão A206 em Ubuntu e Windows.

## Segurança

Sem alterações de execução, Outbox, Worker, UI Negócios, provider, integração cloud,
credenciais, rede ou custos. `UNCERTAIN=ZERO_AUTO_RESEND`.
**0/6 P0. HARD NO-GO.** A207 RED segue pendente de prova externa e não deve
ser mascarado por aprovação de testes estruturais.
