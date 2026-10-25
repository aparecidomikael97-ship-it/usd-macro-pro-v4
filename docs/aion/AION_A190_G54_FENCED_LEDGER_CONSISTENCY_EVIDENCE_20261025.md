# AtlasQuant / AION A190 — G54 fenced/snapshot ledger consistency (2026-10-25)

**Estado:** branch LAB isolada, `lab/aion-a190-g54-fenced-ledger-consistency-20261025`, empilhada sobre a G53 candidata. **Não há PR G54 confirmada**: a tentativa de criar a PR Draft foi recusada por uma restrição da ferramenta. Não contornar. Nenhum merge, deploy ou Worker.

## Codex — revisão independente apenas de leitura

Codex instalado no Windows, versão 0.164.0-alpha.11.1, executou sessão `01a173ea-0b6e-7ea0-a6d4-a6ea1fbccd42` com `-s read-only --ephemeral` no código G53. A revisão estática destacou três possíveis lacunas: (1) ledger preexistente na confirmação com `fence_lab`/`reconcile_snapshot_lab`; (2) uma projeção JSON alterada antes de reconfirmação com projeção estrita; (3) fechamento de transação após falha/abortamento incomum. O Codex **não executou testes e não alterou arquivos**. Apenas a primeira lacuna foi investigada e corrigida nesta G54; as demais seguem sem homologação.

## Resultado adversarial reproduzido (RED antes do patch)

Arquivo `labs/a190/test_g54_fenced_ledger_consistency_lab.py` criado primeiro em `ff2847af023bf5473d6e686abd6b3b85508b180e`, antes de alterar o motor. Windows, SQLite descartável, sem rede ou efeito real:
- 9 testes executados;
- 7 passaram, 2 **falharam**, especificamente os testes 05 e 06, que exigiam recusar um histórico de efeito já existente com a mesma referência enquanto a operação continuava em `UNCERTAIN`.
- Prepatch `_confirm` aceitava a referência compatível, conservava o timestamp antigo do ledger e gravava timestamp novo em `action_outbox`, construindo uma história inconsistente.

## Patch restrito (GREEN)

Em `46b46802db97001653a84718a060c901b8404c6c`, a validação de `_confirm`, ainda sob transação SQLite, passou a rejeitar efeito preexistente quando a linha Outbox não está `CONFIRMED`, inclusive com fence/snapshot. A verificação ocorre depois da guarda de colisão com referência diferente, preservando o erro histórico de colisão. Não há reparação silenciosa, reenvio ou criação de efeito externo.

**Mesmos 9 testes G54: 9/9 PASS** no Windows após a correção, com os marcadores `G54_FENCED_ORPHAN_GREEN=NO_ADOPTED_LEDGER` e `G54_SNAPSHOT_ORPHAN_GREEN=NO_ADOPTED_LEDGER`.

**Regressão completa G30–G54:** 472/472 PASS no Windows, checkout `C:\Users\apare\AtlasQuant-G54-Fenced-LAB-20261025` limpo. Inclui G53 11, G52 10, G50 11 e regressões herdadas, sem grupo independente G51 (a consolidação de 11 casos está na suíte G50).

Workflow `.github/workflows/aion-a190-g54-fenced-ledger-consistency-lab.yml` criado em `5bbf6639668e6208f3ad0e32749730733e73f66d`, configurado para 472 testes por OS (Windows + Ubuntu). **Como a PR Draft não foi aberta, não existe nesta evidência execução verificada da matriz G54**. Nunca chamar o workflow configurado de CI verde.

## Restrições e riscos que seguem pendentes

- Exceções/abortamentos de transação em condições extremas e projeção estrita adulterada na reconfirmação.
- Autenticidade dos recibos de fornecedores e identidade externa do proprietário, testemunha monotônica independente, rollback físico/hospedagem hostil, recuperação da primeira tentativa, disponibilidade H0 após reinício.
- Qualidade/Security canônicas e dependências históricas requerem verificação separada.

**0/6 P0 homologados — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.** Nada foi enviado a fornecedor real; nenhum cliente, segredo, pagamento, merge ou deploy foi manipulado.
