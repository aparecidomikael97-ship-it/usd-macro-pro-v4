# AION — Auditoria de fonte canônica: seis P0 abertos, Quality RED e M71 RED

**19/10/2026 — SOMENTE LAB.** Não há merge, deploy, ativação do Worker, execução externa, contratação ou gasto adicional. Veredito inalterado: **0/6 P0 homologados; HARD NO-GO; ZERO_AUTO_RESEND.**

## Fonte da verdade em vez de contadores de mini-suítes

O arquivo machine-readable `docs/aion/AION_P0_SIX_BLOCKERS_CANONICAL_EVIDENCE_REGISTER_20261019.json` contém **seis** requisitos ainda abertos e distingue a lacuna transversal M71 do conjunto dos seis. O registro foi extraído de documentos e código realmente lidos, com links GitHub e condições de prova, mas **não substitui um sistema oficial de issues ou uma verificação de identidade externa**. Alguns códigos de rastreio originais não apareceram nas fontes auditadas; não inventá-los. A coluna `canonical_tracker_id: null` sinaliza essa pendência.

| P0 / apelido de trabalho | A evidência LAB já demonstrou | Falta para GO e fechamento |
|---|---|---|
| **1 — Identidade real HUMAN_OWNER** | Verificação matemática WebAuthn ES256 com credenciais inventadas e chaves temporárias, CI #39308275545 | Matrícula e custódia reais independentes, prova do proprietário, origem/credencial real, challenge durável, perda/revogação e ação crítica autorizada |
| **2 — Autenticidade de recibos do produtor** | Recibo Ed25519 sintético, CI #39309509077 | Conta/chave do emissor fora do fixture, readback/recibo do fornecedor, prova efetiva de efeito ou fence terminal no-effect, origem confiável |
| **3 — Primeira tentativa/resultado incerto** | A110 e ensaio de crash confirmam bloqueio local de UNCERTAIN e que backup antigo elimina esse marcador; CI #39312063253 | Fence independente pré-efeito; reconciliação de provedor; resposta perdida sem reenvio; concorrência real de dois hosts |
| **4 — H0 após reinício e rollback** | Observador H0 examina SQLite real e sempre bloqueia; CI #39323959715 | Inicialização real obrigatoriamente guardada, witness externo monotônico/pinado, reboot/power loss físico e custódia independente anti-PITR |
| **5 — Compatibilidade SQLite leitura** | Recusa de conexão usada por thread estrangeira no `SQLiteChatStore`, CI de RED #39316307777 e correções LAB posteriores | **Identificador/teste original do P0 histórico ainda não foi reconciliado**; bateria do caminho de leitura em ambiente real + original RED→GREEN canônico |
| **6 — Compatibilidade SQLite escrita** | Guards LAB para transação proprietária/threads em Outbox, Saga e Budget; CI #39320080553 | **Identificador/teste original do P0 histórico ainda não foi reconciliado**; durabilidade, transação externa, WAL, Windows físico e CI canônica |

**Todos os seis permanecem OPEN.** Os dois apelidos SQLite são categorias de trabalho, NÃO IDs canônicos certificados. O registro em JSON atribui `status` e `missing` explícitos, todos com `independent_evidence_obtained=false`. Não transformar `PASS` de LAB em `CLOSED` no registro.

### Lacuna transversal M71, ainda RED

Validador público do gate de reativação do Worker recebe um gate `READY` anterior à reabertura do incidente. Dentro dos 300 segundos de TTL, a função aceita o gate antigo sem revalidar uma nova observação de incidentes. O M71 original demonstrou `AssertionError: 'READY' != 'BLOCKED'` em Linux/Windows [run #39264761619](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39264761619).

Nesta rodada, o mesmo cenário foi copiado **sem afrouxar a expectativa** para `test_aion_p0_m71_original_stale_gate_safety_negative_lab.py`. O teste negativo roda isolado num subprocesso: deve falhar, e a suíte de inventário exige ver o marcador `M71_RED_STALE_READY_GATE_ACCEPTED_AFTER_REOPENED_INCIDENT`, exit code diferente de zero e a divergência literal READY/BLOCKED. Isso prova apenas que a **propriedade desejada está violada** no validador A118 original, não que exista approval legítimo ou bypass de writer/Worker/fornecedor. A função de Writer ainda é negada por falta de autoridade externa. O guard verdadeiro exige revalidação de incidente por fonte confiável **imediatamente antes da operação de habilitação**, com epoch monotônico/pinning de escopo, sob o HARD NO-GO.

### Quality e Security originais sem waivers

- Fonte Quality: `.github/workflows/quality-tests.yml` com extração do conjunto exato de root files (`562` root tests em seleção). A seleção executada em LAB foi **6.562 casos, 51 FAIL, 34 ERROR** no [workflow #39333976933](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39333976933). Ainda aguardamos eventual run seguinte após ajuste no test helper de Git hash. A suíte permaneceu RED, **não mascarada**.
- Histórico anterior `#38919546692`: 6.562 casos, 50 FAIL e 34 ERROR. A falha adicional agora é o test de cobertura `test_quality_workflow_coverage`: 15 root files de testes LAB não listados na seleção canônica. Isso é uma lacuna real de CI, embora NÃO demonstre nova brecha de execução. A lista inclui o M71 negative-by-design, que não deve ser banalmente adicionado a uma suíte que espera tudo PASS, e testes de LAB que hoje possuem CI dedicada. Reconciliar estrutura/segregação desses arquivos e seleção de testes **sem apagar o RED M71 nem relaxar o Quality gate**.
- Segurança canônica A74/A76 `--canonical --security`: **365/365 PASS** na mesma rodada, sem alterar o status global. Diversos erros Quality decorrem dos contratos antigos que tentam caminhos agora bloqueados antes do produtor; é preciso distinguir expectativa obsoleta de regressão real caso a caso antes de propor compatibilidade.
- Após a primeira execução Ubuntu 10/10 de evidência, Windows falhou **apenas** porque o helper Python fez hashing manual de arquivos CRLF, em vez de usar o `git hash-object` que normaliza arquivos do checkout. O próprio workflow havia confirmado hashes A118 no Windows; o helper foi corrigido **somente em teste** no commit `44a4de01817d896e056810025d6c68ec8e34112f`. O teste M71 propriamente dito reproduziu seu RED no Windows original. CI de reexecução [#39334210568](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/39334210568) cobre o helper revisado.

## O que fazer a seguir (na ordem)

1. **Remediar RED M71 no limite do validador**, com contrato de fonte fresca e confiável para incidentes reabertos, testado antes de tocar em qualquer writer/Worker. Se o validador não consegue recuperar estado atual independente, sempre BLOCKED. Não aceitar só um JSON de incidente enviado pelo caller.
2. **Rastrear SQLite P0 exatos** até os nomes/testes/stack traces de origem; caso não haja identificação verificável, manter unverified. Separar erro do teardown Windows dos dois P0 de leitura/escrita, não contar guard local como homologação.
3. **Triage da Quality RED** sem alterar expectativas nem blanket-xfail, incluindo os 15 root files LAB fora da seleção do workflow.
4. **Homologação de fontes externas** para owner, receipts, first-effect H0 requer matrícula de dispositivo/contas, gastos, identidade de custodiante e aprovação explícita do proprietário; nenhum desses itens foi executado e nenhuma credencial real pode ser autoenrolada por um fixture.
5. Continuar com `HARD NO-GO`, `Worker OFF`, `ZERO_AUTO_RESEND`; usar o JSON apenas como registro de dívida de evidência, não como fonte de autoridade.

**Conclusão:** a auditoria mostra o que já foi provado localmente e, sobretudo, o que ainda não foi. 0/6 P0 homologados; falhas canônicas e M71 permanecem visíveis. Nenhum efeito externo, merge, deploy ou despesa nova.
