# ATLASQUANT / AION — Checkpoint M63: testes negativos de proveniência
**Data:** 2026-10-19 · **Escopo:** laboratório documental, somente leitura; **GO-LAB limitado / NO-GO integração / HARD NO-GO operacional**.

## Estado da fonte
O A118 permanece no PR [#1326](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1326), **aberto / Draft / sem merge**, HEAD `c62fab663c6349d7320f7843c8d09587c514426b`; não foi identificada revisão formal submetida no PR nesta conferência. Computador Windows `am12` **OFFLINE**. Nenhum código oficial, branch de produto, feature flag, Worker ou deploy foi modificado.

## Experimento reproduzido: o que foi realmente executado
Em ambiente isolado da conversa, reexecutada a transcrição **somente da função** `operational_incident` (linhas 212–249 de `atlasquant_aion_global_worker_supervision.py`, commit A118). A transcrição foi criada no M61 e conferida visualmente contra o trecho oficial do GitHub; **não é importação nem execução integral do produto**, e não valida a autenticidade de origem.

Executado `python -B -m unittest -v test_m63_boundary_RED` contra a cópia isolada, duas rodadas, preservando a expectativa futura:
- **9 testes: 6 PASS / 3 FAIL deliberados / 0 ERROR**.
- 01–06 (caracterização atual): proposta com `source_authenticated=False` recebe `evidence_state=CONFIRMED`; `incident_open='false'` é truthy; digest ausente ainda produz `INC-AION-GW-`; campos adicionais que alegam credenciais não alteram a saída; nenhum efeito externo automático; mesma evidência com campos alegados de origem diferentes tem o mesmo ID.
- 07–09 (exigências FUTURAS para a camada de **admissão**, ainda não presente): negar autenticidade sem matrícula de produtor; rejeitar abertura não booleana; rejeitar identidade de incidente incompleta. Essas três expectativas falham quando aplicadas à **função de proposta** — que por contrato atual é read-only.

**Advertência metodológica:** os 3 FAIL NÃO são prova de três vulnerabilidades operacionais nem significam que `operational_incident` deva executar a autenticação. Apenas tornam explícito que seria perigoso usar a proposta como decisão de admissão durável. A futura função de admissão deve garantir esses vetos por sua própria autoridade; sem ela os testes positivos de admissão são impossíveis.

## Achado sustentado pela fonte oficial
- `atlasquant_aion_global_worker_supervision.py:212–249`: a proposta fixa `source=aion_global_worker_live_verification`, `evidence_state=CONFIRMED`, `status=OPEN` e `executes_action=False` sem verificar autenticidade do produtor dentro desta função. Hash Git do módulo A118: `8a6ab6be8789deeeb80b6b2df39df9745d91e902`.
- `atlasquant_aion_global_worker_incident_reconciliation.py:237–430`: reconciliação de propostas e fechamentos é read-only; não fornece o admitidor durável de `OPEN/REOPEN`. Blob A118 `85541bb2d10f0b97b096df10b5184851160cfec9`.
- `atlasquant_aion_global_worker_activation.py:638–705`: mesmo após avaliações locais, o wrapper retorna negação independente de autoridade; não foi demonstrado bypass operacional. Blob A118 `df43bb4371c784396069f4ede51205b0aa19cc0a`.

## Contrato de admissão a comprovar ANTES de implementar storage
1. O **produtor** de observações OPEN/REOPEN deve ter origem, identidade, escopo e revisão autenticados independentemente do objeto de proposta.
2. O **admitidor** tem permissão explícita de registrar abertura, diferenciando proposta `INCIDENT_PROPOSED` de commit persistido. Sem produtor matriculado ou tipo inválido, negar commit e qualquer reativação dependente da evidência.
3. A identidade **causal da ocorrência** é distinta do `evidence_digest`; uma ocorrência não se define por prefixo de hash, status ou motivo isolados.
4. O estado durável deve sobreviver a reinício com flag desligada, revisão monotônica, proteção honesta contra rollback/replay dentro da fronteira de confiança definida e leitura completa/fresca na decisão final.
5. Nenhum rótulo `CONFIRMED`, campo `producer_enrolled` autodeclarado, checksum local ou token fictício concede permissão. Incerteza => UNKNOWN/BLOCKED; não apagar sinal como efeito colateral.
6. A verificação de ausência de incidentes deve ser independente do histórico de **fechamentos**; no M53/M54 ficou demonstrado que o código de gate local pode dispensar análise por zero closures, mas o Worker real continua bloqueado por guardas separados.
7. O contrato só poderá ser considerado em integração quando **o caminho do produtor até o efeito** estiver provado com identidades/recibos reais, testes oficiais, restart, falha de commit, concorrência, reabertura, antirollback e revisão externa.

## Resultados e pendências
**0/6 P0 homologados; HARD NO-GO; Worker OFF; ZERO_AUTO_RESEND; A118 Quality histórica 50 FAIL e 34 ERROR e três resultados históricos de reativação permanecem pendentes, não reexecutados no M63.** Sem merge/deploy, contratação, PR novo, permissão, escrita de checkpoint runtime, envio a fornecedor, ou gasto adicional.

**Próximo critério de decisão:** identificar um responsável legítimo pelo produtor e pelo admitidor de OPEN/REOPEN, ou registrar formalmente que essa dependência impede prosseguir com storage. Não iniciar novos testes sintéticos apenas para aumentar PASS. Se a origem independente não puder ser estabelecida, redirecionar esforço aos P0 reproduzíveis e verificáveis localmente, preservando este bloqueio.

## Custódia e limitações
Este arquivo é um **checkpoint textual** público na branch isolada de continuidade; não contém dados pessoais, segredos nem evidências reais. O teste e seus logs foram construídos em ambiente temporário da conversa e, quando anexados, devem ser mantidos como artefatos complementares. **Não são repositório oficial, CI, auditoria Codex ou homologação.** A mídia da conversa não substitui cópia de segurança permanente dos binários. 
