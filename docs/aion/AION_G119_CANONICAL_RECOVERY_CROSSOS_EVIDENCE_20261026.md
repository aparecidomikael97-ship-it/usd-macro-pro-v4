# AION G119 — Verificação canônica Windows e Ubuntu após recuperação G118

**Data:** 2026-10-26. **PR Draft:** #1609, base G118 #1608. Somente workflow de verificação; sem modificação em código original de produção, WorkER, dependências fixadas ou seletores históricos. **0/6 P0 HOMOLOGADAS — HARD NO-GO.**

## Contrato G118 submetido às regressões

O código G118 fornece um observador de recibo de reserva assinado por custodiante **sintético no mesmo host**. Mesmo `RESERVED` não comprova execução pelo fornecedor e não deve virar confirmação, reenvio ou autorização de SEND; `NOT_FOUND` e `ENROLLED` não atestam ausência de uma operação antiga após rollback. O objeto retornado não oferece operações de escrita/reserva/envio.

G118 [execução 40378021974](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40378021974): **Windows 34/34 + 24/24 G116 + 15/15 G114** e **Ubuntu 34/34 + 24/24 G116 + 15/15 G114**, todos PASS. Os 34 da primeira bateria incluem testes herdados descobertos duas vezes: 23 métodos distintos, não 34 propriedades únicas. Os testes de ACK perdido e reinício preservaram `UNCERTAIN`, evento reservado no testemunho, efeito de fornecedor `UNKNOWN` e zero envios simulados. A recuperação nunca autoriza reenvio.

## Resultado canônico original G119 — seis jobs SUCCESS

[GitHub Actions 40378236812](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40378236812). Código cumulativo testado: G118 fonte/workflow SHA `89242ad1eaed6a4609bf5e15f0224614fdb1b7e3` + G119 workflow-only SHA `64a8279dc5c3f06cb1a5d9a9849d63edea347c75`.

| Sistema | Quality original | Security unittest | Security pytest | Audit / Bandit |
| --- | ---: | ---: | ---: | --- |
| Ubuntu | **6449/6449 PASS** (75.960s) | **368/368 PASS** | **2825/2825 PASS** | **SUCCESS**, pip-audit sem vulnerabilidades conhecidas |
| Windows | **6449/6449 PASS** (165.327s) | **368/368 PASS** | **2824 PASS + 1 SKIP histórico**, zero FAIL | **SUCCESS**, pip-audit sem vulnerabilidades conhecidas |

Referências dos seis jobs:
- Quality Windows `121767100893`; Quality Ubuntu `121767101079`.
- Security Windows `121767100978`; Security Ubuntu `121767100448`.
- Audit Windows `121767100912`; Audit Ubuntu `121767100687`.

O executor `scripts/run_a183_canonical_lab.py` extrai os seletores canônicos existentes, sem alterar critérios ou dispensar suites. O skip de plataforma Windows não equivale a teste aprovado. O isolamento de socket de testes permanece apenas controle Python no LAB, não um firewall OS, e não se aplica automaticamente a subprocessos.

## Limites P0 não superados

Cinco exigências históricas A184 de evidência realmente externa ainda NÃO foram atendidas — foram anteriormente testadas como RED e **não foram reexecutadas nesta PR**:

1. Custodiante monotônico fora do domínio administrativo do host, durável contra restore/rebootstrap;
2. Autenticação independente do evento original e aprovação do proprietário;
3. Raiz/pin de confiança provisionados fora do controle do cliente/host;
4. Prova de versão e identidade VFS/handle SQLite nativos da instância viva;
5. Bloqueio antirollback de escrita do mesmo inode/versão, aplicado na admissão nativa.

O protocolo LAB aceita assinatura de um componente com keyfile SQLite no MESMO computador. O teste de ataque `G115_HOST_CONTROLLED_WITNESS_ROLLBACK=STILL_VULNERABLE_NOT_P0` continua mostrando que é possível restaurar o arquivo do próprio custodiante e voltar a gastar o mesmo evento. A G118 bloqueia SEND mesmo depois de observar uma reserva, mas não tem acesso a fonte externa de confirmação do fornecedor nem prova verdadeira de ausência. Portanto, nenhum GO foi declarado.

**0/6 P0 HOMOLOGADAS · HARD NO-GO · NO MERGE/DEPLOY/WORKER/REAL SEND/FUNDS.**
