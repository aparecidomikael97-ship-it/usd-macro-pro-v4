# AtlasQuant / AION A190 — G65 sensitive JSON key and admission budgets

**Data:** 2026-10-25, **branch LAB:** `lab/aion-a190-g65-json-key-node-budget-20261025`. [PR Draft #1551](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1551) empilhada sobre [G64 #1550](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/pull/1550), **não main**. Sem merge/deploy/Worker/provedor/cliente/credencial/fundos/gasto.

## Problemas mensuráveis

A G64 verificava dados sensíveis **dentro de valores** após serialização, mas `privacy.redact` preserva **os nomes das chaves de dicionário**. Marcadores sintéticos parecidos com `sk-...` e `Bearer ...` eram aceitos como nomes de chaves e podiam chegar ao JSON de decisão ou confirmação. A detecção de ciclos e limite de profundidade 64 não controlava a largura de um array nem a expansão repetida de objetos compartilhados. Não havia política de tamanho UTF-8 para o JSON que seria persistido.

Essas lacunas são somente de privacidade e disponibilidade **local em SQLite sintético**; não provam nenhum efeito real em fornecedor ou cliente.

## Revisão independente Codex — antes do patch

Codex CLI Windows v0.164.0-alpha.11.1 `-s read-only --ephemeral`, sessão `01a17495-fcf0-7e62-83f7-fb1ef55ced41`, leu o código G64 anterior e os testes de privacidade/limites. Sugeriu: rejeitar chaves que acionam redaction de string, preservar nomes normais `password`/`secret` com valores protegidos, contar todas as visitas inclusive duplicações de DAG, evitar conjunto global `seen`, separar cota de bytes e medir UTF-8, validar 4096 permitido / 4097 negado, sem afirmar exactly-once global de objetos. **Codex não editou ou executou testes.**

## RED real versionado antes da correção

Novo `labs/a190/test_g65_key_width_bytes_budget_lab.py` criado sozinho no commit **`a9e366cb9fc596a98db740a2e16ee78cec5cf06f`**, antes de modificar motor. Windows isolado sobre G64:
- **14 testes, 6 PASS / 8 FAIL**. Os 8 FAIL mostram admissão indevida de nomes de chave sinteticamente sensíveis (3), estruturas muito largas/referências DAG repetidas sem orçamento (3) e textos enormes excedendo tamanho pretendido (2).
- Controles G64 de ciclo raso, profundidade nível 65, confirmação legítima e somente uma conversão do objeto opaco já PASS, não são atribuídos à nova correção.

## Correção LAB limitada e testes posteriores

No `atlasquant_aion_execution_outbox.py`, commits **`3fb2f17b89416c0ce83c036c5c9bf3921716de38`** e **`6bde813e9fb8e9bdbe9782c15e205030120bbdd8`**:
1. `_assert_acyclic_payload_lab`, já usado antes de redaction e BEGIN, agora recusa nome de chave `str` cujo padrão seria modificado por `redact(key)`: `G65_SENSITIVE_JSON_KEY_DENY`. Nomes normais que indicam valores sigilosos, como `password` e `secret`, permanecem no documento e o valor é ocultado normalmente. Somente **chaves** disparam a rejeição, não valores.
2. Controle de **4096 visitas expandidas** ao conjunto de contêineres, chaves e folhas, inclusive múltiplas referências ao mesmo subobjeto acíclico. A visita 4097 dispara `G65_NODE_BUDGET_DENY`. Limites G62 ciclo e G64 profundidade 64 mantidos.
3. Controle de **262144 bytes UTF-8 (256 KiB)** sobre o JSON realmente serializado. `enqueue` mede e deriva o digest dos mesmos bytes da primeira serialização **antes de BEGIN**; a serialização final da decisão também é medida antes de `INSERT`, preservando rollback/quarentena se falhar após a reserva. `_confirm` mede `encoded` antes de BEGIN e reutiliza os mesmos bytes sem converter objeto opaco uma segunda vez. `G65_SERIALIZED_BYTES_DENY` recusa, sem truncar ou corrigir.
4. Nenhuma chamada ou autorização real de fornecedor, Worker ou nova tentativa de SEND foi ativada.

O conjunto original passou **14/14** após o patch, mais cinco casos de fronteira. Primeiro gabarito da fronteira contava o contêiner-lista duas vezes e provocou **2 falhas de expectativa do próprio teste**; isso foi corrigido nos testes, sem alterar motor, no SHA **`06cdb063ec5ac50f07bdf53c2c884da0d00dacae`**. A bateria ampliada **19/19 PASS** inclui exatamente 4096 aceitos/4097 recusados em `enqueue` e `_confirm`, proteção de padrões textuais **em valores** e não como chave.

## Proveniência de regressão e CI

Workflow `.github/workflows/aion-a190-g65-admission-budget-lab.yml` versionado com o código no commit **`22b10df9bf4e0067437a4acab045ca7d88688282`**, para Ubuntu/Windows, 607 testes distintos por OS.
- Windows local isolado `C:\Users\apare\AtlasQuant-G65-Budget-LAB-20261025`, `git switch --detach` do SHA acima: G30–G65 (exceto G51, absorvido em G50) **607/607 PASS**, exit code 0, `git status` limpo.
- GitHub Actions [G65 run #40227887293](https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/actions/runs/40227887293) iniciou matriz Ubuntu/Windows no mesmo SHA. **Não contabilizar CI como aprovado sem resultados finais dos dois jobs e conferência de logs.** Esta evidência é um commit documental posterior ao SHA do código testado.

## Codex independente pós-patch e bloqueios para G66

Codex CLI Windows `-s read-only --ephemeral`, sessão `01a1749d-3dc3-7ad2-9822-f1dc68c2a578`, leu o diff G65 no checkout local do SHA de código e CI `22b10df9bf4e0067437a4acab045ca7d88688282`, sem editar arquivos, executar testes ou consultar fornecedores. A inspeção confirmou a separação chave/valor, cota de 4096 visitas, tamanho máximo de 262144 bytes UTF-8 no início da admissão/confirm e a reutilização de `encoded` sem outra conversão `__str__` na confirmação.

**Questões ainda abertas que os 19 testes G65 NÃO cobrem:**
1. Nomes de chave como `authorization`, `access_token`, `api-key`, `apiKey` e `client_secret` com valores simples não são todos reconhecidos pela política herdada em `privacy.redact`. Pode existir dado que deveria ser ocultado sem ser rejeitado.
2. Um `Mapping` customizado é percorrido na verificação, mas a função de redação lida com `dict` e pode tratar outro Mapping como objeto opaco via `default=str`.
3. Materialização de `dict(payload/result)` e a primeira conversão `json.dumps` alocam bytes antes da cota de saída; **o limite é de admissão, não de memória máxima**.
4. Chaves não string podem gerar `TypeError` herdado, sem contrato uniforme; faltam provas de fronteira exata 262144/262145 bytes com UTF-8 multibyte, strings JSON escapadas e recusa com rollback de decisão final maior que o orçamento após reserva.
5. Casos históricos/replay que eram permitidos em G64 e agora excedem cotas G65 podem ficar fail-closed; não há migração ou garantia retroativa de compatibilidade.

Esses são candidatos a testes RED e correções separadas **G66**, sem homologação, sem auto-limpeza e sem redefinir o contrato já testado da G65.

## Limites remanescentes, HARD NO-GO

O limite de bytes impede **admissão e persistência** de JSON muito grande, mas não limita a alocação de memória temporária durante a primeira serialização nem o tamanho de objetos de entrada construídos pelo chamador. O walker executa `Mapping.items()` e percorre dados mutáveis: `__str__` e mappings personalizados têm efeitos colaterais possíveis. A proteção de padrões não é DLP universal; chaves não-`str`, Unicode e outros formatos de segredo exigem auditorias próprias. Registros históricos prévios e novas cotas podem bloquear a operação (fail-closed), mas não foram migrados, corrigidos ou apagados.

Não há identidade HUMAN_OWNER externamente comprovada, recibo autêntico do fornecedor, proteção contra rollback coordenado do host, testemunha de primeira tentativa remota com resultado desconhecido, custódia H0 externa resistente a rollback, validação física de SQLite nem Security/Quality canônica completa.

**0/6 P0 HOMOLOGADOS · HARD NO-GO · UNCERTAIN · ZERO_AUTO_RESEND. Nenhum merge/deploy, Worker, SEND, clientes, dinheiro, credenciais ou gasto real.**
