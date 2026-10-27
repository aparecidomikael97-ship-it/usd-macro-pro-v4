# G137 — gatilho SQLite de admissão antes de action_decisions (LAB)

**Cadeia:** #1628 G136 → G137. **0/6 P0 HOMOLOGADAS. HARD NO-GO.**

## Hipótese
O G136 demonstrou que qualquer chamador pode ignorar o facade Python e usar a `ExecutionOutbox.enqueue()` real. No G137, a proteção está no **SQLite** já aberto pela Outbox: um `BEFORE INSERT` em `action_decisions` recusa qualquer linha quando não encontra um registro local `g137_local_stage_permits_lab` que corresponda ao escopo completo, `intent_ref`, ação e hash do payload. O `AFTER INSERT` consome o registro **na mesma transação** da decisão/Outbox. Aplica-se também a `enqueue` sem `semantic_event_id_lab`.

Antes de produzir o registro local, o orquestrador de laboratório exige o manifesto original e assinaturas Ed25519 sintéticas do G135, depois uma reserva por subprocesso do G134, e só então prepara o registro vinculado ao hash do payload e chama a Outbox real. Receber ACK desconhecido ou falhar após reservar exige UNCERTAIN e não tentar novamente automaticamente.

## 15 casos
1. Assinatura e custódia sintéticas → INSERT real, autorização local consumida.
2. Chamado direto com evento sem autorização local → barrado pelo SQLite.
3. Chamado direto sem qualquer identificador semântico → também barrado.
4. Autorização de hash/payload diferente → barrado.
5. Autorização em outro tenant → barrado.
6. Autorização para outro `intent_ref` → barrado.
7. Marcador local `consumed=1` junto com a transação real.
8. Identidade ou valor econômico alterado → nenhuma autorização criada.
9. Rollback SOMENTE da Outbox AION → custodiante separado intacto nega nova gravação.
10. Timeout/ACK não confiável de custodiante → sem stage/permissão.
11. **RED:** atacante grava uma autorização falsa diretamente na mesma base → INSERT não autorizado passa.
12. **RED:** atacante faz `DROP TRIGGER` → chamada direta volta a passar.
13. **RED:** atacante abre um novo SQLite sem gatilho → chamada direta passa.
14. **RED:** atacante restaura juntos o SQLite AION e o custodiante → mesmo efeito pode ser readmitido.
15. A Outbox padrão nunca chama o adapter `send` no teste, mesmo com staging local.

## Limite de segurança não negociável

Isto é um **gatilho de SQLite de laboratório instalado opcionalmente**. Não modifica o código operacional da Outbox, não impede outro `sqlite3.Connection` privilegiado de fazer `DROP TRIGGER` ou `INSERT` falso na tabela de autorizações. Uma autorização local é um *objeto forjável*. G137 não é módulo do SQLite VFS; não captura restauração no mesmo inode, não tem garantia de persistência contra rollback hostil, não autentica primeira identidade HUMAN_OWNER nem possui custódia off-host ou recibos reais do provedor.

Portanto, **até o sucesso completo de 15 testes significa apenas que o experimento reproduz tanto a contenção restrita quanto os contraexemplos de segurança.** Nunca contar testes de ataques reproduzidos como prova de que o ataque é impossível. O G122 deve continuar 5 testes externos RED por sistema. O G125 canônico permanece íntegro e inalterado.

**Nenhum merge, produção, envio real, Worker, deploy, dados de cliente, chave privada de serviço ou gasto.** A PR permanece Draft.
