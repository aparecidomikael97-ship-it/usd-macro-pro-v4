# AtlasQuant Trader — sprint de aceleração com precisão seletiva e provas por etapa — 11/11/2026

**Escopo:** AtlasQuant Trader, 28 Forex G8; depois XAUUSD/índices com verificações específicas. **Nenhuma operação, assinatura, deploy ou merge.** O usuário está no celular; trabalho feito em código e documentação GitHub. Branch `lab/trader-mt5-28fx-live-coverage-20261107`, PR draft #1851.

## Diagnóstico de lacunas reais, sem duplicar o que já existe

**Já existentes no projeto:** macro bilateral por pares, matriz G8/FX28, auditoria de simetria de 28 pares, conferência D1/W1, gate seletivo com ABSTAIN, veto de notícias/blackout, regime de mercado, controle de timestamps/surpresas, congelamento de hipóteses, testes fora da amostra declarativos, contabilidade de oportunidades abstidas, snapshots MT5, plano prospectivo de PPI com sete pares USD, e `atlasquant_calibration_lab.py` com faixas de scores históricos e intervalos de Wilson. Esses recursos **não são atualmente prova de 80%-90% de assertividade** e não precisam ser recriados.

**Faltas de alto valor prioritárias:**

1. **Dependência de evidências:** CPI, rendimento dos títulos, DXY e notícia derivada frequentemente são reações do **mesmo choque**. Contar quatro leituras como quatro provas de origem independente superestima a convicção. Fixar identificação por evento-raiz, conflito e cronologia.
2. **Preço já estendido + liquidez/custo:** conferir distância de movimento antes do viés, volatilidade recente e spread bid/ask observados na janela real. Se custo supera o movimento plausível ou houve extensão excessiva, abster-se. O repositório tem validação de preço M15 e regime, mas **não foi identificado um gate integrado com spread executável e movimento esperado líquido calibrado**; não inventar spread com candles OHLC.
3. **Calibração prospectiva e base rate:** score sintético 0-10 ou bandas de uma tabela de Streamlit não são probabilidade direcional calibrada. Fazer pré-registro das oportunidades totais, registros de abstenção e baseline; usar métricas como Brier score, log loss, reliability curve, cobertura, resultados condicionais por regime e custo líquido.
4. **Risco de concentração cross-pair:** sete pares com USD afetados pelo PPI representam **um evento macro**, não sete choques independentes. Agrupar exposição temática; validação de portfólio separada da validade de cada par.
5. **Reconciliação de macro de verdade:** duas moedas por par, métrica e série comparável, data e período verdadeiros, consenso pré-evento, revisões e licenças. Fonte atrasada e notícias geopolíticas sem tradução causal => `AGUARDAR`.
6. **Atenção ao calendário:** atualização 3x por dia pode ser suficiente para relatórios de contexto, mas **não** para uma hipótese M15 no instante de dado surpresa. Um futuro coletor *event-driven* licenciado e autorizado deve atualizar a janela dos eventos de alta importância e registrar primeiro pacote e latência, sempre distinguindo captura posterior de conhecimento pré-evento.

## Implementação feita neste sprint: origem compartilhada da evidência

Arquivos de código:
- `atlasquant_trader_fx_evidence_dependency_gate_lab.py`
- `test_atlasquant_trader_fx_evidence_dependency_gate_lab.py`

**Função:** entrada = um par FX28, horizonte D1/W1, horário decisório e evidências `factor_id`, `root_catalyst_id`, `source_family`, `relative_side`, horário de captura alegado e SHA256 alegado. Saída: inventário dos *fatores* e dos *eventos-raiz declarados*, bloqueio por conflito e cronologia, diversidade de grupos/famílias meramente documental, estado `AGUARDAR` sempre.

- Em ensaio sintético: `CPI_US`, `DXY_MOVE`, `US_YIELD_MOVE` todos atrelados ao mesmo `US_CPI_OCT2026` => **3 fatores, apenas 1 raiz declarada; abstenção**.
- Em ensaio sintético com três raízes declaradas e duas famílias, a análise retorna somente **candidato documental**, jamais viés, sinal ou probabilidade.
- Conflito de sinais base/cotada, identificador de fator duplicado, fonte futura, família desconhecida, raiz `UNKNOWN`, SHA inválido e falta de dados => bloqueio/abstenção.
- Os limiares `MIN_CLAIMED_ROOTS=3` e `MIN_CLAIMED_FAMILIES=2` são **hipóteses de pesquisa não calibradas**; podem ser restritivos demais e **não** serão ativados em produção sem experimento incremental fora da amostra.
- **Limite crucial:** raiz/família, horário e SHA são informados pelo chamador. **Não há certificação real de independência causal ou estatística**. A coerência estrutural não equivale a fonte autenticada.
- **20 testes sintéticos PASS** em ambiente isolado. O módulo é puro, sem acesso ao computador do usuário, conectores de mercado ou fontes externas. CI em Python 3.11/3.12 adicionada.

## Caminho mais rápido sem tornar o sistema pesado

**Trilha A — dados (prioridade P0):** automatizar a cobertura de indicadores macro relevantes G8 com controle de UTC, primeira publicação, revisões e concorrência de fontes; reutilizar integrações existentes. PPI 13/11 com TD e TE já capturados antes do evento serve como primeiro exercício prospectivo; calendários/alertas já agendados, não duplicar.

**Trilha B — Precision Gate (P0):** unir, somente depois de provas suficientes, controles existentes: qualidade e antiguidade, macro bilateral, alinhamento D1/W1, evento/risco geopolítico, raiz comum, regime, liquidez/spread e preço estendido. Cada bloqueio terá motivo claro, não um score inflado. Até integração documentada e segura, os módulos novos são **auditorias isoladas**.

**Trilha C — prova de resultado (P0):** definir coorte de todas as oportunidades (incluindo sem viés) e janelas do período antes de observar desfechos; comparar baseline vs macro vs macro+filtros. Reportar cobertura, acertos, erros, custo líquido e estabilidade por regime. Testes sintéticos de GitHub provam regressão **de código**, não taxa de acerto de mercado.

**Trilha D — apresentação (P1, somente após auditorias):** Radar com três saídas: `VIES_PESQUISA_QUALIFICADO`, `AGUARDAR` e `BLOQUEADO_POR_DADOS`; texto explica decisão; probabilidade percentual **somente com calibração estatística real e validação por horizonte**. Não encher a tela de 'sinais'.

## Critérios objetivos de priorização

- Primeiro corrigir falhas com risco de gerar convicção falsa: fonte futura/vencida, família duplicada, inversão inconsistente, notícia já precificada, price extension, mercado ilíquido, concentração de evento.
- Depois aumentar cobertura (28 pares G8, XAUUSD, EUA e WIN/WDO em modelos adequados), **sem expandir para sinal quando a evidência é insuficiente**.
- Não comprar dados nem instalar integrações pagas até provar, em comparação controlada, ganho incremental de qualidade e cobertura.
- Não prometer número arbitrário de dias até '80%': desenvolvimento de infraestrutura pode acelerar, evidência fora da amostra depende do tempo e quantidade de eventos reais observados.

## Estado

`GO-LAB` para checagens sintéticas. `NO-GO` para publicar viés probabilístico ou integrar sinais. `HARD NO-GO` operações reais. **Não mesclar PR #1851 nem criar worker sem autorização**. A meta é reduzir sinais ruins, com prova de abstenções e resultado líquido, e não aumentar a quantidade de indicadores.
