# A307 — Auditoria adversarial do dossiê A306 (somente LAB)

**HARD NO-GO · ZERO_AUTO_RESEND · 0/6 P0 homologadas · sem serviços pagos novos.**

## Falha concreta no código A306 de pesquisa

Na versão A306 anterior à A307, `case_file_locally_valid` ignorava
falhas verificadas nos próprios recibos alegados. Assim, um dossiê com
`CLAIM_FIELDS_INVALID`, `CLAIM_DIGEST_INVALID`, duplicação de evidência,
fontes repetidas ou alegações contraditórias podia continuar com
`case_file_locally_valid=True`. Isso não liberava o AION, mas **podia
transmitir falsa confiança ao revisor**.

Outro erro de classificação: o dossiê podia dizer que um efeito fora
`locally_observed` quando apenas recebia um dicionário com
`sqlite_effect_count=1`, sem corroborar os outros campos do ensaio A305.

## Correção restrita à branch LAB

Este PR empilhado sobre a A306 altera somente o classificador
`labs/a306_manual_intent_reconciliation_lab.py` e adiciona testes A307:

- Falhas estruturais, duplicatas, conflito entre reivindicações, fontes
  repetidas e alegações de ausência contraditórias com a observação local
  agora retiram `case_file_locally_valid`.
- Novo `claimed_evidence_consistent_locally` distingue alegações
  sintaticamente coerentes de fichas vazias ou defeituosas. Nunca autentica
  que as fontes sejam distintas de verdade.
- Para marcar `locally_observed_effect`, exige coerência do contrato A305,
  do identificador semântico da intenção e mensagem, da sinalização de
  `ACK_UNKNOWN`, da razão exata do veto e dos marcadores locais. Um
  objeto arbitrário com apenas uma contagem não é prova de efeito.
- Um formulário `HOLD` vazio pode continuar sendo uma ficha de revisão
  **estrutural**, mas `claimed_evidence_consistent_locally=False` e
  `EXTERNAL_OUTCOME_EVIDENCE_MISSING` mostram que falta comprovação.
- Diversos nomes de fontes, vários hashes e IDs de revisor jamais se tornam
  autenticação externa.

## Matriz adversarial

Testes específicos com dados sintéticos de SQLite da A305 e status
Ed25519 fictícios A304:

- Campos inválidos, tipos errados ou valores não serializáveis;
- Casos antigos, mudança de intenção/geração, declarações de reenvio;
- Duplicatas, reivindicações contraditórias e suposta ausência que diverge
  do histórico SQLite;
- Bancos de observação incompletos, adulterados ou com marcador ausente;
- Matriz de mutações determinística para campos do dossiê e de evidências;
- Regressões A306, A305, A304, A303, A302, A301, A300, A299, A293, A292
  em Ubuntu e Windows.

## Limites permanentes

O A307 **não** verifica identidade real, propriedade do FD SQLite,
durabilidade física, status de revogação externa, custódia imutável ou
efeito em um fornecedor. Todos os dados são temporários e autoatestados,
e uma observação sintética totalmente falsificada ainda poderia
**parecer** localmente coerente. Isso não autoriza retomar.

Todos os caminhos devem manter `can_resume=False`, `can_resend=False`,
`can_auto_retry=False`, `can_authorize_real_effect=False`,
`hard_no_go=True` e `p0_homologated=0`.

**Sem merge, Worker, deploy, ordens, operações externas, restauração
real, custo pago ou homologação P0.** Verde significa LAB somente.
