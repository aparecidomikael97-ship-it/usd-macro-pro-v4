# AION G122 — auditoria externa real intencionalmente RED após G120

**Data:** 26/10/2026. **PR:** #1612 Draft, empilhada sobre G121/G120. **0/6 P0 HOMOLOGADAS · HARD NO-GO.** Workflow apenas, sem alterações de código, testes originais, Worker, deploy ou envio real.

## O que foi executado

[GitHub Actions G122 40393928709](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40393928709), ambos os sistemas:

```shell
python -B -m unittest -v lab_a183_external_requirements_red
```

- Ubuntu job **121821832964** — **5/5 FAIL**, `Ran 5 tests in 0.063s; FAILED (failures=5)`; GitHub job FAILURE, exit code 1.
- Windows job **121821833434** — **5/5 FAIL**, `Ran 5 tests in 0.662s; FAILED (failures=5)`; GitHub job FAILURE, exit code 1.
- Nenhum `skip`, `xfail`, `continue-on-error`, filtro de seletor, ajuste de assertiva, trap de exit code ou status inventado. A PR ficou vermelha porque os **requisitos continuam realmente não atendidos**.

## Exatamente cinco requisitos, e o que os testes demonstraram

| # | Critério de aceitação real | Falha objetiva atual |
|---|---|---|
| 1 | Custódia/contador e checkpoint externamente monotônicos | Apagar e reinicializar custódia local e contador permite reservar de novo o mesmo efeito |
| 2 | Inscrição original do evento de negócio autenticada, imutável fora do solicitante | Substituir identidade original por configuração local continua sendo aceito em caminho legado A182 |
| 3 | Raiz pública confiável e pinada por autoridade independente | Substituir assinador E fingerprint/pin correspondente não produz a exceção obrigatória |
| 4 | Versão nativa, VFS e snapshot do MESMO handle SQLite em leitura | Restaurar os bytes antigos no mesmo inode com handle vivo NÃO lança `StorageUnavailableError` |
| 5 | Escrita nativa do SQLite bloqueada após restauração dos bytes no mesmo inode | O writer ainda NÃO lança o `StorageUnavailableError` obrigatório |

Os casos estão nas suítes pré-existentes `lab_a182_external_requirements_red.py` e `lab_a183_external_requirements_red.py`, sem alterações na G122. São critérios de aceitação estrutural, e não simples regressões G120: verificam o que o núcleo **ainda não pode garantir em produção**.

## Comparação justa com a G120/G121

- [G120 RED pré-correção 40391558626](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40391558626): 23 execuções, 1 FAIL por SO por segunda inscrição inventada para a mesma decisão original. Um **adaptador simulado** recebeu chamada, sem efeito real.
- [G120 GREEN 40392570322](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40392570322): Windows e Ubuntu 30/30 G120, 34/34 G118, 24/24 G116 PASS. Exige segundo comprovante de inscrição Ed25519, distinto do assinador do custodiante, válido e fiel à decisão original.
- [G121 canônico 40393026754](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40393026754): 6 jobs SUCCESS; Quality 6449 PASS em ambos OS, Security unittest 368 PASS, pytest 2825 Ubuntu / 2824+1 skip Windows, auditoria de dependências e Bandit SUCCESS.
- Controle negativo **G120_HOST_CONTROLLED_OWNER_REPIN=STILL_VULNERABLE_NOT_P0** permanece PASS porque DEMONSTRA o ataque: um operador host-controlled substitui assinatura e pin da suposta autoridade original juntos e cria outro evento. Isso nunca equivale a identidade HUMAN_OWNER real.

## Próxima fronteira objetiva

Os próximos commits em LAB podem preparar interface e ensaios de um custodiante sob administração realmente separada, com fonte original identificada e credencial protegida fora do host. Fechamento só será possível com:
1. Escolha/autorização do custodiante e provedor de chave real, respeitando limite de custos e LGPD.
2. Provisionamento independente da chave-raiz, identidade e primeira inscrição imutável do evento de negócio.
3. Prova de contador monotônico fora do host após rollback/reboot completo e resposta incerta.
4. Integração de leitura/escrita SQLite na fronteira nativa do handle/VFS, com testes de mesma instância/mesmo inode.
5. Auditoria de end-to-end primeiro SEND com reconciliador do fornecedor, verificador independente e autorização humana formal antes de qualquer GO.

**Não foram contratados serviços, provisionados segredos ou gerados custos externos. NADA DE MERGE/DEPLOY/WORKER/PROVIDER SEND REAL/FUNDOS.**
