# AION P0 — Envelope assinado Ed25519, replay e rollback: ensaio criptográfico NEGATIVO em LAB

**Data: 20/10/2026 — estado HARD NO-GO.** Não há chave pública produtiva matriculada, emissor externo autenticado, serviço remoto de último head, challenge externo, armazenamento monotônico inviolável ou fonte real de revogação; portanto **nenhum teste desta proposta libera Worker, primeira operação ou efeito externo**.

## 1. Por que testar criptografia sem alegar ter uma fonte externa

O contrato [#1358](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1358) fixa **sempre `BLOCKED`** mesmo para pacotes sintéticos coerentes. Esta continuação testa um requisito intermediário concreto com a dependência já presente no projeto: **`cryptography==50.0.2`** e seu verificador **Ed25519**. Os testes usam um par de chaves efêmero **gerado apenas em memória durante a execução**, nunca matriculado em IAM, FIDO2, AWS ou uma conta real.

O arquivo `atlasquant_aion_p0_signed_incident_envelope_lab.py` inspeciona assinatura matemática sobre bytes canônicos de um envelope e domínio separado (`ATLASQUANT:AION:P0:INCIDENT_WITNESS:LAB:V1\x00`). Mesmo assinatura válida e contexto coincidente retornam **`BLOCKED`**, com flags de autoridade `False`. A função **não recebe nem configura autoridade produtiva**. A chave pública passada pelo próprio teste é **tão não confiável quanto o pacote**; verificação criptográfica não prova matrícula, separação de administradores ou chave vigente.

| Evidência no LAB | Consegue demonstrar | Não comprova |
| --- | --- | --- |
| Assinatura Ed25519 correta | Posse da chave privada correspondente à chave pública fornecida | Identidade real do emissor ou autorização do HUMAN_OWNER |
| Formato JSON único e canônico | Ausência de campos duplicados, ambiguidades simples e mudanças ocultas no payload | Prova de proveniência independente, antirollback, assinatura da fonte correta |
| Campos issuer/scope/epoch/seq/head/nonce | Inconsistências locais quando comparados a valores esperados pelo chamador | Head externo mais recente ou nonce registrado fora da máquina |
| Intervalo de tempo 300 s | Envelope rejeitado com datas inválidas, expirado ou emitido depois do relógio indicado no teste | Frescor autêntico se o relógio do executor for manipulado |
| Check de head local | Mismatch detectado contra a cópia indicada na entrada | Que duas cópias antigas, ambas coerentes, não sofreram PITR coordenado |
| Flags `execution_allowed=False` etc. | Saída do LAB sempre negativa | Ausência histórica de operação do produtor ou efeito remoto |

## 2. Casos adversariais desta rodada (34)

Em `tests/test_aion_p0_signed_incident_envelope_cryptographic_lab.py`:
- assinatura correta porém sem matrícula; chave pública diferente; alteração de bytes; assinatura de outro domínio;
- repetição da mesma assinatura e nonce, demonstrando que criptografia **não implementa um replay cache**;
- troca de issuer/repositório/tenant, nonce, data de emissão futura, expiração, janela excessiva e fuso/formato inválido;
- campos epoch/revogação com `bool`, número negativo, zero ou overflow; mismatch de sequências, digest e head;
- incidente aberto/desconhecido corretamente negado; ausência de leitura externa;
- JSON com membro duplicado, campos extras, espaços não canônicos e payload excessivo/profundamente aninhado;
- entradas de tipos hostis e objetos que tentam executar `__eq__`/ `__ne__` ou `__str__`;
- **substituição da chave pública por chave gerada pelo atacante**: assinatura matemática verdadeira, mas identidade do emissor ainda `False`;
- **rollback coordenado do envelope e do head para a mesma época antiga**: correspondência matemática válida, porém frescor e monotonicidade externos continuam falsos.

A CI branch-only Ubuntu/Windows executa os 34 testes, além do modelo anterior de custódia SQLite local em dois domínios, **30 testes do contrato estrutural #1358**, **12 A53/A76**, A74/M71 antigos, **22 IAM H0**, **17 de rollback em três domínios**, 17 testes de ciclo de vida SQLite STAGING, 8 hardstops e **23 módulos LAB raiz**. Testes legados RED da Quality não são eliminados nem alterados.

## 3. Condições realmente necessárias para sair de HARD NO-GO

1. Emissor técnico e administrativo independente do executor, conta e recuperação de MFA verificadas; matrícula de chave pública por canal fora do AION e atestado de rotação/revogação.
2. Challenge gerado por verificador independente, ligado a repo/tenant, nonce, digest, epoch, versão, identidade da credencial e pedido individual. Cache de replay durável em domínio que não pode sofrer PITR junto do AION.
3. Último high-water/head lido por identidade verificadora independente, com política IAM read-only, versão exata, retenção, comparação com seq/epoch e garantias contra fork/omissão. Uma assinatura antiga correta **não é prova de que não existe versão posterior**.
4. Owner/HUMAN_OWNER real e reaprovação biométrica de ações críticas; provas separadas de `COMMITTED_EFFECT` e `NO_EFFECT_FENCED` para cada fornecedor e primeira tentativa incerta. Worker permanece sem autoridade mesmo que um pacote de incidente fosse autêntico.
5. Ensaios independentes reais de Windows físico, desconexão, reinício, restauração/PITR e falhas de storage após eventual aprovação de arquitetura e orçamento. Hoje todos ficam proibidos ou indisponíveis.
6. Security e Quality canônicas completas, sem waivers, e conciliação individual dos 32 ERROR Outbox/Saga.

### Operação e FinOps

**Nenhuma conta, chave produtiva, assinatura real, SMS, bucket, Object Lock, KMS, cloud, licença ou custo extra foi criada nesta rodada.** A referência de teto operacional é R$200/mês, com exceção de até R$250 apenas com justificativa e autorização. Os custos de assinatura/ancoragem externa permanecem **não cotados**.

**Estado:** P0 homologados **0/6**, Quality canônica **6.562 testes / 52 FAIL + 34 ERROR**, Security gate **RED em A53**, 32 erros Outbox/Saga `OPEN_NOT_WAIVED`, `HARD NO-GO`, Worker OFF, `ZERO_AUTO_RESEND`. A aprovação de uma CI LAB mede somente comportamento do modelo de laboratório. Sem merge/deploy.
