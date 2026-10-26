# AION G121 — regressões canônicas completas após G120

**Data:** 26/10/2026. **PR:** #1611 Draft, base G120 #1610. **Somente workflow de validação; nenhum código de produção alterado.**

## Teste exato do código cumulativo

- G120 código corrigido SHA **`3aadc19e2378d06d9ee9566f9b07987aa6d41dc8`**.
- G121 commit somente de workflow SHA **`edc2fec3071da0448981b1a09c0d1e6a4fbe959f`**.
- [GitHub Actions G121 40393026754](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40393026754): **6/6 jobs SUCCESS** no Windows e Ubuntu.

| Bateria original | Ubuntu | Windows |
| --- | --- | --- |
| Quality canônica | **6449/6449 PASS** (82,954 s), job 121818689594 | **6449/6449 PASS** (153,072 s), job 121818689103 |
| Security unittest canônica | **368/368 PASS**, job 121818689330 | **368/368 PASS**, job 121818689318 |
| Security pytest original | **2825 PASS**, sem skip, job 121818689330 | **2824 PASS + 1 SKIP histórico**, sem fail, job 121818689318 |
| pip-audit e Bandit | **SUCCESS**, sem vulnerabilidades conhecidas, job 121818689396 | **SUCCESS**, sem vulnerabilidades conhecidas, job 121818688940 |

O executor `scripts/run_a183_canonical_lab.py` extrai os mesmos seletores históricos originais, sem omitir/alterar testes. A proteção de rede do LAB usa socket guard Python, NÃO firewall de SO. Uma auditoria de dependências sem alertas conhecidos nesta data não impede que novas vulnerabilidades sejam descobertas posteriormente.

## Contexto G120 e limites

[RED G120 40391558626](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40391558626): Windows/Ubuntu reproduziram uma segunda inscrição de `event_id` para a mesma decisão original sem prova independente, produzindo `CONFIRMED` e uma chamada ao adaptador falso. [GREEN G120 40392570322](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40392570322): 30/30 G120 + 34/34 G118 + 24/24 G116 em AMBOS os sistemas, após tornar obrigatória uma assinatura distinta de aprovação da identidade original no contrato LAB.

**Teste negativo G120_HOST_CONTROLLED_OWNER_REPIN=STILL_VULNERABLE_NOT_P0:** ao substituir o pin público e o assinador de suposta aprovação juntos, um operador do mesmo host ainda cria outra identidade original com assinatura aparentemente válida e consegue usar o adaptador falso. Os históricos e a chave continuam host-owned.

A aprovação sintética NÃO estabelece HUMAN_OWNER real nem uma autoridade independente. Os cinco requisitos externos A184 — custódia monotônica, identidade original autenticada, raiz externa, SQLite VFS nativo e escrita antirollback — continuam pendentes. G122 Draft #1612 executa os testes reais external-red separadamente, sem masking.

**0/6 P0 HOMOLOGADAS · HARD NO-GO · LAB/DRAFT ONLY · NO MERGE/DEPLOY/WORKER/REAL SEND/FUNDS.**
