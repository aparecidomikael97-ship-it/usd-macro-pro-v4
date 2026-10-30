# A308 — Evidência vinculada ao conteúdo e recibo assinado (LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · nenhum novo serviço contratado.**

## Lacuna real observada no LAB anterior

A307 corrige a classificação enganosa de dossiês malformados. Porém, na A306/A307, o campo `claimed_evidence[].evidence_sha256` era verificado somente como uma sequência de 64 caracteres hexadecimais: **não havia documento, conteúdo nem recibo com o qual confrontar o hash**. Uma sequência hexadecimal inventada podia satisfazer a checagem estrutural do dossiê. Isso não concedia nenhuma autorização, mas era informação insuficiente de proveniência.

## Nova separação de evidências

`labs/a308_evidence_provenance_contract_lab.py` adiciona ensaio de três camadas, **sem tocar no AION operacional**:

1. `case_structure_locally_consistent`: a avaliação A306/A307 é apenas internamente consistente. Uma ficha preenchida não autentica relator, revisor nem fato externo.
2. `payload_digests_match_locally`: calcula SHA-256 do **conteúdo binário apresentado**, com limite de 16 KiB por evidência e 8 itens, e compara com cada hash alegado.
3. `receipt_chain_locally_consistent`: verifica Ed25519 real sobre comprovante sintético com separador de domínio, vinculando fonte, referência, intenção, mensagem, desfecho alegado, hash da evidência, hash de todo o dossiê, nonce, geração do incidente, sequência, hash do comprovante anterior e tempo de validade.

A prova recusa bytes trocados ou ausentes, chave pública diferente, assinatura adulterada, origem sem pin, chaves duplicadas, reuso de nonce, head antigo, referência alterada, caso antigo, incidente incompatível, prazo expirado e recibo deformado. Os testes também mostram que uma chave e um último head **forjados juntos pelo mesmo host** podem produzir recibos matematicamente coerentes.

## Contrato de confiança

As chaves privadas das fontes são geradas **dentro dos testes** e seus pins, heads, relógio e nonce são fornecidos pelo próprio chamador. A presença de dois nomes diferentes não comprova organizações, custódia separada, reconhecimento do titular, entrega do fornecedor ou inexistência de revogação.

A saída permanece incondicionalmente:
- `evidence_provenance_independent=False`;
- `actual_provider_outcome_verified=False`;
- `last_seen_heads_off_host_verified=False`;
- `can_resume=False`, `can_resend=False`, `can_auto_retry=False`, `can_authorize_real_effect=False`;
- `zero_auto_resend=True`, `hard_no_go=True`, `p0_homologated=0`.

Um recibo assinado pela fonte fictícia "provider" NÃO é confirmação de uma operação real. Para prova real serão necessárias autenticação independente da origem e custódia durável/monotônica, além de reconciliar o efeito externo pela fonte original, com autorização separada. Esse LAB não consulta redes/provedores, não recebe credenciais nem reativa Worker.

## Como executar

`python -m unittest -v labs.test_a308_evidence_provenance_contract_lab`

Também executar regressões A307/A306/A305/A304/A303/A302/A301/A300/A299/A293/A292 em Ubuntu e Windows, Python 3.12, com biblioteca livre de criptografia instalada no CI; PR empilhada sobre A307, somente draft. **Teste verde significa investigação válida, não homologação P0.**
