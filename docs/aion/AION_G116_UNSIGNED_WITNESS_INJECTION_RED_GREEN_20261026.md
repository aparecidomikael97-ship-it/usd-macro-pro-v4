# AION G116 — Rejeitar clientes simulados sem prova criptográfica na admissão Outbox

**Data:** 26/10/2026. **PR Draft:** #1606, empilhada sobre G115 #1605. **Status:** LAB, sem merge, deploy, Worker, fornecedor ou SEND real. **0/6 P0 HOMOLOGADAS; HARD NO-GO.**

## Falha reproduzida ANTES de corrigir

A G115 aceitava qualquer objeto com os métodos `status()` e `reserve()` como sendo uma fonte autenticada. Esse objeto devolvia apenas dicionários de campos; o guard não exigia que tivessem sido verificados criptograficamente pelo cliente G114.

O teste adversarial `UnsignedForgedWitness` devolveu uma sequência `ENROLLED -> RESERVED -> RESERVED` perfeitamente formatada, sem assinatura Ed25519 ou gravação no SQLite do custodiante.

**RED real:** [GitHub Actions 40373795092](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40373795092), **Windows e Ubuntu: dois FAIL por sistema**. O teste de construtor demonstrou que o objeto não autenticado era aceito, e o teste integrado Outbox passou à condição `CONFIRMED` e chamou o adaptador **falso de memória** com histórico do custodiante real ainda em zero. Não houve chamada de rede nem fornecedor real.

## Correção restrita ao LAB

- `labs/a190/g115_public_witness_outbox_guard_lab.py`: exige especificamente a classe experimental `G114PublicKeyWitnessClientLab` na interface do guard, que implementa verificação Ed25519 e de desafio antes de devolver status/reservas. Objetos duck-typed de retorno arbitrário falham com `G116_AUTHENTICATED_CLIENT_REQUIRED`.
- `labs/a190/test_g115_cross_process_outbox_guard_lab.py`: injeções de perda de ACK, troca de chave após COMMIT e indisponibilidade foram movidas para a função de **transporte** do cliente G114 real, em vez de substituí-lo por classes sem verificação de assinatura.
- `labs/a190/test_g116_unsigned_witness_client_injection_lab.py`: dois testes adversariais adicionais, mais 11 contratos herdados G115. Descoberta `unittest` executa G115 também como classe base importada, resultando em **24 execuções por SO (13 métodos únicos, 11 duplicados)**.
- Primeira execução após a correção demonstrou `Ran 24 tests; OK` em ambos os SO, mas o próprio workflow procurava `Ran 13 tests` e ficou vermelho só pela conferência textual. Corrigimos o grep, sem mudar os testes ou a implementação.

**GREEN final:** [G116 run 40374644732](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40374644732) — **Windows 24/24 PASS + 15/15 G114 PASS; Ubuntu 24/24 PASS + 15/15 G114 PASS**. Duas verificações explicitamente presentes: `G116_UNSIGNED_CLIENT_CONSTRUCTOR=DENIED`, `G116_UNSIGNED_BARE_RESPONSES=NO_ADAPTER_SEND`. A barreira histórica de lost ACK continua `G115_LOST_REMOTE_ACK=NO_PROVIDER_SEND_SPENT`.

## Limitações que impedem homologação

A checagem `type(witness_client) is G114PublicKeyWitnessClientLab` é uma proteção **da API opcional LAB**, não uma fronteira de confiança resistente a um administrador do host. Código privilegiado pode fazer monkeypatch, alterar o callback do Outbox, substituir o pin/configuração ou restaurar a assinatura e o SQLite locais.

O teste `G115_HOST_CONTROLLED_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0` continua passando precisamente porque demonstra que a restauração do banco do próprio custodiante REABRE a mesma operação. Não existe cadastro original de autoridade externa, histórico monotônico independente, raiz de chave protegida, VFS SQLite nativo autenticado, escrita antirollback ou gateway de primeira operação externa.

A G117 #1607 verifica separadamente as suítes canônicas originais sobre o código cumulativo corrigido, sem alterar seletores, ignorar falhas ou tratar testes locais como licença para produção.

**0/6 P0 homologadas; HARD NO-GO; sem merge/deploy/Worker/SEND real/fundos.**
