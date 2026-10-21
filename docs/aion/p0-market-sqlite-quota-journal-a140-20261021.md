# AION P0 A140 — Diário de cotas SQLite, persistência local e recuperação conservadora (LAB)

**Data:** 21/10/2026. **Base:** PR #1423 (A139); branch isolada A140. **Permissões:** nenhuma alteração de main, nenhum merge, deploy, conexão com fornecedor pago ou Global Worker.

## Defeito e risco

A139 usava MemoryOnlyReservationLedger: após reiniciar o processo, reservas e orçamento desapareciam. Reexecutar uma chamada de dados real depois de um resultado incerto poderia duplicar cobrança. O A140 modela uma reserva durável local ANTES da chamada, mas mantém a fonte explicitamente SINTÉTICA. Nenhum resultado pode ser promovido a execução de fornecedor, recibo independente, nem prontidão H0.

## Implementação

- `atlasquant_market_sqlite_quota_a140.py`: ledger SQLite com arquivo fixo `aion_a140_quota_ledger.sqlite3` apenas em pasta LAB pré-existente FORA do checkout, sem symlinks, sem destino configurável para checkpoint.
- `PRAGMA synchronous=FULL`, transação `BEGIN IMMEDIATE` para serializar reservas, restrição UNIQUE no run_id e CHECK para unidades/state. `COMMIT` seguido de readback por conexão distinta; se resultado do COMMIT/readback ficar incerto, a API retorna DENY e **NUNCA** chama a fonte novamente automaticamente.
- Política de limite 1..100 persistida numa linha singleton versionada; alterações no limite após criar o banco (mesmo para aumentar) exigem revisão/migração e falham fechadas.
- Estado inicial `RESERVED_UNCERTAIN`, inclusive após erro, timeout ou reinício. `record_local_output(run_id,payload_sha256)` pode passar a `LOCAL_OUTPUT_OBSERVED` apenas uma vez, após escrever o arquivo sintético, e comprova somente a observação local, **não** efeito do provedor.
- Fechamento explícito de cada handle SQLite e de abertura com PRAGMA que falha. Esse detalhe era necessário no Windows: a primeira versão retornou 30 erros WinError32, depois 5 até o fechamento completo. Não se limpou evidência alterando asserts ou abandonando testes.
- `atlasquant_market_boundary_a139.py`: aceita somente os tipos exatos do ledger em memória antigo OU ledger SQLite LAB; reserva antes da leitura, recusa objetos genéricos, output único fora do checkout, e marca resultado SQLite somente depois do arquivo, sem retry/refund em falha.

## Testes e evidências

- RED-first inicial: A140 ainda ausente; depois primeiras suites SQLite revelaram erros de ciclo de vida apenas no Windows.
- **40 testes A140** incluem reservas persistindo após criar novo objeto e processo encerrado abruptamente; duplicidade após restart; concorrência por run_id e limite entre threads/conexões; mudança de política; SQLite corrompido ou metadados ausentes; lock; rejeição de symlinks/caminhos; falha de leitura após COMMIT mantendo reserva; arquivo escrito com recibo SQLite incerto sem emitir sucesso; transação não confirmada após os._exit.
- **Testes 39/40 distinguem fatos**: um arquivo SQLite de uma época antiga pode ser restaurado por um atacante local para reabrir um run_id usado; isso é uma vulnerabilidade demonstrada em LAB, **não uma defesa contra rollback**. Outro teste confirma que transação não commitada desaparece quando o processo termina abruptamente. A segunda condição só é segura porque neste LAB não houve leitura de fornecedor antes de reservar.
- Regressões junto ao ledger: 30 A139, 25 A138 e 14 de contrato de workflow, por SO.
- [Primeira rodada A140 totalmente GREEN no SHA intermediário #39694073142](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39694073142): **109 PASS Ubuntu +109 PASS Windows =218 testes**, sem testes desabilitados.

## Distinção entre durabilidade e autoridade

Este SQLite é uma única cópia em sistema de arquivos local. Não possui testemunha externa independente, antirollback/PITR, prova de revogação de chaves, identidade HUMAN_OWNER, recibo de efeito/no-effect de fornecedor, reconciliador de cobranças, protocolo de crash entre o fornecedor e o sink ou garantias de atomicidade entre máquina e provedor. Se a pasta LAB, o SQLite ou a máquina forem comprometidos, a reserva pode ser forjada/retrocedida. SQLite local não homologa nenhum dos 6 P0.

## Critério para etapa futura

Separar credencial/escopo de provedor e destino de mercado do núcleo; criar prova externa de reserva e readback com custódia independente; testar falhas entre reserva durável, envio externo, resposta incerta, observação de efeito e consumo de quota; nunca reenviar automaticamente; reexecutar Quality/Security canônicas sem waivers, mantendo histórico exato de falhas e CI no commit final.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND · SEM MERGE OU DEPLOY.**