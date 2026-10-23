# A190 G0/G1 — Evidência verificada de LAB em Ubuntu e Windows

Data 2026-10-23; missão #1486; PR Draft #1488 sobre preflight #1487.

## Estado da evidência

- **SHA exato de código/testes/workflow verificado pelo CI:** cefd6f419af7c702fc39ecb27688dd2f02cdce43.
- **Run verificado:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40042023892
- **Resultado:** quatro jobs **SUCCESS**: G0 Ubuntu, G0 Windows, G1 Ubuntu UID e G1 Windows SID. Inspecionados job summaries e logs de G1. Sem alteração em módulos operacionais ou arquivo de credenciais.
- **Tentativa inicial mantida para rastreio:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40041894887 — G0 passou nos dois SOs e G1 Windows passou, mas G1 Linux falhou **antes do probe** por não conseguir importar o script dentro do checkout como UID restrito. Corrigido copiando script de teste para /tmp público com permissões de leitura, sem alterar ACL do banco, asserts ou critério de aceitação.
- Este commit documental posterior não altera o código/testes/workflow já testados. Não converter documentação em declaração de novo CI.

## Resultados e o que provam

| Ensaio | Ubuntu | Windows | Interpretação correta |
| --- | --- | --- | --- |
| G0 apagar ambos SQLite+witness e recriar genesis | 3/3 testes PASS | 3/3 testes PASS | **RED de segurança reproduzido:** a mesma reserva reaparece como nova no lab |
| G0 apagar somente witness | DENIED | DENIED | detecção local se outro arquivo ainda sobrevive |
| G0 apagar somente DB | DENIED | DENIED | detecção local se outro arquivo ainda sobrevive |
| G1 leitura/gravação legítima por dono separado | euid 999, PASS | SID distinto terminando 1003, PASS | o principal proprietário consegue exercer SQLite |
| G1 leitura raw por conta app | euid 997, PermissionError | SID distinto terminando 1004, PermissionError | OS impediu leitura sob esse principal |
| G1 SELECT direto | OperationalError / OS_DENIED | OperationalError / OS_DENIED | conexão/query não alcança banco protegido |
| G1 INSERT direto | OperationalError / OS_DENIED | OperationalError / OS_DENIED | inserção negada sob usuário não autorizado |
| G1 renomear arquivo do banco | PermissionError | PermissionError | acesso de modificação do path negado |

G1 usa dois usuários reais criados apenas no runner efêmero, identificados nos logs por euid/SID. As quatro negações **só contam porque a operação equivalente de leitura/escrita foi exercida e teve sucesso pela conta proprietária**. Não interpretar OS_DENIED como verificação de inode/VFS/sidecar/WAL, que não foi coberta.

## Lacunas sem relaxamento

1. Usuário root/administrador do mesmo host pode contornar ACL ou restaurar todo armazenamento local. Este caso **não foi mitigado**.
2. Integridade de SQLite LIVE em todas as conexões, cache/statement, WAL/SHM, rename-out/ABA e same-inode overwrite não foi atestada.
3. Custódia monotônica em principal/host independente não foi demonstrada.
4. Evento original autenticado, recibos de provedor, identidade HUMAN_OWNER, perda real de ACK/efeito e recuperação física H0 não foram homologados.
5. Quality/Security canônicas **não foram reexecutadas por este workflow**. No baseline A189 continuam os cinco external-RED por SO e 43 advisories herdados; não se declara remoção de testes ou limpeza de dependências.
6. O controle G0 é um teste que **passa ao demonstrar vulnerabilidade**. Não reinterpretar teste verde como gate P0 verde.

**Veredito:** conclusão do ensaio estreito G0/G1-LAB. 0/6 P0; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND. Nenhum merge, deploy, Worker, operação real, API paga, contratação, credencial de cliente ou custo adicional autorizado. Próximo gate é G2 rollback conjunto comparado a custódia independente, e G3 evento/recibo externo, condicionados à decisão humana da arquitetura.
