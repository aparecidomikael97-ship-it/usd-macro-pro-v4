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
- **45 testes A140** incluem reservas persistindo após criar novo objeto e processo encerrado abruptamente; duplicidade após restart; concorrência por run_id e limite entre threads/conexões; mudança de política; SQLite corrompido ou metadados ausentes; lock; rejeição de symlinks/caminhos; falha de leitura após COMMIT mantendo reserva; arquivo escrito com recibo SQLite incerto sem emitir sucesso; transação não confirmada após os._exit.
- **Testes 39/40 distinguem fatos**: um arquivo SQLite de uma época antiga pode ser restaurado por um atacante local para reabrir um run_id usado; isso é uma vulnerabilidade demonstrada em LAB, **não uma defesa contra rollback**. Outro teste confirma que transação não commitada desaparece quando o processo termina abruptamente. A segunda condição só é segura porque neste LAB não houve leitura de fornecedor antes de reservar.
- Regressões junto ao ledger: 30 A139, 25 A138 e 14 de contrato de workflow, por SO.
- [Primeira rodada A140 totalmente GREEN no SHA intermediário #39694073142](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39694073142): **109 PASS Ubuntu +109 PASS Windows =218 testes**, sem testes desabilitados.

## Distinção entre durabilidade e autoridade

Este SQLite é uma única cópia em sistema de arquivos local. Não possui testemunha externa independente, antirollback/PITR, prova de revogação de chaves, identidade HUMAN_OWNER, recibo de efeito/no-effect de fornecedor, reconciliador de cobranças, protocolo de crash entre o fornecedor e o sink ou garantias de atomicidade entre máquina e provedor. Se a pasta LAB, o SQLite ou a máquina forem comprometidos, a reserva pode ser forjada/retrocedida. SQLite local não homologa nenhum dos 6 P0.

## Critério para etapa futura

Separar credencial/escopo de provedor e destino de mercado do núcleo; criar prova externa de reserva e readback com custódia independente; testar falhas entre reserva durável, envio externo, resposta incerta, observação de efeito e consumo de quota; nunca reenviar automaticamente; reexecutar Quality/Security canônicas sem waivers, mantendo histórico exato de falhas e CI no commit final.

**HARD NO-GO · 0/6 P0 homologados · Worker OFF · ZERO_AUTO_RESEND · SEM MERGE OU DEPLOY.**
## Segunda revisão independente com Codex (desktop Windows, 21/10)

Foi copiado SOMENTE o código A140 da PR Draft (três arquivos sem credenciais) para pasta TEMP isolada e submetido ao Codex em modo `read-only`, sem edição nem execução. A análise identificou dois erros graves locais e uma inconsistência de estado:

1. `collect_synthetic_market`: `symbols` aceitava `list` mutável; um teste alterando a lista logo após a reserva demonstrou **três leituras para uma unidade reservada**. Correção: criar snapshot tuple imutável ANTES de validar, reservar e consultar. Isso não liga nem simula fornecedor real.
2. `_initialize` podia recriar `reservations` faltante em banco existente e apagar a evidência lógica das reservas anteriores. Correção: exigir tabelas pré-existentes `quota_policy` E `reservations` antes de qualquer `CREATE TABLE IF NOT EXISTS` em arquivo SQLite já existente. Um SQLite válido porém restaurado a época anterior continua vulnerável sem witness externa.
3. Se o arquivo JSON fora do checkout foi escrito mas o recibo SQLite falhou, `market_files_written=0` omitiria a presença do arquivo. Correção: sinalizar `market_files_written=1`, `local_file_observed=true`, `reconciliation_required=true`, mantendo `saved=false` e `automatic_retry_allowed=false`.

Os testes **41, 42, 43** reproduziram exatamente essas três falhas na [RED-first #39694778120](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39694778120) antes das correções. Os testes **44, 45** injetam exceção sintética antes/depois de COMMIT: pós-COMMIT retorna bloqueio, mas reserva permanece; pré-COMMIT é revertido. Não há rede ou fornecedor.

**Após correções:** [bateria A140 #39694896120](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39694896120): **45 + 30 + 25 + 14 = 114 PASS por OS, 228 PASS total**; nenhum waiver. Também se reexecuta Quality/Security canônicas no HEAD final.

**Limite adicional NÃO RESOLVIDO:** as checagens de symlink/regularidade antecedem a abertura; se outro ator puder trocar diretórios ou junctions Windows entre verificação e uso, existe risco TOCTOU. Corrigir exigiria isolamento ACL real ou validação de identidade por handle, além de witness externo antirollback. Esta PR LAB não afirma fechar essas lacunas.

**Mantido:** HARD NO-GO, 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND, sem merge, deploy, chamada paga, ativação de coletor ou alteração de Checkpoint Mestre.
