# AtlasQuant / AION A190 — G64: privacidade da confirmação e limite de profundidade

**Data:** 2026-10-25. **Branch LAB:** `lab/aion-a190-g64-confirm-opaque-privacy-depth-20261025`. **PR Draft:** [#1550](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1550), empilhada sobre G63 #1549, **não main**.

## Escopo restrito

A G63 validava ciclos antes de `_confirm`, mas ainda serializava `redact(raw_result)` com `json.dumps(default=str)`. Um objeto opaco Python convertido *depois* do redactor podia produzir texto sintético parecendo `sk-...` ou `Bearer ...` e gravá-lo no ledger local `action_effects.data`. Além disso, a detecção de ciclos G62 não impunha limite de profundidade; árvores acíclicas muito profundas podiam causar `RecursionError` ou consumo excessivo de recursos.

Esta é uma falha de privacidade/robustez **somente em SQLite sintético**. Não demonstra efeitos reais em fornecedor, nem comprometeu informações reais neste teste.

## Codex independente antes do patch

Codex CLI Windows 0.164.0-alpha.11.1, `-s read-only --ephemeral`, sessão `01a1748a-fb02-7f43-ae8e-2ebdb804e8ad`. Leu `_confirm`, `_assert_acyclic_payload_lab`, `privacy.redact` e testes G63, e confirmou estaticamente as duas vias de risco. Recomendou verificar o *JSON já codificado* antes do BEGIN sem chamar `__str__` novamente; limite de 64 níveis (raiz = nível 1), preservando DAG compartilhado; teste espião de zero `BEGIN IMMEDIATE`. Não editou código, rodou testes ou contatou rede/provedor.

## RED factual antes da correção

`labs/a190/test_g64_confirm_opaque_privacy_depth_lab.py` foi criado **antes** da alteração do motor no commit `d6125be28ce92b5f309b865f3fc7ad4371ed97d9`. Bateria Windows em arquivo SQLite descartável sobre motor G63 inalterado: **12 testes; 7 PASS, 5 FAIL reais**. Três falhas de objetos opacos gerando marcadores sintéticos em resultados de confirmação (inclusive dentro de tupla); duas falhas de aceitação de 90 níveis de listas sem rejeição de profundidade. Sete controles normais já passavam, incluindo objetos de texto benigno, redaction de strings, resultados acíclicos compartilhados e ciclos conhecidos G62/G63.

## Patch de laboratório

Código `atlasquant_aion_execution_outbox.py` em `93705c717bf8e7dc6ddc9cd1c316cb03f5ceb7b1`:

1. `_assert_acyclic_payload_lab` passou a verificar limite **64 níveis de contêiner** para Mapping/list/tuple, com `G64_EXCESSIVE_NESTING_DENY`. O objeto raiz começa no nível 1; nível 65 é negado, preservando recusa específica de ciclos e referências compartilhadas acíclicas. Ocorrências profundas sob `password` também são verificadas **antes** da ocultação. Política é fail-closed: entradas previamente aceitas com profundidade maior que 64 agora serão recusadas, sem migração.
2. Em `_confirm`, depois de `encoded = _canonical(redact(raw_result))`, o JSON já codificado é interpretado e verificado novamente contra `redact`. Se surgir padrão de segredo *somente* no texto convertido pelo objeto, o método recusa com `G64_CONFIRM_SERIALIZED_PRIVACY_DENY`, **antes do BEGIN**, sem ledger novo e sem reparo silencioso. Usa os bytes `encoded` originais aprovados para eventual persistência. Não serializa novamente o objeto customizado.
3. Não altera `_confirm` para autenticar recibos, não desbloqueia Worker/provider/SEND e não modifica COMMIT/rollback.

Testes pós-patch: **G64 12/12 PASS**. Expansão da suíte em `4e7a290d3ce8ee35efc183d966426ef13b512b67`: níveis 64/65 explicitamente aceito/negado, profundidade sob chave redigida, e instrumentação `BeginWatch` confirmando **zero BEGIN** para resultado cíclico. **G64 16/16 PASS**. G63, G62 e G61 herdados também passaram.

## Regressão completa / CI

Workflow `.github/workflows/aion-a190-g64-confirm-privacy-depth-lab.yml` no SHA de código e CI **`a8935e708736f01f3851dbf43447c08884fb5df7`**. Regressão Windows isolada `C:\Users\apare\AtlasQuant-G64-Confirm-LAB-20261025`: G30–G64 (G51 consolidado em G50) **588/588 PASS**, exit code 0, checkout Git limpo, exatamente nesse SHA.

[GitHub Actions run G64 #40226802145](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40226802145): job Ubuntu `121269777059` **SUCCESS** quando foi escrita a versão inicial deste relatório; job Windows `121269776940` estava na fila. Conferir contagem e marcadores nos dois logs antes de declarar sucesso multiplataforma. Este documento é commit posterior, somente documentação, não substitui SHA de código testado.

## Segunda revisão Codex independente, pós-patch

Codex CLI somente leitura/efêmero, sessão `01a17490-5f47-7b90-866c-1f7eea43b541`, inspecionou o **código corrigido** no SHA `a8935e708736f01f3851dbf43447c08884fb5df7` e os 16 testes G64, sem editar arquivos, executar testes ou usar rede. Confirmou pela leitura que:
- A confirmação realiza teste de ciclo/profundidade, redaction, **uma serialização** e conferência do JSON persistível antes do BEGIN. As duas chamadas `json.loads` não repetem `__str__`.
- O limite conta raiz como 1; 64 aceita e 65 recusa. Os testes G64 demonstram o limite exato em enqueue e o bloqueio de confirmação com profundidade 90, mas **ainda não testam exatamente 65 níveis em confirmação**.
- Erros rasos de ciclo mantêm os códigos G62/G63; excesso de profundidade tem código G64; checks de G63 de privacidade permanecem anteriores aos de divergência de digest.

**Lacunas remanescentes, não resolvidas:**
1. Se o primeiro ancestral cíclico reaparecer exatamente no nível 65, a checagem de profundidade ocorre primeiro, alterando a precedência G62/G63 para G64. Verificar e documentar política via RED específico.
2. O teste de objeto opaco benigno não instrumenta `__str__` para comprovar **exatamente uma** chamada. Testar retorno diferente numa segunda chamada, garantindo que não ocorre.
3. O limite de profundidade não limita quantidade total de nós, largura de objetos, tamanho de bytes e expansão de DAG compartilhado. Exige cotas separadas e validação de disponibilidade.
4. `privacy.redact` preserva **chaves** arbitrárias de dicionário; um marcador sintético no próprio nome da chave poderia escapar ao mesmo verificador de redação. Criar RED/solução separada, sem alegar DLP completo.

Nenhuma dessas lacunas é homologação P0 ou autorização de deploy. Sugestão de próxima rodada LAB: G65 para chaves de JSON, limites de largura e testes de profundidade/begin.

## Limites explícitos, não resolvidos pela G64

A redaction é baseada em padrões e não prova DLP universal; strings personalizadas com formatos desconhecidos ou efeitos colaterais em `__str__` não são cobertas. Outras estruturas Python não suportadas, chaves sensíveis fora do contrato, strings Unicode especiais, mudanças de função `default=str`, integridade após corrupção física e histórico legado exigem verificações separadas. O limite de 64 níveis é uma política conservadora, não um resultado de homologação com cargas reais.

Não existe prova externa independente da identidade HUMAN_OWNER, autenticidade de recibo de provedor, primeira tentativa remota idempotente com resultado desconhecido, custódia H0 monotônica fora do host, resistência física a rollback, nem certificação integral de SQLite nativo e Security/Quality.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND.** Nenhum merge, deploy, Worker, envio externo, credenciais, cliente, fundos ou novo gasto.
