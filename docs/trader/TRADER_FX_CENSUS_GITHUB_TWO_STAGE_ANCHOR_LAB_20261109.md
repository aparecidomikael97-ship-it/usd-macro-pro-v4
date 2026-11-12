# AtlasQuant Trader — protocolo de pré-registro externo D1/W1 (LAB, 09/11/2026)

**Estado:** implementação experimental *offline*. Nenhuma previsão de alta/baixa foi emitida. Nenhum comentário de previsão foi postado no GitHub. O AM12 permanece **offline** nesta rodada; não houve leitura dos 103.600 candles arquivados, backtest real, custo, trade, deploy, Worker, integração na UI ou liberação do Radar.

## Por que mais uma camada?

`atlasquant_trader_fx_trial_census_lab.py` já exige um universo completo de **28 pares G8 × D1/W1 = 56 posições por rodada**, com `ALTA`, `BAIXA` ou `AGUARDAR`, hash canônico e horários *declarados*. Um hash local pode ser recriado depois do movimento. O próximo requisito é uma **testemunha externa, registrada antes de os preços-alvo começarem**, e uma auditoria contra alterações.

## Fluxo em duas etapas, rigorosamente nessa ordem

1. **Planejar, antes das decisões.** Preparar o plano via `freeze_fx_trial_roster_lab(...)`, com alvos futuros D1/W1 e `rule_version` fixo. Chamar `prepare_roster_github_anchor_lab(...)`, **sem precisar das 56 decisões**. Publicar exatamente `roster_anchor_body` em um comentário GitHub da PR/locus designado. Recuperar do GitHub o `id`, o `created_at`, o `updated_at`, o texto integral e a URL; esse primeiro `created_at` deve ocorrer **estritamente antes do primeiro `recorded_at` declarado** entre as 56 decisões.
2. **Registrar as decisões antes do alvo.** Congelar as 56 linhas via `freeze_full_fx_direction_census_lab(...)`, incluindo AGUARDAR + motivos. Chamar `prepare_census_github_anchor_lab(...)`; publicar o corpo **num segundo comentário**, contendo `roster_sha256` e `census_sha256`, ainda **antes da primeira abertura** entre D1/W1. Recuperar e arquivar a resposta da plataforma também antes do primeiro alvo. Se houver falha de GitHub, deixar a rodada **sem testemunho externo**, sem reconstruir cronologia retrospectivamente.
3. **Conferir duas referências.** `inspect_two_stage_github_anchor_claims_lab(...)` verifica integridade canônica local, escopo de repositório/PR, hashes esperados, corpo exato, URLs, IDs diferentes, ausência declarada de edição (`updated_at == created_at`), ordem e horários de primeira leitura. Se um comentário faltar, for editado, tiver corpo divergente ou for tardio, **não aceitar a rodada como pré-comprometida**.
4. **Auditoria separada com API/connector real.** **O módulo puro recebe os campos do GitHub do chamador, portanto não autentica a API nem o relógio do GitHub.** Mesmo quando o exame documental está consistente, o retorno é `LAB_GITHUB_TWO_ANCHOR_CHRONOLOGY_CLAIM_ONLY`, com `external_precommitment_verified=False`. O testemunho verdadeiro precisa ser obtido/reconferido por consulta independente à plataforma; guardar resposta originária, momento da consulta e trilha que não permita reutilizar decisões em outros alvos.

**Nunca postar forecasts reais antes de validar a fonte, o calendário e a autorização de divulgação.** O corpo do comentário de pesquisa contém apenas hashes, ID da campanha, versão do modelo, horizonte inicial e a marca `trade_authorized=false`; não expõe preços, credenciais ou recomendações de compra/venda.

## Testes realizados localmente

```bash
PYTHONPATH=.:../atlasquant_anchor_lab:_testdeps python -m unittest -q \
  test_atlasquant_trader_fx_trial_census_lab \
  test_atlasquant_trader_fx_census_github_anchor_lab
```

**57/57 testes sintéticos aprovados:** 34 do manifesto preexistente + 23 da nova âncora. Foram testados preparação antes da existência do censo, duas publicações diferentes, tentativa de publicar plano depois da primeira decisão, empate de segundos, previsões editadas, conteúdo modificado, censo re-hasheado, URLs trocadas, reutilização do mesmo comentário, anúncio depois do alvo e leitura documental retroativa. **Esses 57 testes não medem nenhum acerto de mercado.** O repositório ainda precisa executar sua suíte completa/CI com dependências reais.

## Dependências ainda abertas

- Confirmar sessão e timezone dos candles da corretora, em particular D1/W1.
- Receber dados macro *ponto-no-tempo*, com as fontes existentes antes das decisões.
- Voltar a acessar os candles do AM12, incluindo revisão da lacuna GBPNZD D1 em 30/09/2025.
- Capturar timestamps reais e íntegros **da plataforma** nas duas publicações de uma rodada futura; não usar `author_date` de commit como prova isolada.
- Unir o censo prospectivo pré-registrado à ponte `atlasquant_trader_mt5_paired_outcome_bridge_lab.py`, preservando também as abstenções, e executar validação cronológica fora da amostra, com contagem integral e sem otimização do limiar no período de teste.

**Restrições invariáveis:** `operational_bias=AGUARDAR`, `trade_authorized=False`, `publishable=False`, `external_precommitment_verified=False` nesta implementação pura, `validated_directional_accuracy=None`, custo novo **R$0**. A PR #1851 deve continuar **draft**, sem merge/deploy/ordens.
