# Checkpoint Trader — Integridade FX 28/28 e força relativa G8 (LAB)

Data: 04/11/2026 · Prioridade: AtlasQuant Trader — Forex e Índices.

## Verificação realizada
- `atlasquant_fx_universe.py`: universo canônico G8 com **28 cruzamentos sem inversões duplicadas**; oito moedas. Força/score é classificação relativa, não probabilidade de lucro.
- `atlasquant_trader_radar_compact_ui.py`: a interface exibe força G8 e Top 10 somente quando recebe um contrato diário nomeado e validado upstream. **Esse upstream ainda não está ligado a um provedor real verificado.** O Top 10 de variação **não** representa melhores entradas.
- `dados/autopilot_daily_cache_v107.json`: contém `updated_at = 2026-09-17T06:28:09Z`. O carimbo do arquivo no disco é recente, mas os **dados internos estão vencidos**, e há apenas sete pares observados no inventário anterior. Não foi usado como feed atual.
- Integrações antigas de Twelve Data (`CHAVE_TWELVE_DATA`) e EODHD (`CHAVE_EODHD`) existem no repositório; a assinatura ativa, a quota, a cobertura de 28 pares e os direitos de cotações não estão comprovados. **Nenhuma chave foi lida ou utilizada nesta etapa.** Não fizemos requisições.
- WIN/WDO e índices não herdam automaticamente os pesos de Forex, nem este método de força G8.

## Contrato novo e independente
`atlasquant_fx_daily_integrity_research.py` recebe **somente payload explicitamente OFFLINE_RESEARCH** do esquema `ATLASQUANT_FX_28_QUOTE_RESEARCH_V1`. Os campos incluem, para cada um dos 28 pares: `bid`, `ask`, `previous_close`, `observed_at`, `reference_at`, `source`. O snapshot geral inclui `as_of`, `source` e `schema`.

Bloqueios atômicos (sem ranking parcial):
1. Qualquer par faltando, par extra, fonte vazia/divergente ou número inválido → **BLOCKED**.
2. Bid maior que ask, preço anterior não positivo, spread acima de 0,5%, variação diária acima de 15% → **BLOCKED**. Limites provisórios de qualidade, sem calibração para previsão.
3. Timestamp ausente/sem fuso, futuro, snapshot ou cotação com idade acima de 15 minutos, observação mais de 3 minutos anterior ao snapshot ou observações entre si com amplitude acima de 90 segundos → **BLOCKED**.
4. Comparação diária exigindo **a mesma referência temporal para todos os pares**; dados de sessões misturadas ou fechamento incompatível → **BLOCKED**.
5. Incoerência acima de 0,30 ponto logarítmico entre o retorno observado e o diferencial implícito na força G8 → **BLOCKED**. É teste de integridade cruzada, não arbitragem garantida.

## Matemática verificável
Para o par **BASE/QUOTE**, calcular:
- **Preço de referência do snapshot:** médio `(bid + ask) / 2`.
- **Retorno percentual diário:** `100 × (médio / fechamento_anterior − 1)`.
- **Retorno logarítmico em pontos:** `r = 100 × ln(médio / fechamento_anterior)`.
- **Força relativa da moeda C:** nos **sete cruzamentos totais que contêm C**, somar cada retorno logarítmico com sinal **+** quando C é a base e com sinal **−** quando C é a cotação; dividir essa soma por **8** (oito moedas no universo completo).

Uma moeda participa em 7 arestas do grafo; **dividir por 8** é o fator de centragem da solução de mínimos quadrados do grafo completo. Essa força fica centrada em zero e tem unidade de **pontos log-relativos** — não é variação absoluta da moeda nem uma porcentagem de acerto.

Para cada par, diferença `força_base − força_cotação` deve explicar seu retorno log dentro da tolerância. O Top 10 é ordenado apenas pelos **retornos percentuais simples diários** dos 28 pares; não é ranking de entradas, e pode conter pares negativos.

## Posição de segurança e promoção
O contrato de saída é distinto: `ATLASQUANT_FX_28_STRENGTH_RESEARCH_V1`, estado `RESEARCH_ONLY`, e todos `publishable`, `provider_authenticated`, `trade_authorized` e `accuracy_verified` falsos. **Nunca entregar este resultado diretamente ao contrato `VALIDATED_DAILY` da interface.**

Nenhuma integração com dinheiro real, providers, AION ou Worker. Nenhuma despesa e nenhuma autorização adicional.

## Próximos gates antes de publicar números verdadeiros
1. Inventário de **quais 28 pares realmente existem na fonte disponível** e respectivos intervalos, permissões e quotas. Observar sem consumir a quota paga até autorização.
2. Adapter de fonte confiável com checagem de integridade/autenticidade de produtor; snapshot do dia e revalidação de relógio ao exibir.
3. Testes de abertura, fechamento, feriados, virada de fuso e fim de semana. Testes de dispersão e spread em histórico real.
4. Backtest fora da amostra, walk-forward e paper do método antes de traduzir rankings em decisões; medir risco e R líquido.
5. Somente depois, revisão humana e publicação gradual. O alvo de assertividade >=80% segue **não demonstrado**.

## Mudança visual nesta entrega
No Radar, dentro da seção de força relativa das moedas, há um **painel recolhível** explicando o método e o estado pendente, sem adicionar uma nova aba nem preencher valores artificiais.
