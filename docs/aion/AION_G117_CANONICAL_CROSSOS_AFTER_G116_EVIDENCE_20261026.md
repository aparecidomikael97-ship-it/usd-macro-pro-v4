# AION G117 — verificação canônica Windows/Ubuntu após G116

**Data:** 26/10/2026. **PR Draft:** #1607, empilhada na G116 #1606. **Escopo:** workflow isolado de verificação, sem alteração de código operacional/testes originais/Worker/deploy. **0/6 P0 HOMOLOGADAS, HARD NO-GO.**

## Fonte e seletores reproduzíveis

Fonte G116 corrigida usada como base: `7ebd50fb57dda033647a1d5d49f55a37f7e47a85`. Commit G117 só de workflow: `8051e0e134d08d1b2b0f50c359501d12d390d4ba`.

O executor `scripts/run_a183_canonical_lab.py` extrai os seletores originais diretamente de `.github/workflows/quality-tests.yml` e `.github/workflows/aion-core-security-gate.yml`. O isolamento socket é o LAB já existente: **não** é firewall do SO e não se aplica automaticamente a subprocessos. Dependências conforme requirements e ferramentas de teste fixadas; não removemos testes, ignoramos achados nem flexibilizamos os critérios de segurança.

## GitHub Actions — seis jobs canônicos SUCCESS

[Execução G117 40374511757](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40374511757):

| SO | Quality original | Security unittest | Security pytest | Dependências e Bandit |
| --- | ---: | ---: | ---: | --- |
| Ubuntu | **6.449/6.449 PASS** (84,152 s) | **368/368 PASS** | **2.825/2.825 PASS** | **SUCCESS**, pip-audit: nenhum aviso conhecido |
| Windows | **6.449/6.449 PASS** (160,337 s) | **368/368 PASS** | **2.824 PASS + 1 SKIP histórico**, sem falhas | **SUCCESS**, pip-audit: nenhum aviso conhecido |

Jobs:
- Quality Ubuntu: `121753787578`
- Quality Windows: `121753787427`
- Security Ubuntu: `121753787287`
- Security Windows: `121753787244`
- Audit Ubuntu: `121753787074`
- Audit Windows: `121753787160`

`pip-audit` sem vulnerabilidades conhecidas refere-se às **versões instaladas e checadas nessa execução**, não a garantia eterna de inexistência de vulnerabilidades. Um teste historicamente ignorado no Windows não é contado como aprovado.

## G116 específica — prova RED anterior e GREEN objetiva

[RED G116 40373795092](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40373795092): objeto falsificado não assinava respostas, mas a interface G115 aceitava status/reserva em dicionários e autorizava um envio **simulado** sem gravar no custodiante. Dois FAIL de segurança no Windows e Ubuntu.

[GREEN G116 40374644732](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40374644732): Windows **24/24 PASS + 15/15 G114 PASS**; Ubuntu **24/24 PASS + 15/15 G114 PASS**. Dos 24 executados, **13 são métodos distintos**: 11 antigos G115 aparecem duas vezes devido à herança/importação dos testes, mais 2 novos G116. A correção restringiu a API LAB à classe exata de cliente G114, que verifica Ed25519 e challenge. Cenários de timeout/perda de ACK agora são injetados no transporte desse verificador.

## Não homologado / próximos requisitos externos

Este ciclo valida código e testes em laboratório, **não** muda a raiz de confiança:
- `G115_HOST_CONTROLLED_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0` continua uma demonstração de ataque funcional: restaurar o banco do próprio assinador reabre o evento.
- O código Python/callback é alterável por administrador privilegiado, e a verificação de tipo sozinha não é isolamento criptográfico.
- O evento original e a chave pública confiável ainda são provisionados por fixture controlada pelo host, sem assinatura de origem independente.
- A proteção do VFS nativo, antirollback same-inode, autorização real do proprietário, confirmação externa de primeiro SEND e H0 após reinício ainda não foram homologadas.
- As cinco exigências externas A184 históricas **não foram reexecutadas nesta PR**, e continuam não atendidas por falta das evidências de uma autoridade externa real.

**Decisão de segurança: 0/6 P0 HOMOLOGADAS; HARD NO-GO. Sem merge, deploy, Worker, envio real, dinheiro ou infraestrutura externa contratada.**
