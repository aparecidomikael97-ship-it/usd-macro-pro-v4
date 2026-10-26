# AION P0 G75 — contenção de envio externo por ausência de reserva confiável (LAB)

**Candidato isolado:** G75 sobre G74 RED `662b9e230dcb0e93864d7db526ff3e0f756bdfb5`.
**Estado:** DRAFT / SEM MERGE / SEM DEPLOY / SEM WORKER / SEM SEND REAL. **0/6 P0 homologados. HARD NO-GO.**

## Falha demonstrada e alteração estreita

A G74 documentou 4/4 FAIL reais do baseline: POST de texto e de voz sem reserva e repetição em chamadas manuais após perda simulada de ACK. Nenhuma rede/credencial real foi usada. Codex prepatch na sessão `01a175d5-5f65-75f2-9b84-70711ca99729` localizou `atlasquant_aion_provider.py` e `atlasquant_neural_tts.py` como fronteiras de transporte independentes do Outbox; **não** encontrou retry automático no próprio Outbox.

A G75 acrescenta `atlasquant_external_first_send_gate.require_external_first_send_authority`, sem configuração de bypass, callback do usuário ou modo produtor: atualmente **sempre nega** com `G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE`.
- Texto: depois das proteções existentes de privacidade, feature flag, credencial, aprovação e orçamento, retorna `BLOCKED_FIRST_SEND_AUTHORITY_UNAVAILABLE`, `called=False`, **antes de `post`**.
- Voz: após validação da configuração, texto e chave, lança `RuntimeError(G75_EXTERNAL_FIRST_SEND_AUTHORITY_UNAVAILABLE)`, **antes de `requests.post`**.
- Mesmo valores sintéticos aprovados, configuração pronta, objeto `session` falso, clique repetido ou ambiente falso **não** constituem reserva.
- O teste G74 para as duas rotas de voz muda apenas o tipo esperado de exceção no *candidato G75*: `TimeoutError` de resposta perdida virou `RuntimeError` de bloqueio **antes do POST**. O baseline G74 original (commit `662b9e2`) permanece RED, sem alteração.

## Execução local de laboratório (Windows)

```text
py -B -m unittest -q labs.a190.test_g74_operational_first_send_red_lab labs.a190.test_g75_external_first_send_lab
Ran 16 tests
OK (exit 0)
```

O Codex implementou o patch na sessão `01a175de-4fd7-74a3-ba41-23081a5d6785` em sandbox workspace-write; nenhum envio externo real nem uso de segredos. Verificação local posterior foi executada separadamente. A G75 usa mocks com bloqueio de `requests` e `socket`. O código alterado não faz `git push`, Worker nem deploy.

**Regressão funcional conhecida, não disfarçada:**
```text
py -B -m unittest -q test_atlasquant_aion_provider test_atlasquant_voice_profile
Ran 23 tests
FAILED (failures=2, errors=1); exit 1
```
Três cenários historicamente presumem que o fake HTTP é executado e que sucesso/HTTP 401 são retornados. Bloqueá-los deliberadamente quebra esse contrato anterior. Não foram mudadas as expectativas históricas para fabricar verde. Isso **impede liberação/merge** até decisão sobre UX offline, cobertura e integração confiável; interface atualmente pode mostrar indisponibilidade.

## Limitações inegociáveis

Este código é um **kill switch de contenção**, não uma implementação de testemunha H0, idempotência de evento autêntico, reconciliação, prova de resultado incerto ou recibo real. Chamada direta de biblioteca externa fora dessas duas funções, execução de código hostil privilegiado no mesmo processo e outros provedores não estão atestados. O gate sempre nega; **não é seguro substituí-lo por flag ou callback autodeclarado**. Bloqueio funcional de respostas e áudio externos é intencional no LAB, mas requer decisão de produto.

**Próximo gate:** revisar arquitetura de autoridade externa independente; mapear outras fronteiras com efeito, persistir a identidade original e estado `UNCERTAIN` antes de uma reserva confiável; sincronização anti-rollback em H0; construir testes adversariais em Windows/Ubuntu; reparar compatibilidade historicamente verde somente com um novo contrato de produto explícito, nunca enganando o teste. Sem custo adicional, sem operação real e 0/6 P0 fechadas.

## Revisão independente após o patch

Codex read-only `01a175e0-acec-7e40-a10c-bb32100dac07` inspecionou os arquivos alterados e não encontrou caminho concreto de HTTP não autorizado nas duas fronteiras. Não executou testes, não alterou arquivos e não acessou rede. **Limite apontado:** a aprovação G74 agora testa ausência completa de primeiro envio, não persistência de `UNKNOWN` após envio real. Isso deve ser provado separadamente quando houver autoridade externa e contrato verificável.

A G75 **não deve ser promovida para uso comercial** enquanto os três testes de compatibilidade continuarem falhando e a autoridade externa permanecer ausente.
