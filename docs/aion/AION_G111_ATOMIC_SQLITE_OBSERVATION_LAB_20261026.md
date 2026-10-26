# AION G111 — observação coerente de reserva SQLite (LAB)

Data: 2026-10-26. PR Draft #1601, empilhada sobre G109 #1599. Código validado: 05b765f7c2475a27164ffee94af0356bfe20dda1. Sem merge nem deploy.

## RED primeiro

G107/G109 consultavam o contador do SQLite e, depois, em uma conexão distinta, o registro original da reserva. Um segundo registro podia ser gravado entre essas duas consultas, mantendo a reserva original intacta. A leitura do contador (1) e do registro original eram individualmente corretas, mas o estado real já havia avançado para 2 sem que o atestador sintético tivesse acompanhado.

[Execução RED 40361690643](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40361690643): Windows e Ubuntu, 50 testes executados em cada um, dois FAIL e um ERROR. Um teste demonstrou admissão indevida de segunda reserva não atestada; os outros dois exigiram uma nova interface que ainda não existia. Os 50 incluem regressões e testes herdados repetidos, não 50 contratos únicos.

## Correção limitada ao LAB

Novo helper `labs/a190/g111_atomic_reservation_observation.py` executa BEGIN, SELECT de high-water, SELECT de count e SELECT do registro da tentativa antes do ROLLBACK, tudo na mesma conexão SQLite, fechada explicitamente. Uma leitura transacional dá uma visão consistente entre as consultas, sem modificar o banco.

O verificador opt-in `aion_chat/pinned_external_enrollment_g102_lab.py` exige agora um callback de observação coerente e confere o snapshot final e todos os sete campos de identidade da reserva contra o recibo A180 validado. Falhas, dados divergentes e ausência do callback negam a admissão. Os controles anteriores G102/G104/G106/G107/G109 permanecem.

[Execução GREEN 40362029654](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40362029654): Windows 50/50 PASS, Ubuntu 50/50 PASS; sem skips dos novos testes. [Regressão G109 na mesma versão 40362029655](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40362029655): ambos os sistemas PASS.

## Auditoria canônica

[A184 40362029628](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40362029628): Ubuntu Quality 6449/6449 PASS, Security unittest 368/368 PASS, pytest 2825/2825 PASS, auditoria de dependências sem vulnerabilidades conhecidas. Exatamente cinco requisitos de evidência externa continuam RED em Windows e Ubuntu. Nenhuma dispensa ou alteração dos testes de aceitação.

## Limitações e governança

A transação coerente é um controle local, não uma autoridade externa. Um operador privilegiado ainda pode trocar arquivo/chave/callback ou alterar o estado depois da leitura. Não há prova de VFS nativo vivo, custódia monotônica independente, identidade original imutável, escrita antirollback, primeiro SEND do fornecedor ou recuperação H0 homologada. O procedimento G112 Draft #1602 valida a Quality/Security completa do Windows após esta mudança; o resultado deve ser verificado separadamente.

**0/6 P0 HOMOLOGADAS. HARD NO-GO. Sem merge, deploy, Worker, envio real ou fundos.**
