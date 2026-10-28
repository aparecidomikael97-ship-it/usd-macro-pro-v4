# A214 — Entrada de candidatos de evidência externa (somente leitura)

**Status: HARD NO-GO.** Implementação experimental, isolada na branch Draft A214. **0/6 P0 externos homologados**. O Núcleo AION não envia, confirma, reenvia ou publica efeitos com base neste mecanismo. UNCERTAIN=ZERO_AUTO_RESEND.

## Fronteira de confiança

A213 fechou a via perigosa: uma resposta positiva de adapter.send ou adapter.reconcile **não prova** um efeito no provedor; o Outbox não faz a transição CONFIRMED e não cria um lançamento em action_effects.

A214 adiciona somente uma **porta de pré-inspeção** de uma alegação não confiável, sem alterá-la:

1. ExecutionOutbox.evidence_challenge(key) recupera o registro por escopo na SQLite local e monta uma *pergunta local determinística* apenas se o estado for SENT ou UNCERTAIN.
2. O desafio vincula owner, tenant, workspace, chave de idempotência, decisão, intenção, ação, SHA-256 do payload local, política, autorização, sequência do agregado, tentativa, estado, início de dispatch, envio (se houver) e janela temporal original.
3. O digest SHA-256 de um domínio fixo e JSON ordenado **não é uma assinatura e não prova autenticidade**, porque um host comprometido pode gerar os mesmos bytes.
4. inspect_untrusted_effect_candidate(key, candidate, observed_at=...) faz validação estrutural e confronto de campos com o Outbox **atual**. Aceita mapa de dados ou JSON de tamanho limitado, rejeita chaves JSON repetidas, atributos inesperados, valores não finitos, timestamps sem timezone, digests inválidos e mudanças na intenção/tentativa.
5. Mesmo para o candidato perfeito, o resultado é **apenas** matches_local_binding=True, may_confirm=False, LOCAL_BINDING_OK_EXTERNAL_AUTHORITY_AND_EFFECT_UNPROVEN.

provider_id, provider_event_id, effect_ref, provider_receipt_digest, witness_root_fingerprint, witness_checkpoint_hash e witness_sequence são **declarações de um possível host adversário**. Seu formato correto não verifica identidade do provedor, assinatura, testemunho, inclusão, consistência, não replay ou ocorrência real do efeito. Um par de supostas testemunhas de mesmo host não configura independência.

## Garantias e limites

- **Sem** rede, consulta ao provedor, captura de credencial, chave de assinatura externa, validação de cadeia, inclusão de log externo ou armazenamento de nonce/replay.
- **Sem** escrita da porta na SQLite e sem estado CONFIRMED, reabertura de CLAIMED, inserção em action_effects, compensação executada ou envio/reenvio; _confirm segue bloqueado.
- As estruturas de resultado são frozen dataclasses. Isso impede reatribuição acidental, mas não se apresenta como proteção contra host comprometido.
- A comparação de candidato com o estado local ajuda a descartar erros grosseiros e troca de operação. **Não é autorização**, autenticação, decisão final nem homologação P0.
- occurred_at e observed_at são checados como sequência temporal *declarada*; observed_at também é argumento controlado pelo host, sem relógio seguro.
- O digest local usa serialização JSON própria com sort_keys=True; **não** implementa canonicalização RFC 8785 nem assinatura HTTP RFC 9421. Migração futura requer contrato explícito e testes independentes.
- Não há caminho adicional para confirmar mesmo em caso de match, propositalmente.

## Teste adversarial

labs/test_a214_external_evidence_intake.py: 30 testes com SQLite real e adapters totalmente sintéticos. Cobrem SENT/UNCERTAIN, match sem confirmação, imutabilidade do resultado, replay, fraude por campos "verified", alteração de escopo/payload/tentativa/estado, JSON ambíguo, campos extras, falsos hashes de testemunha, janelas temporais, recusa no estado CLAIMED, _confirm bloqueado e invariância db.total_changes/effect_count()==0.

CI A214 executa regressão A207 original (inalterada), A202–A213, Outbox, saga e caos nos dois sistemas operacionais. A suíte é local e sintética: passar os testes não substitui prova de uma integração externa independente.

## Requisitos antes de qualquer evolução de autoridade

Bloqueado enquanto **cada uma das seis obrigações P0 externas** permanecer não homologada. Uma futura proposta separada deverá demonstrar, com terceiros independentes e com rastreabilidade auditável, de onde vem a raiz confiável, como se verifica assinatura e identidade externa, inclusão/consistência de recibos de efeito, revogação e replay, coerência entre resultado e operação, e proteção contra rollback/host comprometido; ainda exigirá homologação de corridas, falhas, custo e guardrails de produção.

Referências de desenho (não implementadas aqui como norma):
- RFC 8785: JSON Canonicalization Scheme — https://www.rfc-editor.org/rfc/rfc8785.html
- RFC 9421: HTTP Message Signatures — https://www.rfc-editor.org/rfc/rfc9421.html
- NIST SP 800-57 Parte 1 Rev. 5, gestão de chaves — https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final

**Decisão A214: diagnóstico local sem autoridade. HARD NO-GO. 0/6 P0; UNCERTAIN=ZERO_AUTO_RESEND.**
