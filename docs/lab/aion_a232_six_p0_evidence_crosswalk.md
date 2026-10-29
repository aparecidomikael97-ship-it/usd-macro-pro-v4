# A232 — Cruzamento dos 60 desafios A231 com os seis P0 históricos

**Estado:** inventário de pesquisa, **não** aceite, prova externa nem certificado operacional. **HARD NO-GO · P0 homologados 0/6 · `UNCERTAIN=ZERO_AUTO_RESEND`.**

## Proveniência e regra de contagem

Os seis P0 são os da matriz histórica `docs/aion/AION_P0_MATRIZ_PENDENCIAS_20261022.md`, publicada no [Draft A183 #1474](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1474). A cobertura de A231 é um catálogo de **12 requisitos × 5 domínios = 60 células não executadas**. Uma mesma pergunta pode ser relevante a mais de um P0: por isso a soma dos vínculos abaixo **não significa novas provas obtidas**.

| P0 | Bloqueio concreto | Questões A231 que apoiam o futuro ensaio | O que não pode ser substituído pelo checklist |
|---|---|---:|---|
| **1 — HUMAN_OWNER** | Pessoa proprietária e raiz de confiança não autenticadas externamente | 35 células (7 requisitos × 5 domínios) | Cerimônia real de identidade, assinatura explícita e revogação/recuperação |
| **2 — Recibo** | Assinatura local não comprova a instituição emissora nem efeito final | 30 (6 × 5) | Recibo autoritativo de fonte independente e consulta de reconciliação |
| **3 — Primeira intenção** | Novo ID, rollback e ACK incerto podem duplicar efeito | 30 (6 × 5) | Identidade autêntica do evento e reserva linearizável **antes** de enviar |
| **4 — H0 / rollback** | Host e testemunha locais podem ser restaurados juntos | 30 (6 × 5) | Testemunha monotônica independente e reinício/recuperação realmente adversarial |
| **5 — SQLite leitura** | Pathname, descritor auxiliar e VFS não provam o mesmo handle real | **0** — a matriz externa não resolve esta obrigação nativa | Vínculo real de handle/FD/VFS ou nova arquitetura; ABA e restore mesmo inode hostis |
| **6 — SQLite escrita** | Resultado após COMMIT incerto, backup/restore e sidecars sem garantia | 10 (2 × 5), apenas **apoio** para recibo/reconciliação | Handle de escrita atômico, resultado pós-COMMIT confiável e ensaios de durabilidade/sidecars |

**Observação:** 35+30+30+30+0+10 = 135 associações sobre as mesmas 60 perguntas. **Não são 135 fontes, certificados ou testes externos.** Todos os 12 requisitos A227 foram associados a pelo menos um P0; nenhum foi homologado. O P0-5 é propositalmente `0`: seria enganoso chamar controles de autoridade externa de solução para uma falha real de arquivo SQLite.

## Dependências e execução permitida

**P0-1/2/4 — externo, não autorizado agora:** raiz confiável fora do host, custodiante/testemunha independente, entidade financeira e cerimônia humana. Nenhum nome, conta, preço ou serviço foi selecionado.

**P0-3 — pesquisa interna possível:** caracterizar a rota de primeira tentativa e as falhas por IDs forjados e restauração, sempre com `UNCERTAIN=ZERO_AUTO_RESEND`. A prova de evento autêntico e custódia resistente a rollback continuará externa.

**P0-5/6 — pesquisa interna necessária, não substituída:** matriz de leitura e escrita SQLite com VFS/FD, concorrência, same-inode restore, WAL/SHM/journal, backup e pós-COMMIT incerto. A existência de testes sintéticos A231/A232 não mede a correção do caminho nativo.

O registro A232 é estrito, vinculado a A231 por digest **local não autenticado**, exige IDs P0 1–6 e descrições canônicas, e só permite `NOT_OBTAINED`, `NOT_PROVEN`, `NOT_DONE`, `HARD_NO_GO`. Qualquer host que se declare aprovado, que troque origem, que forje escopo/aceite ou apresente P0 >0 é recusado. Todos os `may_*` e todos os campos de identidade, efeito, leitura/escrita comprovada são `False`.

## Entregáveis e limite de evidência

- `labs/a232_six_p0_evidence_crosswalk.py`: mapeamento tipado de seis P0 e seus gates nativos/externos; validação somente leitura.
- `labs/test_a232_six_p0_evidence_crosswalk.py`: 50 testes adversariais, com P0-5 sem falsa cobertura, P0-6 sem falso aceite e upstream A231 fail-closed.
- `.github/workflows/aion-a232-six-p0-evidence-crosswalk-readonly.yml`: Ubuntu e Windows, **1.005 testes por sistema esperados** (50 novos + 955 anteriores), sujeitos a confirmação dos logs.

**Conclusão:** o inventário mostra onde falta **evidência externa** e onde falta **engenharia nativa real**. Mesmo completo, este documento não fecha qualquer P0, não justifica compra de serviços, não escolhe raiz offline/KMS/HSM e não libera merge, deploy ou Worker.
