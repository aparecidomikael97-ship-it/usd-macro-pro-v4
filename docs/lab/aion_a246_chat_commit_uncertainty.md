# A246 — SQLite chat COMMIT outcome uncertain: fail-closed em processo (LAB)

**HARD NO-GO · P0 0/6 · sem Worker, deploy, merge, custo ou efeito externo.**

## Diagnóstico
Na operação `append_message`, `sqlite3.Connection.commit()` pode retornar erro quando o host já perdeu a certeza de que a transação persistiu. O tratamento antigo classificava `sqlite3.OperationalError` com texto “busy/locked” como DEGRADED, o que não bastava para vetar novos acessos. Um `rollback()` posterior é apenas best-effort e não prova que o COMMIT não aconteceu.

## Mitigação estrita
O método **somente de mensagens** agora envolve `commit()` em um try/except: qualquer exceção após iniciar o COMMIT marca a instância `FAILED` com `COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY` e lança `StoreCommitOutcomeUncertainError`. Operações subsequentes na mesma instância, inclusive nova mensagem, criação de conversa e health check, são recusadas. Erros **antes** do COMMIT continuam no tratamento existente.

## Provas / limites
- Banco de teste real é transacionado; proxy de laboratório chama o COMMIT real e só então simula perda de ACK. O registro confirmado pode estar lá, mas o chamador não recebeu sucesso.
- Falha antes do COMMIT também é tratada conservadoramente, sem permitir reenvio cego pela mesma instância.
- Operação normal continua funcional.
- **XFAIL explícito:** após fechar/reabrir o SQLite, a incerteza não é preservada nem autenticada por testemunha externa; este teste documenta a lacuna real de P0-6.
- Não houve ensaio real de queda de energia, durabilidade física, VFS/FD autenticado, garantia de fornecedor externo ou qualquer efeito financeiro.
- Outras rotas de escrita que usam `with db:` ou manipulam o DB diretamente não são cobertas por este patch. Devem ser revisadas separadamente para semântica de COMMIT incerto.

## Invariantes
`UNCERTAIN=ZERO_AUTO_RESEND` permanece. Nenhum sistema externo, Worker, envio, implantação ou custo foi ativado. Não transformar XFAIL em sinal de homologação.
