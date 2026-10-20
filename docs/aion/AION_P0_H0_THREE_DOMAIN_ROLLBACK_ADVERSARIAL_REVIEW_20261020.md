# AION P0 H0 — três domínios de histórico e rollback simultâneo (LAB, NÃO é custódia real)

**Data:** 20/10/2026. **Veredito inicial:** HARD NO-GO, 0/6 P0 homologados, Worker OFF, ZERO_AUTO_RESEND.  
**Escopo:** reproduzir *falhas observáveis* de rollback com três arquivos SQLite **todos locais, temporários e deliberadamente NÃO confiáveis**. Não há Cloudflare, S3, WORM, conta externa, credenciais, assinatura nem envio.

## Descoberta e diferença em relação ao LAB anterior

Já existe `atlasquant_aion_p0_h0_custody_two_domain_model_lab.py`, que demonstra CAS local/fixture, uma única reserva e rollback de executor/custodiador. Já existe também o estudo `docs/aion/AION_P0_H0_THIRD_ANCHOR_S3_COMPLIANCE_OBJECT_VERSION_REVIEW_NO_GO_20261019.md`, que propõe S3 Object Lock **COMPLIANCE + version ID exato** em conta administrativa distinta e observa que um nome de objeto/"latest" não é prova do head mais recente.

**Este ensaio acrescenta testes de causalidade aos dois estudos existentes**, sem reinventar código de produto:

- **Domínio A:** cursor de sequência de executor (SQLite local fictício).
- **Domínio B:** custodiador CAS de intenção e epoch (modelo SQLite local existente, não Cloudflare).
- **Domínio C:** histórico versionado de âncora (SQLite local fictício, não S3, sem retenção WORM ou autenticação).
- Caso de produto complementar: execução real de `ExecutionOutbox.enqueue` em duas bases SQLite locais diferentes para demonstrar que perder a anterior e recriar a mesma intenção produz `PENDING`, mesmo quando a intenção anterior ficou `UNCERTAIN`.

| Cenário | Leitura entre três fixtures | Segurança / conclusão |
| --- | --- | --- |
| Heads A/B/C coincidem | `THREE_LOCAL_FIXTURE_HEADS_MATCH_NOT_AUTHENTICATED` | **BLOCKED**: comparação não autentica custodiante, chave/assinatura ou último head |
| Rollback só A | A atrás de B/C | **BLOCKED**: rollback do executor identificável se B/C sobreviverem |
| Rollback só B | B atrás de A/C | **BLOCKED**: PITR do custodiador identificável se A/C sobreviverem |
| Rollback simultâneo A+B, C preservado | A=0, B=0, C=1 | **BLOCKED**: âncora *fictícia* sobrevivente revela regressão, mas NÃO fornece prova autêntica |
| Rollback A+B+C, inclusive referência externa perdida | A=0, B=0, C=0 | **BLOCKED**: consistência forjada indistinguível sem quarta proteção/retensão real |
| Versão lógica `v2` adicionada e `v1` ainda fixada | Referência `v1` está stale | **BLOCKED**: nome/versão fixada sozinho não certifica atualidade; exigir readback autenticado do head |
| Mesmo seq e digest divergente ou epoch distinto | Fork detectável | **BLOCKED**: ledger não é identidade do emissor |
| Âncora indisponível/corrompida ou escopo estrangeiro | Ausência de prova | **BLOCKED**: nunca criar automaticamente substituto "limpo" |
| Campo externo `verified=true` hostil | Ignorado sem introspecção | **BLOCKED**: autoatestado não é autenticação |
| Banco AION real perdido/recriado | Mesmo key determinístico volta `PENDING` | **LACUNA ABERTA**: sem histórico independente não há prova de não envio |

## O que isso NÃO resolve

**Uma terceira base de dados local NÃO é terceira custódia.** Todos os três fixtures ficam sob o mesmo sistema de arquivos, root e administrador. Um atacante ou restauração que alcance as três consegue esconder regressões. A retenção S3 COMPLIANCE de versão sob conta independente é uma *candidata à preservação*, não um atestado de atualidade, assinatura, anti-PITR distribuído ou efeito concluído.

Em uma arquitetura futura, separar estas quatro perguntas:

1. Quem é o custodiante e como o AION autentica a chave/conta/issuer de forma independente e revogável?
2. Qual a intenção exata — digest, escopo/tenant, idempotência, nonce, lease, epoch — reservada atômica e duravelmente **antes do primeiro efeito**, e como se evita race/reativação?
3. Qual a versão imutável de log publicada em *outra conta administrativa*, com política COMPLIANCE/version ID/retention válida, e como ler **HEAD atual autêntico** mesmo depois de delete-marker, nova versão, PITR, timeout e cadeia-fork?
4. **A matrícula/âncora não comprova o efeito externo.** Onde está o recibo independente `COMMITTED_EFFECT` ou `NO_EFFECT_FENCED` do produtor, incluindo garantia contra envio tardio? Até existir, manter `UNCERTAIN`, FIFO congelado e **ZERO_AUTO_RESEND**.

O custo, IAM, MFA e isolamento também continuam não validados. **Não é autorizado provisionar Cloudflare DO, AWS S3 Object Lock ou qualquer produto pago**, nem reter dados pessoais no laboratório, sem um projeto de FinOps, LGPD e aprovação independente.

## Evidências da rodada

- `tests/test_aion_p0_h0_three_domain_rollback_scenarios_lab.py`: 17 testes offline, 16 condições de três domínios e 1 caso de `ExecutionOutbox` real com SQLite perdido.
- [PR Draft #1340](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1340): baseline de testes da janela OneSignal 30 dias, dados SQLite persistidos e diagnóstico de histórico perdido.
- [Issue #1329](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1329): 32 ERROR históricos `OPEN_NOT_WAIVED`, produtores/recibos/fence externos não inscritos.
- Código de Outbox/Saga/Worker e Quality canônica continuam intactos. Não foi executada integração real, Quality completa, Security 365 ou homologação H0.

**Próximo gate:** revisão de arquitetura por terceiro e **prova real de custódia IAM/append+readback+retention** sob aprovação separada, e só depois avaliar ligação fail-closed ao boot e ao primeiro efeito. Mesmo com uma âncora autêntica, enviar/repetir mensagens permanece NO-GO sem recibos do produtor.

**HARD NO-GO — Worker OFF — ZERO_AUTO_RESEND — 0/6 P0 homologados.**
