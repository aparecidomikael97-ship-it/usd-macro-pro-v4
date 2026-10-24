# A190 G2 — evidências de custódia local sob principais OS distintos

Missão #1486 · Draft PR #1489 empilhada sobre #1488 · LAB exclusivamente sintético.

## Resultado conferido

- **SHA exato de código e workflow executado:** aa4b3822158e2c2c7a1f69df027691c34b046e45.
- **CI final:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40044288118 — **2/2 jobs SUCCESS** (Ubuntu e Windows). Os dois jobs exercem o mesmo cenário e mantêm o controle negativo privilegiado.
- **CI anterior também conferido:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40044221071 — **2/2 jobs SUCCESS**, com logs Windows que identificam as duas contas por SID e registram as duas negações de escrita, a divergência e a readmissão insegura.
- **Primeira execução limitada:** https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40044092194 — **Ubuntu SUCCESS** antes da adição da matriz Windows. Não houve falha de requisito G2 ocultada. O último commit alterou apenas o nome do workflow para refletir os dois SOs; CI final reexecutado.
- Este relatório documental foi adicionado depois do SHA testado e não modifica código nem seletores canônicos.

## Sequência verificada

1. Aplicativo sintético como principal OS A grava no SQLite a sequência 1 e faz snapshot local.
2. Custodiante sintético como principal OS B publica piso/hash correspondente em JSON local de diretório controlado por B.
3. A avança SQLite à sequência 2, e B publica piso 2. Ambos os dados locais correspondem antes do ataque.
4. A restaura seu SQLite antigo (seq1) e tenta alterar o piso protegido por B: escrita no arquivo e criação de substituto no diretório são **OS_DENIED**. A comparação DB seq1 contra piso seq2 produz **DENIED**.
5. Um administrador/root do mesmo runner **consegue restaurar também a cópia antiga do piso**; o verificador aceita novamente seq1. Este é o contraexemplo de segurança obrigatório.

| Controle | Ubuntu runner | Windows runner |
| --- | --- | --- |
| Identidades OS distintas | UID custodiante 999, app 997 | SIDs de contas locais distintas |
| Estado seq1→seq2 | exercido e confirmado | exercido e confirmado |
| Editar piso direto como app | negado | negado |
| Criar substituto no diretório do piso como app | negado | negado |
| Readmissão de banco antigo com piso atual | negada | negada |
| Restaurar ambos com privilégio administrativo | **readmissão insegura reproduzida** | **readmissão insegura reproduzida** |

Testes Linux e Windows realizam operações em arquivos SQLite/JSON isolados de runner efêmero, sem dados de usuários, conta de produção ou credenciais reais do AtlasQuant. O Windows usa contas temporárias por SID e execução de processos com credenciais locais efêmeras; as permissões do diretório protegem o piso contra a conta app, mas não contra Administrators/SYSTEM.

## Delimitação da conclusão

**Consegue provar no LAB:** separação de usuários do mesmo OS é uma defesa de menor privilégio que detecta rollback do DB quando o piso protegido continua intacto. O resultado não depende de apenas duas assinaturas ou dois hashes declarados pelo mesmo aplicativo: a negativa da ACL foi de fato exercida sob outro usuário.

**NÃO consegue provar:**

- Resistência contra admin/root, snapshot integral de host, restauração conjunta de disco, extração de chaves acessíveis no host ou manipulação da conta custodiadora.
- Autoridade monotônica em outro host/serviço com identidade, raiz, challenge, revogação e anti-reenrollment independentes. O piso é JSON **local**.
- A origem do hash/seq, que ainda é comunicada pelo próprio aplicativo sem autenticação externa: uma conta maliciosa pode mentir **antes** da publicação.
- WAL/SHM, VFS live, cache de statement, mesmo-inode ABA, energia, H0 após restart físico ou primeira operação de um fornecedor real.
- Idempotência semântica, autenticidade do evento original, recibo externo ou decisão HUMAN_OWNER.

Este workflow **não executa a Quality/Security canônica**. Permanecem os cinco requisitos external-RED por SO e as 43 vulnerabilidades herdadas dos relatórios da pilha A184–A189; sem promoção automática de um teste verde a homologação.

**Veredito:** G2-LOCAL-PRINCIPAL_LAB=PARCIAL; G2-CUSTODIA_INDEPENDENTE=RED; G3-EFEITO/RECIBO=RED; **0/6 P0; HARD NO-GO; UNCERTAIN; ZERO_AUTO_RESEND**. Sem merge, main, deploy, Worker, provedor externo, credencial real ou novo custo.

Próximo gate exige custódia de fato independente e acordo de idempotência/recibo de fornecedor; não provisionar serviços ou chaves sem decisão expressa do proprietário, respeitando teto mensal definido.
