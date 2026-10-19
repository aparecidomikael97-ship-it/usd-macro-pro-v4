# AION P0 — Original Outbox SQLite: queda de processo e RESTORE/ROLLBACK, 19/10/2026

**Esta é evidência de laboratório em SQLite original, não prova de envio real, não homologação H0 e não produção.** O primeiro lote de testes no Ubuntu confirmou o comportamento. No Windows uma conexão aberta no teste impedia a limpeza do arquivo temporário; o fixture foi corrigido sem alterar os módulos originais. Resultado final CI deve ser validado no workflow, nunca presumido.

## Escopo e fontes verificáveis
- Base original A118 commit `c62fab663c6349d7320f7843c8d09587c514426b`.
- `atlasquant_aion_execution_outbox.py` hash Git blob `6bad4ee9ba5909bbb49c609a5d3ac3c05c16ab83` — INTACTO.
- `test_atlasquant_aion_a110_outbox_ambiguous_block.py` hash Git blob `2ca086e315ee629026968924bae8e64cafd3a1f1` — INTACTO.
- O LAB somente acrescenta `test_aion_p0_first_attempt_sqlite_crash_rollback_lab.py` e workflow isolado, usa `SQLiteChatStore` e `ExecutionOutbox` reais com caminho temporário, e mata subprocessos locais via `os._exit(73)`. No subprocesso, uma modificação de estado feita por SQL DIRETO é exclusivamente um fixture: a lógica de despacho original é inatingível por causa do gate `INDEPENDENT_PRODUCER_NOT_ENROLLED`.
- Não se insere credencial, provedor, efeito externo, Twilio, Worker, chamada de rede, produção, cliente ou dados reais.

## Separação essencial: crash/processo versus falha elétrica real
- `COMMIT` concluído + término abrupto do processo: `UNCERTAIN` reaparece no banco SQLite reaberto e a liberação de claim expirada não o faz `RETRY`; `claim_next` não o reenvia.
- Término do processo ANTES do `COMMIT` da transição sintética `UNCERTAIN`: SQLite reabre `CLAIMED` sem `dispatch_started_at`. O claim pré-despacho pode expirar e reciclar como `RETRY` no escopo de laboratório **porque nenhum efeito externo foi tentado**. Não extrapolar isso para chamada real sem fence.
- Estado `SENT` e `CLAIMED` com marcador de possível efeito ficam bloqueados no reinício; `reconcile` nega antes de inspecionar a propriedade do adapter.
- Os ensaios usam `os._exit`, não corte de energia, falha de `fsync`, barramento/SSD, Windows físico, WAL corrompido ou concorrência real de dispositivos. Assim o P0 de disponibilidade H0 após reboot **continua aberto**.

## LACUNA REPRODUZIDA NO ORIGINAL: RESTORE APAGA A INCERTEZA LOCAL
- A prova cria um backup SQLite **antes** de existir a tentativa incerta.
- A seguir realiza um claim real no Outbox e grava estado `UNCERTAIN` por SQL de fixture, COMMIT, mata subprocesso e reabre comprovando `UNCERTAIN`.
- Quando o backup anterior é restaurado e WAL/SHM descartados em diretório de laboratório sem conexões abertas, a mesma base original volta a `PENDING` e `claim_next` retorna `CLAIMED` novamente.
- Assim o banco original **não detecta sozinho uma restauração antiga do próprio banco**, nem preserva monotonicidade de epoch/attempt sem evidência fora do backup. Isso NÃO é bypass de envio produtivo: `dispatch_claimed` continua bloqueado pela ausência do emissor externo confiável; nenhum adaptador foi executado.
- A restauração é intencional e autorizada apenas sobre arquivo temporário do laboratório; não há manipulação de checkpoint ou banco operacional.

## Correção de segurança necessária (não implementada)
**Não resolver com outro arquivo local junto ao backup e NÃO liberar Worker por um mock verde.** Para detectar rollback significativo, a fonte de verdade do high-water precisa estar em custódia diferente do Outbox e de seus backups, com identidade da conta/tenant/host, sequence/epoch, hash de intenção e recibos de transição, monotonicidade, revogação e fonte autenticada. Verificar o mesmo witness imediatamente antes de registrar/executar uma primeira chamada externa. Um resultado `UNKNOWN`, erro de rede, restore, contagem menor, fork ou testemunha indisponível => BLOCKED e ZERO_AUTO_RESEND.

A solução ainda depende de contrato de custódia independente, desenho de commit/fencing transacional, testes de sincronização e crash, evidência real de produtor e habilitação apenas depois da homologação de TODOS os P0. PRs de laboratório e 10 casos sintéticos não podem fechar o problema.

## Próximos testes com maior valor
1. Auditoria do **original A118** sob abertura do DB por múltiplos processos/threads e concorrência SQLite, com CI Linux/Windows e sem mudar gates.
2. Ataque de rollback após backup/restauração com witness em processo independente; esse witness precisa ser especificado fora do rollback domain e sem autorizar escrita real.
3. Teste físico de queda de energia / desligamento forçado sob autorização específica; não presumir equivalência com `os._exit`.
4. Reexecutar Quality/Security históricos e auditoria externa após correção, sem mascarar regressões do legado.

**0/6 P0 homologados, HARD NO-GO, Worker OFF, sem merge/deploy/gastos e sem reenvio automático.**
