# AION G118 — leitura assinada após resultado incerto, sem inferir entrega no fornecedor

**Data:** 2026-10-26. **PR:** #1608, Draft LAB, base G117 #1607. **Status:** laboratório validado Windows/Ubuntu; nenhuma operação, Worker ou provedor real. **0/6 P0 homologadas, HARD NO-GO**.

## Problema tratado: reserva de intenção versus efeito no fornecedor

A G115 passou a usar um processo assinador sintético e um Outbox com adaptador de memória. Quando a reserva é gravada, mas o recibo não chega, o Outbox marca corretamente `UNCERTAIN` e não envia. Após reinício, uma consulta assinada pode confirmar que o custodiante de TESTE viu uma reserva. Isso **não prova** entrega, aceite, rejeição, efeito nem ausência de efeito no fornecedor. É perigoso promover status de reserva para `CONFIRMED`, ou interpretar `NOT_FOUND` como liberação para repetir, principalmente quando o histórico do próprio custodiante pode ser restaurado.

## Novo contrato estritamente read-only

Arquivo `labs/a190/g118_signed_witness_recovery_lab.py`:
- Construtor exige a classe exata do cliente G114 que verifica assinatura Ed25519 e challenge, event ID fixado, digest SHA256 da decisão original, escopo (owner/tenant/workspace), request ID e high-water mínimo conhecido pelo chamador.
- `inspect()` emite somente uma consulta de `status` assinada. **Não tem métodos de reserva, bootstrap, envio, confirmação ou reconciliação do fornecedor.**
- Retorna `RecoveryObservationLab` imutável (`frozen=True`) com `allow_send=False`, `allow_retry=False`, `may_mark_provider_confirmed=False`, `provider_outcome="UNKNOWN"` sob **TODAS** as respostas, inclusive ausência assinada.
- `RESERVED` e todos os campos iguais à decisão original → `RESERVATION_PRESENT_PROVIDER_UNKNOWN`: intenção gasta no estado observado; nenhum direito de SEND.
- `ENROLLED` ainda não comprova ausência histórica; `NOT_FOUND` assinado não é ausência autoritativa; assinatura inválida/chave ausente/IPC falho → HOLD.
- Divergência de original, request ID e efeito é CONFLITO. High-water atual abaixo de um piso externo RETIDO sinaliza suspeita de rollback. O piso atualmente é dado por fixture local, e pode ser restaurado com o banco: não é prova antirollback.
- Reserva de evento distinto posterior pode elevar o high-water global sem invalidar a sequência original.

## Prova objetiva cross-OS

Primeiro CI [40377769455](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40377769455): novos e antigos testes de fato executaram `Ran 34 tests\nOK` em Windows e Ubuntu, mas o workflow procurava uma contagem `Ran 23 tests`. A importação de `G115CrossProcessOutboxLab` acrescenta 11 testes da classe base ao discovery, além de 11 herdados e 12 novos, totalizando **34 execuções / 23 métodos únicos**. Corrigimos só o grep do workflow; nenhuma mudança no código de segurança, nas expectativas ou em testes executados.

[GREEN final 40378021974](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40378021974): Ubuntu e Windows concluíram SUCCESS:
- **G118 34/34 PASS** por SO (inclui 22 execuções G115 e 12 G118).
- **G116 24/24 PASS** por SO (inclui repetição descoberta G115 + 2 ataques de injeção de objeto sem assinatura).
- **G114 15/15 PASS** por SO.
- Marcadores: `G118_SIGNED_RESERVED=PROVIDER_UNKNOWN_NOT_CONFIRMED`, `G118_LOST_ACK_RESTART=SIGNED_SPENT_PROVIDER_UNKNOWN`, `G118_RECOVERY_READ_DOES_NOT_PROMOTE_OUTBOX_CONFIRMED`, `G118_SIGNED_NOT_FOUND=NOT_AUTHORITATIVE_PROVIDER_ABSENCE`, `G118_RESET_LOCAL_FLOOR=STILL_NOT_EXTERNAL_ANTIROLLBACK`, `G118_RECOVERY_RESULT=IMMUTABLE_NO_SEND_NO_CONFIRM`.
- Teste do Outbox após perda de ACK confirma estado `UNCERTAIN`, reserva TESTE assinada de sequência 1, resultado do fornecedor desconhecido e zero chamadas ao adaptador de memória.

## Limites e próximos critérios reais

1. O resultado `RESERVED` é do assinador G114 no mesmo computador, com keyfile SQLite e pin controlados pela fixture. Administrador do host pode alterar código/segredo/banco.
2. Restauração do ledger + high-water retido localmente pode fazer parecer que nunca houve reserva. O teste não aprova replay: a G118 continua bloqueando reenvio, mas tampouco pode determinar o histórico verdadeiro.
3. Não há recibo assinado de fornecedor, consulta de status com proveniência externa, autoridade original independente, autenticação OWNER, H0 após reboot homologado, VFS nativo SQLite ou escrita antirollback.
4. Os cinco requisitos A184 externos continuam NÃO ATENDIDOS, e não podem ser convertidos em GREEN por testes sintéticos, tampouco por retirar o HARD NO-GO.
5. G119 Draft #1609 executa em paralelo as baterias canônicas originais sobre G118; resultados devem ser registrados separadamente, sem presumir aprovação.

**0/6 P0 HOMOLOGADAS · HARD NO-GO · DRAFT ONLY · NO MERGE/DEPLOY/WORKER/REAL SEND/FUNDS.**
