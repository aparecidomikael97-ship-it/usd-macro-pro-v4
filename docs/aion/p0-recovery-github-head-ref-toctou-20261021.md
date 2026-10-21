# A133 — Recheck de HEAD da branch antes de restaurar (LAB; NO-GO)

Data: 21/10/2026. Stack sobre PR Draft #1416. Não é a testemunha externa necessária à homologação.

## Lacuna demonstrada antes do patch

O preflight A129 lê o arquivo no GitHub e A130 compara revisão histórica com a branch. Mas a recuperação não reconfirmava o commit HEAD da branch imediatamente antes do save. Uma branch movida/forçada enquanto a revisão era relida podia alcançar `save_runtime_checkpoint`, desde que seu SHA de blob anterior ainda fosse compatível. O CAS GitHub por SHA de arquivo não autentica o commit HEAD nem prova monotonicidade.

RED-first: https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39670858045. Os 13 testes sintéticos não acessam GitHub nem escrevem; Ubuntu 12 FAIL + 1 PASS antes da correção. A saída inicial chegava a save simulado, sem GET de HEAD.

## Implementação delimitada

A função `_recheck_runtime_branch_head_before_save` obtém em leitura o ref `git/ref/heads/<runtime-branch>` exato, exige objeto commit e SHA hexadecimal de 40 caracteres, compara ao `runtime_branch_head` observado na resposta de ancestry de A130 e nega se houver diferença, timeout, JSON inválido, tipo inválido ou resposta de outra branch.

O gate roda após digest histórico revalidado e antes de construir checkpoint/append de evento/save. Sem reenvio automático. Cinco mocks legados e A129 são atualizados só para fornecer o novo gate; A130 agora exige as DUAS leituras GitHub nos caminhos positivos (compare + head-ref). A133 testa 13 cenários incluindo ref alterado, race, timeout, type mismatch e caminho legítimo simulado.

## Limites de confiança

A rechecagem é feita na MESMA autoridade GitHub e não está protegida contra rollback coordenado, replay consistente, split-view, mudança após o GET ou manipulação pelo operador dessa conta. Ela não equivale a testemunha independente, sequência monotônica nem comprovante do fornecedor. O CAS por blob permanece condição adicional, não evidência de custódia independente. Não existe head witness matriculada, nem assinatura de HUMAN_OWNER homologada.

Critério: CI direcionada Ubuntu/Windows no HEAD exato; Quality canônica 588 módulos e Security A74 em etapa separada, sem waivers. Estado esperado: HARD NO-GO / 0 de 6 P0 homologados / Worker OFF / ZERO_AUTO_RESEND. Nada em main, produção, Worker ou pagamento.