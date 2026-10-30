# A298 — Auditoria de dependências reais das seis P0 canônicas

**Data:** 30/10/2026 (America/Manaus). **HARD NO-GO, 0/6 homologadas,
ZERO_AUTO_RESEND.** Aba Negócios congelada; foco núcleo AION/Trader.
**Sem contratação, custo novo, merge, Worker, deploy ou operação real.**

## Fontes e limite de verificação

A nomenclatura canônica P0-1–P0-6 foi recuperada do histórico do projeto,
especialmente `AION_P0_AUDITORIA_RAPIDA_CLAUDE_2026-10-22.md`, e cruzada
com descrições **existentes** de PRs no repositório. Nesta etapa não houve
acesso ao arquivo de auditoria original montado em disco, inspeção de
todos os commits, execução da Quality/Security canônica nem entrevista com
provedor/custodiante independente. Não transformar PR verde em
homologação.

Âncoras: [#1464](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1464),
[#1504](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1504),
[#1624](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1624),
[#1625](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1625),
[#1693](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1693),
[#1694](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1694),
[#1743](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1743)–[#1748](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1748).

## Registro canônico: seis P0, nenhum GO

| P0 | Objetivo de homologação | Evidência LAB real e lacuna restante |
| --- | --- | --- |
| **P0-1 HUMAN_OWNER** | Identidade/autorização independente do proprietário, cadeia de aprovação, chaves controladas, revogação e replay | A295/#1746 mostra que um Boolean de aprovação pode mentir e dois signatários locais podem ser reiniciados; **sem consentimento real comprovado** |
| **P0-2 Recibos externos** | Recibos do emissor/provedor real, assinados e verificáveis, custodiante distinto, versão vigente e recuperação histórica | A243/#1694 e A294/#1745 só ensaiam assinaturas e testemunhas locais; emissor, custódia e efeito reais **não autenticados** |
| **P0-3 Primeira operação** | Reserva durável ANTES da primeira tentativa, idempotência semântica sob novos IDs, timeout/UNKNOWN sem reenvio automático | A174/#1464 reproduz reapresentação após apagar diário; G133/#1625 admite o mesmo efeito sob novo ID após rollback; #1693 é **guard de LAB injetável** |
| **P0-4 H0/recuperação** | Reinício seguro, high-water externo, não restaurar histórico antigo, incidentes reabertos, reconciliação quando ACK incerto | G132/#1624 reproduz rollback conjunto de banco e testemunha; A294/#1745 mostra reancoragem; A297/#1748 formaliza veto **local**, não custódia externa |
| **P0-5 SQLite lido** | Provar o handle/arquivo efetivamente aberto no VFS nativo, sidecars WAL/SHM, Linux/Windows, rejeitar substituição | G17/#1504 testou extensão C LAB; pathname/stat/data_version (#1696/#1744) não atestam FD/arquivo/histórico; **sem integração nativa auditada** |
| **P0-6 SQLite escrito** | Garantir transação, resultado de COMMIT, durabilidade WAL e recuperação sob concorrência, confirmação perdida e falha de energia | A292/#1743 testou seis writers e dois estados de ACK, mas auxiliares SQL e outro PID contornam marker; P0 nativa ainda **não demonstrada** |

**Importante:** A296 criou oito *subobrigações de pesquisa*. Elas NÃO
substituem esta classificação canônica das seis P0.

## Próximas entregas preparáveis a R$ 0

| Foco | Produção em LAB que podemos fazer agora | O que não podemos declarar fechado |
| --- | --- | --- |
| P0-1 | Contrato offline de matrícula/consentimento, revogação, anti-replay, cerimônia de recuperação; chaves fictícias | Identidade original HUMAN_OWNER real |
| P0-2 | Especificação por tipo de recibo do provedor, rotação e rejeição de emissor falso, fixtures sintéticas | Confirmação e custódia externas reais |
| P0-3 | Matriz concorrência, novo request-ID, semântica de evento, primeira reserva e ACK perdido, sempre sem SEND | Reserva externa imutável e efeito real idempotente |
| P0-4 | Testes cold restart, rollback simultâneo, incidente reaberto, ausência de high-water → negar | Testemunha externa durável e reconciliação autoritativa |
| P0-5 | Rever código e supply chain da extensão VFS G17/G18, teste native-file em ambiente isolado | Autorizar carregamento de binário não auditado ou integração |
| P0-6 | Testes WAL/SHM/COMMIT, falha energética simulada, múltiplos mutadores/handles | Durabilidade física, identidade nativa e efeito confirmado |

Nenhum item desta tabela exige **nova assinatura paga** para preparar
contratos ou testes sintéticos. A homologação real, porém, exige
independência que não pode ser autodeclarada pelo mesmo host.

## Dependências externas a resolver — sem contratar agora

1. **Proprietário:** decidir futuramente como comprovar pessoalmente
   autorização (chave/dispositivo/canal de verificação independente).
   Ainda não registrar credenciais nem substituir a vontade do usuário.
2. **Custodiante/high-water:** selecionar mecanismo realmente controlado
   fora do host local, resistente à restauração conjunta, e responsável
   pela disponibilidade e retomada de incidentes.
3. **Provedor/efeitos:** contrato e evidência de reserva/recibo e consulta
   do estado real; comportamento UNKNOWN nunca autoriza reenvio.
4. **Native SQLite:** comprovar e revisar em Windows/Linux a mesma conexão,
   FD/VFS, WAL/SHM e resultados de COMMIT, inclusive cadeia de fornecimento
   de extensões C; binário não revisado continua bloqueado.
5. **Homologação:** executar a Security/Quality canônica e revisão
   independente dos seis critérios. Os testes que demonstram falhas
   legítimas **não devem ser alterados para ficarem verdes**.

Dependência externa **não é automaticamente despesa**; algumas opções
podem usar recursos já controlados pelo proprietário. Qualquer nova
contratação, credencial, identidade real ou envio requer autorização
separada e posterior.

## Ordem recomendada

1. Conservar 0/6 e o HARD NO-GO como gates imutáveis.
2. Fechar **em laboratório** a definição do evento semântico da P0-3 e
   seu vínculo à operação, para saber exatamente o que deve ser
   reservado antes de enviar.
3. Preparar a cerimônia de confiança/recuperação de P0-1/2/4, sem fingir
   um custodiante externo.
4. Auditar G17/G18 e native WAL para P0-5/6 sem carregar extensão C
   em produção.
5. Só então obter evidência externa, repetir casos adversariais
   canônicos e deliberar sobre a primeira homologação de P0.

## Verificação da própria matriz

`labs/a298_six_p0_gap_register_lab.py` é um inventário estático,
versionado, com exportação JSON. Seus testes negam omissão de P0,
duplicação de evidência, aceitação automática de PR verde e qualquer
marcação indevida de P0 homologada. **Não implementa nem altera**
`SQLiteChatStore`, `ExecutionOutbox`, serviços ou mecanismos reais.

```bash
python -m unittest -v labs.test_a298_six_p0_gap_register_lab
```

**Resultado permitido:** GO-LAB para continuar pesquisa e auditoria.
**Resultado proibido:** GO de Worker, operação real, integração ou
declaração de fechamento das seis P0.
