# A255 — Vínculo de duas assinaturas sem falsa independência (LAB P0-2/3/4)

**HARD NO-GO · 0/6 P0 homologadas · nenhum Worker, provider, deploy, merge ou contratação.**

## Objetivo

A254 define o evento de negócio com ID imutável e assinatura Ed25519 de origem **sintética**. A243 define uma reserva de primeira tentativa assinada por testemunha **sintética**. Sem um contrato de vinculação entre as duas, uma reserva assinada para um evento poderia ser reaproveitada para outro evento/escopo, apesar de os dois objetos terem assinaturas isoladamente válidas.

A255 cria um **verificador de vinculação de formato**, sem conexão real ou autoridade de execução. O teste de duas chaves distintas **não comprova dois controladores independentes**, e não dá permissão para enviar.

## Requisitos do envelope

- Origem: envelope A254 vinculado a `event_id`, owner/tenant/workspace, ação, agregado e hash do payload. A identidade **não depende** do request-ID técnico.
- Testemunha: novo envelope A255 `RESERVED` com domínio exclusivo, assinatura Ed25519 de segunda chave, `issuer` e `key_id` distintos, `event_id`, `event_effect_digest`, `origin_envelope_sha256`, escopo, sequência, janela UTC curta e desafio de 256 bits fornecido pelo solicitante.
- Campos fechados, assinatura verificada sob chave de fixture; não aceita `verified`, claims extra, sequência `True`, hash/challenge alterados, assinatura/TTL inválidos ou escopo/evento divergente.
- `SyntheticTwoPartyReservationLab.review` usa ledger A254 em memória e `high_water` local com mutex. O replay é negado **enquanto a mesma instância permanece íntegra**, não após restauração conjunta.
- Se um envelope estruturalmente válido falha na etapa posterior, o evento de origem pode ter sido consumido localmente. O protocolo deve **recusar reenvio cego e exigir reconciliação independente**.
- Todo resultado, inclusive dois signatários sintéticos válidos, tem `authorizes_send=False`, `independent_origin_proven=False`, `independent_witness_proven=False`, `p0_homologated=0`. Nenhum callback conecta isto ao Worker.

## 18 testes

1. Dois envelopes vinculados e assinados não concedem autoridade.
2. Dois eventos autênticos sintéticos com mesmo payload continuam distintos.
3. Mesmo evento, outro request-ID, é recusado.
4–12. Origem/assinatura da testemunha erradas, digest, escopo, desafio, envelope trocado, sequência, relógio, schema extra, ACK perdido são recusados.
13. Chave idêntica ou identidade de emissor idêntica é rejeitada no construtor.
14. Perda do ACK não retorna permissão.
15. Integração negativa com Outbox exige **UNCERTAIN, 0 adapter.send, 0 effects**.
16. 48 revisões concorrentes do mesmo evento obtêm no máximo um resultado estruturalmente vinculado.
17. **XFAIL**: duas chaves host-pinned fraudulentas podem parecer independentes.
18. **XFAIL**: rollback/reinício host simultâneo das duas memórias permite repetição.

Também executa regressões A254/A243/A253 e laboratório SQLite.

## Provas externas ainda necessárias

1. Cerimônia real HUMAN_OWNER e emissor de eventos externos autênticos.
2. Proveniência, rotação/revogação e distribuição confiável das duas raízes **fora da autoridade do host AION**.
3. Testemunha monotônica resistente a rollback e reserva linearizável de primeira tentativa entre falhas/crashes reais.
4. Recibos verificáveis de conclusão/ausência de efeito do provedor.
5. Atestado nativo FD/VFS e semântica de COMMIT/restore do SQLite com testes de durabilidade física.

Não existe fornecedor contratado, prova externa obtida, credencial real, autorização de gasto ou mecanismo seguro de reativação nesta PR. Ainda que a CI fique verde, não converte estrutura sintética em autoridade independente.

**HARD NO-GO / 0-6 P0 / UNCERTAIN=ZERO_AUTO_RESEND**. Estratégia: Trader prioritário, Investimentos pronto para expansão posterior, Negócios congelada.
