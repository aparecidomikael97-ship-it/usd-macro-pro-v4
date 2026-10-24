# A190 G6 — Outbox REAL e risco de callbacks autoalegados como raiz

**Data do proprietário:** 2026-10-23. PR Draft sobre G5 #1492, missão #1486. Somente novos testes/CI/docs; nenhum código de runtime alterado.

## Fato de código observado

O módulo real atlasquant_aion_execution_outbox.py aceita, no construtor ExecutionOutbox, os parâmetros opcionais first_attempt_guard e evidence_verifier, ambos **callbacks Python fornecidos pelo chamador**.

- Sem first_attempt_guard, o componente muda para UNCERTAIN e não executa adapter.send: comportamento fail-closed **comprovável**.
- Quando a callback de primeira tentativa retorna literalmente True, o Outbox executa adapter.send. A callback não tem autenticação de emissor por si própria — é um ponto de injeção de confiança em memória, já rotulado LAB no código.
- Se evidence_verifier retorna True, recibos declarados pelo adaptador podem levar a CONFIRMED, inclusive após reabrir um outro objeto Outbox com callback diferente. A verificação local de argumentos/cópias não prova origem independente.
- A chave de idempotência criada por enqueue contém intent_ref fornecido ao Outbox; dois refs diferentes para a mesma intenção sintética podem produzir duas chaves distintas. O fato de ambas serem confirmadas via callbacks autoalegados mostra o limite semântico.
- No contrato A183, lab_verified=True significa apenas assinatura sintética verificada contra chaves de fixture; o próprio recibo retorna permits_send=False, permits_retry=False, external_homologation=False. Tratar lab_verified como permissão de envio é uma **integração insegura**, mesmo que as assinaturas sejam criptograficamente válidas.

Não é relatada aqui nenhuma chamada a fornecedor real nem alteração do comportamento operacional por essa PR. O adaptador dos testes somente conta chamadas em memória. O teste que confirma estado interno não é recibo verdadeiro de efeito.

## Oito controles adversariais com o código real

| Teste | Situação | Resultado que o LAB precisa observar |
| --- | --- | --- |
| G6-1 | Sem guarda de primeira tentativa, ainda que verificador de efeito retorne True | **Positivo de segurança:** adapter não é chamado, estado UNCERTAIN |
| G6-2 | Evidência A183 assinada em fixture, interpretação CORRETA de permits_send=False | **Positivo:** Outbox não executa adapter |
| G6-3 | Guarda e verificador entregues pelo próprio chamador devolvem True | **RED:** adapter recebe chamada de envio artificial e Outbox marca CONFIRMED sem raiz independente |
| G6-4 | Guarda True, sem qualquer evidence_verifier | **RED:** a fronteira adapter.send já foi cruzada; efeito não é confirmado |
| G6-5 | Guarda de primeira tentativa gera TimeoutError | **Positivo:** UNCERTAIN e adapter nunca chamado |
| G6-6 | Após SENT, outro Outbox recriado com evidence_verifier=True reconcilia o efeito autoalegado | **RED:** troca de callback permite confirmação sem identidade externa do emissor |
| G6-7 | Dois intent_ref diferentes, payload e operação sintética semanticamente iguais, mesma aggregate_key | **RED:** duas chaves de idempotência e duas chamadas de adapter artificial |
| G6-8 | Converter A183 lab_verified=True para True na callback da primeira tentativa, apesar de permits_send=False e evento NÃO relacionado | **RED:** assinatura de fixture sem binding de evento permite atravessar a fronteira |

## Decisão de arquitetura: onde a confiança precisará sair do aplicativo

1. **Fonte do evento original:** quem emite deve ser identificável por raiz previamente fixada fora do AION/app; registrar escopo, operação, tenant, intenção canônica, nonce, challenge, validade, autoridade e epoch. O aplicativo não pode escolher um ID alternativo apenas por mudar request_ref.
2. **Custodiante:** reserva CAS com sequence/epoch monotônicos em conta/principal/host independente. Retenção e recuperação não podem ser revertidas pelo mesmo admin/root que restaura o SQLite local. Revogação/rotação e re-enrollment nunca podem ser autoalegados.
3. **Efeito e recibo:** o principal que tem a capacidade real de executar deve verificar a reserva original, aplicar semântica de idempotência do fornecedor e devolver recibo autenticado com identificador do efeito/primeira tentativa. Callback genérico lambda True não pode ser admitido como permissão operacional.
4. **ACK e H0:** perda de resposta da reserva, do envio ou do recibo permanece UNCERTAIN e ZERO_AUTO_RESEND, sem fallback para testemunha local ou verificador autoassinado. H0 sem custódia externa responde indisponível, sem nova operação.
5. **Rede, disponibilidade e custo:** ainda faltam contrato de API, escolha de custódia/fornecedor, SLA, retenção, limites e cotação verificadas. Esta PR não escolhe nem provisiona nenhum serviço. R$200/mês permanece teto operacional, aumento até R$250 somente com justificativa e aprovação expressa.

### Critérios falsificáveis para qualquer implementação futura

- Negative control: mesmo host/app tenta substituir root, chave, issuer, floor e callback; todos falham em cruzar a fronteira do **principal independente**. A execução não pode depender de mera string "verified" ou de atributo local do Python.
- Falha ou indisponibilidade do custodiante/emissor externo, rebinding de event_id, certificado revogado, nonce reutilizado, token antigo, conflito de sequência, ACK perdido e restauração do DB são DENY/UNCERTAIN, sem reenvio.
- Positivo: duas origens/serviços de identidade realmente independentes e um recibo verificável vinculam a ação a uma intenção original única. Exigir logs/assinaturas/provas de provedor, não green de fixture.
- Sem contrato externo comprovado, P0-H0 não pode ser homologado por novas iterações Python.

## CI e status inicial

Workflow G6 Ubuntu/Windows repete G6 (8), G5 (5), G4 (5), G3 (6), A189 (10) e A185 (4): 38 testes por OS, 76 execuções caso tudo passe. **CI ainda não executada/conferida no instante deste preflight.** Sempre identificar SHA real, logs e marcadores de contraexemplo.

A190 permanece **0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND**. Cinco external-RED por SO e 43 advisories herdadas não foram reexecutadas/corrigidas; Quality/Security canônicas fora deste workflow. Sem main, merge, deploy, Worker, rede real, gasto ou credenciais.
