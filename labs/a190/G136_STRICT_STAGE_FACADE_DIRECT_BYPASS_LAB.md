# A190 / G136 — interface estrita de staging, via G135 + G134 + Outbox REAL

**LAB apenas. HARD NO-GO; 0/6 P0. Draft em cima do G135 #1627.**

## Objetivo e limite

G135 exige manifesto original retido e duas assinaturas sintéticas Ed25519 antes da reserva do G134. Mas o chamado é **voluntário** e qualquer chamador pode invocar o `ExecutionOutbox.enqueue()` normal sem passar pelo bridge. G136 cria uma interface LAB mínima e com uso único que amarra, nesta ordem:

1. **Identidade econômica:** verificar o evento original e os campos canônicos `action, kind, target, amount_minor, currency`; A183 duas assinaturas sintéticas e snapshot LAB retido.
2. **Escopo:** `owner_id, tenant_id, workspace_id` autenticados na fixture têm de coincidir exatamente com o `Scope` do `ExecutionOutbox`.
3. **Reserva primeira tentativa:** subprocesso G134 confirma reserva `tenant/event_id` em SQLite diferente da base do AION, no **mesmo host**. Resposta deve ter texto exato, sem saída extra. Falha/timeout/ACK perdido significa UNCERTAIN e nenhuma repetição automática.
4. **Staging local:** somente depois chamar `ExecutionOutbox.enqueue` **REAL**, com campos restritos. Não aceitar parâmetros arbitrários de política, risco, adapter ou callback de envio pela interface.
5. **Single use / crash:** assim que prova sintética passa, a instância deixa de aceitar novas tentativas, mesmo se a gravação local falhar após a reserva, para que um ACK incerto não gere novo efeito.

## 16 testes: proteções de LAB e contraexemplo obrigatório

1. Duas assinaturas, manifesto e custódia íntegros geram **um** staging local na Outbox real.
2. Nenhuma prova: zero staging, zero reservas.
3. ID original adulterado: nega.
4. Alvo, valor ou moeda adulterados: nega.
5. Escopo de outro tenant: nega mesmo que a assinatura seja matematicamente válida.
6. Custódia ausente: nega, sem criar raiz nova.
7. Custódia corrompida: nega.
8. Reutilização do mesmo facade: nega.
9. Nova instância e request diferente para mesmo `tenant/event_id`: custódia nega.
10. Restauração só do SQLite do AION: custódia intacta nega.
11. Referência de requisição inválida: nega sem consumir identidade.
12. Falha/timeout no subprocesso de custódia: nega e não repete.
13. Resposta adulterada do processo: não aceita substring como ACK.
14. Falha de Outbox depois do commit da custódia: preserva UNCERTAIN, zero retry automático.
15. Outbox real em configuração padrão não chama nem adapter sintético de envio.
16. **RED declarado:** chamador pode usar `ExecutionOutbox.enqueue()` normal diretamente e criar uma linha local sem usar este facade. Continua **não sendo envio externo**.

## Implicação de arquitetura

A interface LAB **NÃO resolve** o bypass por código arbitrário do mesmo processo, subclassing, chamadas ao `_outbox`, raw SQLite, outro SQLiteChatStore, recuperação de snapshot, ou troca conjunta do manifesto e da raiz de assinatura local (contraexemplos G135/G134). Não há referência externa de autenticidade, custódia antirollback off-host, autenticidade HUMAN_OWNER ou efeito econômico fornecido pelo provider. Nenhuma chave sintética pode ser tratada como raiz de confiança real.

Para remover o bypass antes de produção, é necessário um **ponto obrigatório de admissão protegido** fora do domínio de reescrita do chamador/host (ou equivalente efetivamente protegido), com identidade econômica original fixada autenticamente, snapshot de confiança em custódia independente, recibo real do provedor e tests de crash/rollback/alias/same-inode nativo. Inserir um `if` ou um callback self-attested no Python da Outbox **não satisfaz P0**. Em eventual implementação operacional, todo caminho de leitura e escrita precisará falhar fechado quando as provas indisponíveis.

**Sem merge/deploy/Worker/SEND, segredos, despesas, dados reais ou mudança do código operacional.** G122 deve continuar 5 RED genuínos por SO e o G125 canônico permanece inalterado.
