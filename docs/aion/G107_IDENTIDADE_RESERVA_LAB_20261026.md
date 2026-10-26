# G107: identidade da reserva com contador igual (LAB)

RED anterior: Windows e Ubuntu, 24 testes executados, 3 falhas em cada sistema. Execução 40357571529.

Falhas: substituição do SQLite por outro com mesmo contador contendo (1) efeito diferente, (2) outro identificador técnico, ou (3) digest da decisão adulterado. G106 aceitava o contador sem conferir novamente o registro.

GREEN: execução 40358058284. Windows 24/24 e Ubuntu 24/24. A G107 exige leitura local final do registro e igualdade de efeito, decisão, idempotência, escopo e sequência com o recibo A180 validado.

G107 é um contrato de laboratório: o banco, as chaves e o atestador continuam sintéticos. A leitura não garante imutabilidade posterior nem autoridade independente.

Seis P0: 0/6 homologadas. HARD NO-GO. Sem merge, deploy, Worker, envio real ou dinheiro.
