# USD Macro Pro V11.0.6 — Strength Attribution + Audit Integrity

## Escopo

Esta versão parte da V11.0.5 e aplica correções derivadas dos 15 cenários do script `reproduzir_auditoria.py` fornecido pelo usuário, além da melhoria de explicação dos pontos de força entre moedas.

**Não foram alterados os pesos macro nem o Score Mestre.** As mudanças se concentram em integridade, fail-closed, frescor, sincronização, validação histórica e explicabilidade.

## Correções da auditoria

| Grupo | Problema reproduzido na V11.0.5 | Ajuste V11.0.6 |
|---|---|---|
| 01 | `AGUARDAR GATILHO` e `SEM GATILHO` recebiam score 100 por conter “GATILHO” | Correspondência com precedência negativa/espera; somente gatilho confirmado pode passar |
| 02 | Campos críticos ausentes ainda permitiam `EXECUTÁVEL` | Campos críticos ausentes passam a bloquear a execução |
| 03 | Riscos como `MUITO ALTO`, `CRITICAL`, `ATENÇÃO`, `N/D` podiam virar `NORMAL` | Normalização explícita + estado `DESCONHECIDO` fail-closed |
| 04 | `pd.NA`, `NaT`, `NaN` e timestamp futuro podiam parecer frescos | Timestamp inválido/futuro retorna indisponível e nunca fresco |
| 05 | Market Map de 7 dias podia continuar “pronto” | `updated_at` entra no gate; mapa antigo não é operacional |
| 06 | Mudança de direção podia reaproveitar evidência calculada para o lado anterior | Divergência entre direção atual e scanner invalida evidências antigas |
| 07 | Cache com listas de objetos vazios contava como candles suficientes | Cache agora valida datetime + OHLC + geometria + duplicatas |
| 08 | Leituras técnicas antigas ainda apareciam em `positives` | Alinhamento técnico só vira positivo se dados atuais estiverem válidos |
| 09 | ADR ausente virava `0%`, parecendo seguro | ADR ausente vira `N/D` e bloqueia execução até confirmação |
| 10 | SMT podia alinhar frames por posição mesmo sem timestamps coincidentes | SMT exige timestamps sincronizados; sem overlap = indisponível |
| 11 | Se direção mudasse e API falhasse, H4/H1/M15 antigos podiam sobreviver | Mudança de lado zera/invalida sinais derivados até nova leitura |
| 12 | `st.cache_data` ignorava `_token/_repo/_branch` por causa do prefixo `_` | Parâmetros renomeados para entrarem na chave de cache do Streamlit |
| 13 | “Fed rules out rate cuts” era classificado como dovish | Negação semântica básica: descartar cortes = hawkish |
| 14 | FVG invalidado podia reaparecer como “em teste” após revisita | FVG atravessado é marcado `INVALIDADO` e não confirma |
| 15 | Validação podia usar último M15 anterior ao congelamento do sinal como “entrada” | Primeiro congela o sinal; entrada só é registrada no primeiro M15 fechado após o sinal |

## Strength Attribution

A seção de força agora mostra uma conta de chegada explícita:

`Macro puro + Fed + Ajustes do modelo = Força final`

Além disso:

- separa fatores que favorecem a moeda base e a moeda cotada;
- mostra o valor líquido de cada fator;
- mostra soma bruta das vantagens de cada lado;
- reconcilia exatamente com a diferença final do par;
- deixa claro que os pontos são internos do modelo, não pips e não probabilidade de lucro.

Exemplo conceitual:

- Macro puro: USD +20,3 pts
- Fed: USD +X
- Ajustes: EUR +Y
- Resultado final: USD +21,3 pts

## Testes locais executados

- 51 testes focados: **OK**
- Script de reprodução da auditoria: **comportamentos críticos corrigidos**
- Compilação/sintaxe dos módulos modificados: **OK**

Observação: o teste completo de produção ainda deve ser executado no GitHub Actions com Python 3.12 e Streamlit real após o upload, como já é feito no fluxo `Quality tests`.

## Arquivos principais alterados

- `decision_integrity_v110.py`
- `data_readiness_v1101.py`
- `institutional_engine_v110.py`
- `pair_intelligence_v110.py`
- `autopilot_v107.py`
- `currency_news_v107.py`
- `ict_execution_v108.py`
- `strength_breakdown_v1104.py`
- `usd_macro_pro_v4_cloud.py`
- testes V11.0.6 e testes antigos atualizados para a nova política fail-closed
- `.github/workflows/quality-tests.yml`
