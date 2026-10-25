# AtlasQuant / AION — G58 Histórico Semântico e Recuperação Local

**Data:** 2026-10-25. **Branch LAB:** `lab/aion-a190-g58-historical-semantic-custody-deny-20261025`. **PR Draft:** [#1544](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1544), empilhada sobre a G57 #1543; NÃO está em main.

## Resultado técnico restrito

A G57 exigia declaração de `semantic_event_id_lab` junto do `payload.business_event_id`, mas não examinava adequadamente decisões antigas que sobreviveram sem a respectiva reserva semântica. Com uma linha histórica no tenant cujo lock fosse apagado, um novo `intent_ref` poderia criar segunda operação para o mesmo evento declarado. Isso é uma admissão duplicada **local**, não prova de segundo efeito financeiro externo.

A G58 passa a auditar decisões existentes do **mesmo tenant** dentro do BEGIN IMMEDIATE já usado pelo Outbox, antes de inserir nova reserva, decisão ou ação. Usa parsing de JSON estrito com rejeição de chaves duplicadas (inclusive escapes equivalentes), constantes não finitas, estruturas inválidas, decisão órfã e divergências básicas de owner/tenant/workspace. Negativas:
- `G58_HISTORICAL_SEMANTIC_CUSTODY_DENY`: mesma identidade declarada por outra chave Outbox já existente;
- `G58_HISTORICAL_JSON_UNTRUSTED_DENY`: histórico não pode ser interpretado com segurança;
- preserva a negativa histórica `semantic lock missing for existing intent` como `ValueError` na repetição do mesmo request sem lock.

**Não há migração, backfill, correção silenciosa, reenvio ou invocação de provedor.** A política fail-closed pode reduzir disponibilidade quando o histórico não é verificável; não é um plano de produção. O scan é O(n) no histórico do tenant e executado sob transação de escrita: custos e índices devem ser medidos separadamente antes de qualquer implantação.

## Evidências RED -> GREEN

1. Testes foram versionados **antes da correção** no SHA `9456d33aebe7333de6c51c54fe1ecdbf561e8034`. Windows contra G57: 11 testes, 5 falhas de expectativa reproduzindo segundo alias, histórico malformado/duplicado ignorado e operação revogada; também 1 erro **do fixture**, que esperava `RuntimeError` onde o contrato antigo corretamente levantava `ValueError`. O erro de fixture não é contado como vulnerabilidade.
2. Patch no motor no SHA `0f27616e1a152db37fcb063141b8fc2a000f924b`, consulta SQL somente por tenant, parse JSON estrito e negação transacional sem escrever artefatos externos.
3. Corrigido o contrato do fixture no commit `999b636c18a2ecee9cc5e19fb605fc2a567de020`; G57 teste 10 (antes RED deliberado) passa a exigir negação, versão `f27aba07618942d7b296fb8027fb90b24d085311`.
4. Adicionados controles de escape JSON, `NaN`, formatação não canônica, decisão órfã, tenant estrangeiro no SHA `f5b369b22147688284866ce8b813b71139a395d2`.
5. Codex identificou que o teste inicial de duplicate-escape estava usando uma sequência `\u0070` que Python interpretava antes do JSON. O teste foi corrigido no SHA `6ddbdf2fc35eefe02314cdc9d3288ad44a98d5c0`. **G58 16/16 PASS** no Windows após a correção.
6. G57, G39, G44, G37 e o restante da regressão G30–G58 foram aprovados localmente no SHA `e90b9a0f9e96b28c01dcba9ff45949453b5467e1`: **517/517 PASS**, checkout isolado limpo. Esse é o SHA completo anterior à pequena correção de teste de escape; a bateria nova G58 foi repetida com a correção.

## Codex independente: revisão e limites identificados

- Codex CLI Windows, modo `read-only --ephemeral`, sessão `01a1741a-4028-7e81-a530-511e8caddfbd`, revisou a G57 e recomendou checagem histórica por tenant com parse JSON estrito no BEGIN já existente, sem editar nem rodar testes.
- Codex sessão `01a17420-f0a2-7231-9634-f43227be801e`, revisão **real do código G58** somente leitura, apontou limitações adicionais. **NÃO CORRIGIDAS NESTA G58**:
  - Adulterar semanticamente um documento JSON histórico (trocar/remover `payload.business_event_id`) mantendo outras colunas originais pode esconder a identidade real anterior do scan. A G58 verifica forma e escopo, mas ainda não rederiva toda a identidade/digest/colunas de cada documento histórico. Uma nova admissão pode não detectar a adulteração.
  - Apagar uma decisão e manter apenas uma linha órfã em `action_outbox` pode torná-la invisível, pois a varredura começa por `action_decisions`. O teste G58 atual cobre somente o inverso (decisão órfã).
  - Relação `decision_id` e cardinalidade não são inteiramente provadas pela inspeção de escopo; há risco de disponibilidade e integridade sob corrupção. Não demonstrada admissão precoce causada isoladamente pelo fan-out.
  - Varredura de todos os documentos históricos do tenant tem custo de desempenho não medido.
  Essas observações vêm de **leitura estática** e necessitam de novos testes RED antes de qualquer reivindicação de correção. As duas primeiras são alvos sugeridos para G59.

## CI, precisão de evidência

- GitHub Actions [G58 primeiro run #40217069228](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40217069228) terminou **FAILURE em Ubuntu e Windows** numa verificação desatualizada: o workflow ainda procurava o antigo marcador RED da G57, que foi convertido em GREEN. Os jobs falharam no passo G57 de greps, não no teste G58.
- Corrigido o marcador e eliminada a execução duplicada de G56 no workflow no SHA `7036eab28836905c46cde0735d3e63804fde0a79`; o CI passou a exigir **517 casos não duplicados por OS**.
- CI da G58 em SHA posterior ao reparo deve ser consultado em job logs antes de declarar matriz aprovada. O relatório é um commit documental posterior, não se deve trocar SHA de prova sem rerun.

## Limites permanentes / gate

- Mesmo identificadores distintos declarados pelo usuário podem representar a mesma obrigação econômica. Não há fonte confiável para provar unicidade do evento real.
- Se todo o histórico e locks forem apagados ou coordenadamente revertidos, a G58 não tem raiz de confiança fora do host.
- Não comprova assinatura/autenticidade de recibo de fornecedor, HUMAN_OWNER externo, primeira tentativa única entre fornecedores, H0 físico, recuperação a power-cycle ou auditoria Quality/Security canônica.
- Sem merge, deploy, Worker, callback externo, credenciais, dados de clientes, fundos, custo adicional nem habilitação de resend.

**0/6 P0 HOMOLOGADOS — HARD NO-GO — UNCERTAIN — ZERO_AUTO_RESEND.**
