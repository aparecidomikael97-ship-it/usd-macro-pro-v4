# AION P0 — adjudicação forense dos dois candidatos SQLite pré-19/10
**20 de outubro de 2026 | HARD NO-GO | 0/6 P0 | Worker OFF | ZERO_AUTO_RESEND**

## Descoberta verificável em logs GitHub (não só nos títulos das PRs)

**CANDIDATO READ, 10/10, Draft #1195:** branch candidata resolveu uma indisponibilidade de rerun Streamlit que retinha a conexão nativa SQLite num session_state ao mudar a thread. A execução final #38089857958 executou **37 testes em Windows e 37 em Ubuntu**, verdes no SHA e0e249db64c1bef32ff47f0048a9900542dd144a. Há um teste concreto test_real_host_rerun_on_another_thread_reuses_no_native_connection dentro do blob c2c4716dd1ce6b7323ba5f21a2a87f2b73aa85dd. A reprodução pré-correção contra main descrita no PR NÃO possui neste dossiê um run/commit/test de origem vinculado aos seis P0. Por isso READ segue OPEN_UNMAPPED. A execução de 19/10 #39316307777 é outra suíte posterior: 15 métodos, 4 FAIL + 9 ERROR + 2 PASS em cada OS, com ProgrammingError de owner-thread; sua correção LAB prova negação segura, não uma disponibilização definitiva nem a causa original de 10/10.

**CANDIDATO WRITE, 14/10, Draft #1281:** o job 115918042449, run #38583150088, no SHA d1fe42193026fa9c573381531215a221e3436bfd falhou em **2 dos 8 testes**. Nos dois cenários de injeção, o estado de Saga continuou PLANNED enquanto existiam 1 action_outbox e 1 action_decisions escritos. O job 115921385571, run #38584114098, SHA 07e95f6b1abd2acdf6e6c2331329b5e392ac3b65 teve **10/10 PASS**, após BEGIN IMMEDIATE externo e SAVEPOINT no Outbox. Os dois métodos de falha mantiveram seu **corpo AST idêntico** entre red e green. Importante: o arquivo completo de testes NÃO ficou byte-idêntico, porque ganhou os métodos 05 e 06. Não inflar a evidência afirmando "suíte imutável" no lugar de "duas asserções causais imutáveis".

A linha WRITE prova que a atomicidade do *staging local* foi corrigida nos casos observados. Não prova que uma mensagem foi enviada ao fornecedor nem que exista recibo causal, nem que o caso seja o P0 WRITE original.

## Mecanismo de auditoria do novo LAB
- Registro JSON com SHAs de commits e Git blobs, run/job IDs, contagens e nomes dos dois testes causais.
- 24 asserts reexecutáveis em runner GitHub com git show/git rev-parse somente para leitura dos objetos Git históricos; sem modificar arquivos de produto.
- Comparação AST dos testes 01/02 RED e GREEN para não confundir a adição legítima de 05/06 com alteração das asserções de falha.
- Preservação obrigatória do mapping UNMAPPED_EXACT_ORIGINAL_INCIDENT nos dois P0 e de 0/6 P0, Quality/Security RED.
- Workflow exclusivo Draft LAB Ubuntu + Windows herdando regressões anteriores da branch #1363.

## Saída real que ainda falta
1. Encontrar o primeiro documento que incluiu READ e WRITE entre os seis P0 (antes de 19/10); obter seu ID/stack/SHA/test e não apenas uma hipótese causal pelo nome.
2. Fazer o vínculo documental original->candidato->correção com revisão independente; a credencial externa, o H0 físico, o produtor/efeito e os outros quatro P0 não são inferíveis dessa evidência.
3. Reexecutar os exatos testes originais sem alterar expectativas por conveniência. Quality 6.562 / 52 FAIL + 34 ERROR, Security A53 RED, 32 Outbox/Saga OPEN_NOT_WAIVED continuam bloqueados.

**Sem merge, deploy, ativação, envio, fornecedor, contratação, criação de chave ou gasto.**
Referências diretas: https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1346 ; https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1195 ; https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1281 ; https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1363
